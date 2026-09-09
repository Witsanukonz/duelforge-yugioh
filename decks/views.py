from collections import Counter

from django.core.exceptions import SuspiciousFileOperation, ValidationError
from django.contrib.auth.decorators import login_required
from django.db.models import Case, IntegerField, OuterRef, Q, Subquery, Sum, When
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import content_disposition_header
from django.utils.text import get_valid_filename
from django.views.decorators.http import require_GET, require_POST

from cards.models import Card
from cards.views import serialize_card
from banlists.services import banlist_metadata, get_active_banlist
from config.api import api_error, paginate, parse_bool, parse_json
from config.pagination import paginate_queryset, pagination_query

from .forms import DeckForm
from .models import Deck, DeckCard
from .services import copy_sample_deck, move_deck_card_copy, save_deck_card, validate_deck
from .ydk import SECTION_ORDER, serialize_ydk


CARD_TYPE_GROUPS = ("Monsters", "Spells", "Traps", "Other")
CARD_TYPE_STYLES = {
    "Monsters": "monster",
    "Spells": "spell",
    "Traps": "trap",
    "Other": "other",
}
MAX_ARCHETYPE_ROWS = 6


def serialize_deck_card(entry):
    return {
        "id": entry.pk,
        "card": serialize_card(entry.card),
        "quantity": entry.quantity,
        "section": entry.section,
        "note": entry.note,
        "added_at": entry.added_at.isoformat(),
    }


def serialize_deck(deck, *, include_cards=False):
    counts = {
        section: getattr(deck, f"{section.lower()}_count", None)
        for section in ("MAIN", "EXTRA", "SIDE")
    }
    if any(value is None for value in counts.values()):
        rows = deck.deck_cards.values("section").annotate(total=Sum("quantity"))
        counts = {"MAIN": 0, "EXTRA": 0, "SIDE": 0}
        for row in rows:
            counts[row["section"]] = row["total"] or 0

    payload = {
        "id": deck.pk,
        "owner": {
            "id": deck.owner_id,
            "username": deck.owner.get_username(),
        },
        "name": deck.name,
        "description": deck.description,
        "deck_type": deck.deck_type,
        "format": deck.format,
        "ban_list": banlist_metadata(deck.ban_list if deck.ban_list_id else None),
        "is_public": deck.is_public,
        "is_sample": deck.is_sample,
        "sample_archetype": deck.sample_archetype,
        "cover_image": deck.listing_cover_url or None,
        "counts": counts,
        "created_at": deck.created_at.isoformat(),
        "updated_at": deck.updated_at.isoformat(),
    }
    if include_cards:
        payload["cards"] = [
            serialize_deck_card(entry)
            for entry in deck.deck_cards.select_related("card").order_by("section", "card__name")
        ]
    return payload


def deck_breakdown(deck_payload):
    archetype_counts = Counter()
    card_type_counts = Counter()

    for entry in deck_payload.get("cards", []):
        quantity = entry.get("quantity", 0)
        card = entry.get("card", {})
        if quantity < 1:
            continue

        archetype = str(card.get("archetype") or "ไม่มี Archetype").strip()
        archetype_counts[archetype or "ไม่มี Archetype"] += quantity

        card_type = str(card.get("card_type") or "").lower()
        if "monster" in card_type:
            card_type_counts["Monsters"] += quantity
        elif "spell" in card_type:
            card_type_counts["Spells"] += quantity
        elif "trap" in card_type:
            card_type_counts["Traps"] += quantity
        else:
            card_type_counts["Other"] += quantity

    archetype_rows = sorted(
        archetype_counts.items(),
        key=lambda item: (-item[1], item[0].casefold()),
    )
    if len(archetype_rows) > MAX_ARCHETYPE_ROWS:
        visible_rows = archetype_rows[: MAX_ARCHETYPE_ROWS - 1]
        visible_rows.append(
            ("อื่น ๆ", sum(count for _, count in archetype_rows[MAX_ARCHETYPE_ROWS - 1 :]))
        )
        archetype_rows = visible_rows

    max_archetype_count = max((count for _, count in archetype_rows), default=0)
    archetypes = [
        {
            "label": label,
            "count": count,
            "bar_percent": round((count / max_archetype_count) * 100, 2),
        }
        for label, count in archetype_rows
    ]

    total_cards = sum(card_type_counts.values())
    offset = 0.0
    card_types = []
    for label in CARD_TYPE_GROUPS:
        count = card_type_counts[label]
        if not count:
            continue
        percent = round((count / total_cards) * 100, 2)
        card_types.append({
            "label": label,
            "count": count,
            "percent": percent,
            "remainder": round(100 - percent, 2),
            "offset": round(offset, 2),
            "style": CARD_TYPE_STYLES[label],
        })
        offset += percent

    return {
        "total_cards": total_cards,
        "archetypes": archetypes,
        "card_types": card_types,
    }


def form_errors(form):
    return api_error(
        "Validation failed.",
        errors=form.errors.get_json_data(),
    )


def validation_error(error):
    details = getattr(error, "message_dict", {"__all__": error.messages})
    return api_error("Validation failed.", errors=details)


def deck_form_payload(payload, instance=None):
    fields = ("name", "description", "deck_type", "format", "ban_list", "is_public")
    if instance is None:
        return {field: payload[field] for field in fields if field in payload}
    data = {
        "name": instance.name,
        "description": instance.description,
        "deck_type": instance.deck_type,
        "format": instance.format,
        "ban_list": instance.ban_list_id or "",
        "is_public": instance.is_public,
    }
    for field in fields:
        if field in payload:
            data[field] = "" if field == "ban_list" and payload[field] is None else payload[field]
    return data


def deck_collection(request):
    if request.method == "GET":
        decks = Deck.objects.select_related("owner", "ban_list")
        mine = parse_bool(request.GET.get("mine"))
        if mine is True:
            if not request.user.is_authenticated:
                return api_error("Authentication required.", status=401)
            decks = decks.filter(owner=request.user)
        elif request.user.is_authenticated:
            decks = decks.filter(Q(owner=request.user) | Q(is_public=True))
        else:
            decks = decks.filter(is_public=True)

        query = request.GET.get("q", "").strip()
        if query:
            decks = decks.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(deck_type__icontains=query)
            )
        deck_format = request.GET.get("format", "").upper()
        if deck_format:
            decks = decks.filter(format=deck_format)

        decks = decks.annotate(
            main_count=Sum("deck_cards__quantity", filter=Q(deck_cards__section="MAIN"), default=0),
            extra_count=Sum("deck_cards__quantity", filter=Q(deck_cards__section="EXTRA"), default=0),
            side_count=Sum("deck_cards__quantity", filter=Q(deck_cards__section="SIDE"), default=0),
        ).order_by("-updated_at", "-pk")
        page, error = paginate(request, decks, default_size=12, max_size=50)
        if error:
            return error
        return JsonResponse({
            "results": [serialize_deck(deck) for deck in page["items"]],
            "pagination": page["pagination"],
        })

    if request.method == "POST":
        if not request.user.is_authenticated:
            return api_error("Authentication required.", status=401)
        payload, error = parse_json(request)
        if error:
            return error
        if "ban_list" not in payload:
            active = get_active_banlist(str(payload.get("format", "TCG")).upper())
            payload["ban_list"] = active.pk if active else None
        form = DeckForm(deck_form_payload(payload))
        if not form.is_valid():
            return form_errors(form)
        deck = form.save(commit=False)
        deck.owner = request.user
        deck.save()
        return JsonResponse({"deck": serialize_deck(deck)}, status=201)

    return api_error("Method not allowed.", status=405)


def visible_deck(request, deck_id):
    decks = Deck.objects.select_related("owner", "ban_list")
    if request.user.is_authenticated:
        decks = decks.filter(Q(owner=request.user) | Q(is_public=True))
    else:
        decks = decks.filter(is_public=True)
    return get_object_or_404(decks, pk=deck_id)


def deck_export_filename(deck):
    base_name = deck.name[:-4] if deck.name.lower().endswith(".ydk") else deck.name
    try:
        safe_name = get_valid_filename(base_name)
    except SuspiciousFileOperation:
        safe_name = f"deck-{deck.pk}"
    safe_name = safe_name[:180].rstrip(".") or f"deck-{deck.pk}"
    return f"{safe_name}.ydk"


@require_GET
def deck_export_page(request, deck_id):
    deck = visible_deck(request, deck_id)
    sections = {section: Counter() for section in SECTION_ORDER}
    rows = deck.deck_cards.order_by("pk").values_list(
        "section", "card__card_id", "quantity"
    )
    for section, card_id, quantity in rows:
        sections[section][card_id] += quantity

    response = HttpResponse(
        serialize_ydk(sections, creator="DUELFORGE"),
        content_type="application/octet-stream",
    )
    response.headers["Content-Disposition"] = content_disposition_header(
        True,
        deck_export_filename(deck),
    )
    return response


def owned_deck(request, deck_id):
    if not request.user.is_authenticated:
        return None, api_error("Authentication required.", status=401)
    return get_object_or_404(
        Deck.objects.select_related("owner", "ban_list"),
        pk=deck_id,
        owner=request.user,
        is_sample=False,
    ), None


def deck_detail(request, deck_id):
    if request.method == "GET":
        deck = visible_deck(request, deck_id)
        return JsonResponse({"deck": serialize_deck(deck, include_cards=True)})

    deck, error = owned_deck(request, deck_id)
    if error:
        return error
    if request.method == "PATCH":
        payload, error = parse_json(request)
        if error:
            return error
        if "format" in payload and "ban_list" not in payload:
            active = get_active_banlist(str(payload["format"]).upper())
            payload["ban_list"] = active.pk if active else None
        form = DeckForm(deck_form_payload(payload, deck), instance=deck)
        if not form.is_valid():
            return form_errors(form)
        deck = form.save()
        return JsonResponse({"deck": serialize_deck(deck, include_cards=True)})
    if request.method == "DELETE":
        deck.delete()
        return JsonResponse({}, status=204)
    return api_error("Method not allowed.", status=405)


def deck_validation(request, deck_id):
    if request.method != "GET":
        return api_error("Method not allowed.", status=405)
    deck = visible_deck(request, deck_id)
    return JsonResponse({"validation": validate_deck(deck)})


def deck_cards(request, deck_id):
    if request.method != "POST":
        return api_error("Method not allowed.", status=405)
    deck, error = owned_deck(request, deck_id)
    if error:
        return error
    payload, error = parse_json(request)
    if error:
        return error

    card_id = payload.get("card_id")
    if card_id is None:
        return api_error("card_id is required.")
    card = get_object_or_404(Card, card_id=card_id)
    try:
        entry, created = save_deck_card(
            deck=deck,
            card=card,
            quantity=payload.get("quantity", 1),
            section=payload.get("section", "MAIN"),
            note=payload.get("note", ""),
        )
    except ValidationError as exc:
        return validation_error(exc)
    return JsonResponse(
        {"deck_card": serialize_deck_card(entry)},
        status=201 if created else 200,
    )


def deck_card_detail(request, deck_id, entry_id):
    deck, error = owned_deck(request, deck_id)
    if error:
        return error
    entry = get_object_or_404(
        DeckCard.objects.select_related("card"), pk=entry_id, deck=deck
    )
    if request.method == "PATCH":
        payload, error = parse_json(request)
        if error:
            return error
        if "move_quantity" in payload:
            if payload.get("move_quantity") != 1:
                return api_error("move_quantity must be 1.")
            section = payload.get("section")
            if not section:
                return api_error("section is required when moving a card copy.")
            try:
                moved = move_deck_card_copy(
                    deck=deck,
                    entry=entry,
                    section=section,
                )
            except ValidationError as exc:
                return validation_error(exc)
            cards = deck.deck_cards.select_related("card").order_by(
                "section", "card__name"
            )
            return JsonResponse({
                "deck_card": serialize_deck_card(moved),
                "deck_cards": [serialize_deck_card(card) for card in cards],
            })
        try:
            entry, _ = save_deck_card(
                deck=deck,
                card=entry.card,
                quantity=payload.get("quantity", entry.quantity),
                section=payload.get("section", entry.section),
                note=payload.get("note", entry.note),
                entry=entry,
            )
        except ValidationError as exc:
            return validation_error(exc)
        return JsonResponse({"deck_card": serialize_deck_card(entry)})
    if request.method == "DELETE":
        entry.delete()
        return JsonResponse({}, status=204)
    return api_error("Method not allowed.", status=405)


def deck_list_page(request):
    query = request.GET.get("q", "").strip()
    library_tab = request.GET.get("library", "character")
    if library_tab not in {"character", "player"}:
        library_tab = "character"
    base_decks = deck_listing_queryset()
    if query:
        base_decks = base_decks.filter(
            Q(name__icontains=query)
            | Q(deck_type__icontains=query)
            | Q(sample_archetype__icontains=query)
            | Q(description__icontains=query)
        )

    if request.user.is_authenticated:
        my_decks = base_decks.filter(owner=request.user, is_sample=False)
        community_decks = base_decks.filter(is_public=True, is_sample=False).exclude(
            owner=request.user
        )
    else:
        my_decks = Deck.objects.none()
        community_decks = base_decks.filter(is_public=True, is_sample=False)

    my_page = paginate_queryset(
        request,
        my_decks,
        page_size=12,
        page_parameter="my_page",
    )
    featured_decks = base_decks.filter(is_sample=True, is_public=True)
    featured_page = paginate_queryset(
        request,
        featured_decks,
        page_size=12,
        page_parameter="sample_page",
    )
    player_page = paginate_queryset(
        request,
        community_decks,
        page_size=12,
        page_parameter="player_page",
    )
    library_page = featured_page if library_tab == "character" else player_page
    library_page_parameter = "sample_page" if library_tab == "character" else "player_page"
    return render(request, "decks/deck_list.html", {
        "my_decks": my_page,
        "my_page": my_page,
        "my_pagination_query": pagination_query(request, page_parameter="my_page"),
        "featured_page": featured_page,
        "player_page": player_page,
        "library_page": library_page,
        "library_page_parameter": library_page_parameter,
        "library_pagination_query": pagination_query(
            request, page_parameter=library_page_parameter
        ),
        "library_tab": library_tab,
        "community_decks": community_decks,
        "query": query,
        "owned_count": (
            Deck.objects.filter(owner=request.user, is_sample=False).count()
            if request.user.is_authenticated else 0
        ),
    })


def deck_listing_queryset():
    section_order = Case(
        When(section="MAIN", then=0),
        When(section="EXTRA", then=1),
        default=2,
        output_field=IntegerField(),
    )
    cover_card = (
        DeckCard.objects.filter(deck=OuterRef("pk"))
        .order_by(section_order, "added_at", "pk")
        .values("card__card_id")[:1]
    )
    return Deck.objects.select_related("owner", "ban_list").annotate(
        main_count=Sum("deck_cards__quantity", filter=Q(deck_cards__section="MAIN"), default=0),
        extra_count=Sum("deck_cards__quantity", filter=Q(deck_cards__section="EXTRA"), default=0),
        side_count=Sum("deck_cards__quantity", filter=Q(deck_cards__section="SIDE"), default=0),
        cover_card_ygo_id=Subquery(cover_card),
    ).order_by("-updated_at", "-pk")


@login_required
def deck_create_page(request):
    ban_lists = current_builder_banlists()
    default_ban_list = next((item for item in ban_lists if item.format == "TCG"), None)
    return render(request, "decks/deck_builder.html", {
        "deck": None,
        "deck_payload": None,
        "can_edit": True,
        "ban_lists": ban_lists,
        "default_ban_list_id": default_ban_list.pk if default_ban_list else None,
    })


def deck_builder_page(request, deck_id):
    deck = visible_deck(request, deck_id)
    can_edit = (
        request.user.is_authenticated
        and request.user == deck.owner
        and not deck.is_sample
    )
    deck_payload = serialize_deck(deck, include_cards=True)
    return render(request, "decks/deck_builder.html", {
        "deck": deck,
        "deck_payload": deck_payload,
        "deck_breakdown": None if can_edit else deck_breakdown(deck_payload),
        "can_edit": can_edit,
        "ban_lists": current_builder_banlists(deck),
        "default_ban_list_id": None,
    })


@login_required
@require_POST
def copy_sample_deck_page(request, deck_id):
    sample_deck = get_object_or_404(
        Deck.objects.select_related("ban_list"),
        pk=deck_id,
        is_sample=True,
        is_public=True,
    )
    copied_deck = copy_sample_deck(sample_deck=sample_deck, owner=request.user)
    return redirect("decks_page:builder", deck_id=copied_deck.pk)


def current_builder_banlists(deck=None):
    ban_lists = [
        banlist
        for banlist in (get_active_banlist("TCG"), get_active_banlist("OCG"))
        if banlist is not None
    ]
    if deck and deck.ban_list_id and all(item.pk != deck.ban_list_id for item in ban_lists):
        ban_lists.append(deck.ban_list)
    return ban_lists
