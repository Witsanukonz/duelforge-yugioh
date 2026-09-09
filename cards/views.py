import re
from urllib.parse import urlencode, urlsplit

from django.db.models import Q
from django.db.models import Case, IntegerField, Value, When
from django.db.models.functions import Length, Lower, Replace
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import Resolver404, resolve, reverse
from django.views.decorators.csrf import ensure_csrf_cookie

from config.api import api_error, paginate
from config.pagination import paginate_queryset

from .catalog import (
    CARD_CATEGORIES,
    MONSTER_FRAME_GROUPS,
    card_category_from_value,
    get_card_catalog_facets,
    monster_card_filter,
)
from .models import Card
from .services import TranslationError, translate_description


def serialize_card(card, *, banlist_entry=None, include_ban_status=False):
    payload = {
        "id": card.pk,
        "card_id": card.card_id,
        "name": card.name,
        "card_type": card.card_type,
        "frame_type": card.frame_type,
        "description": card.description,
        "description_th": card.description_th,
        "race": card.race,
        "attribute": card.attribute,
        "archetype": card.archetype,
        "atk": card.atk,
        "defense": card.defense,
        "level": card.level,
        "image_url": card.image_url,
        "image_url_small": card.image_url_small,
        "local_image_url": card.local_image_url,
        "is_extra_deck_card": card.is_extra_deck_card,
    }
    if include_ban_status:
        payload["ban_status"] = banlist_entry.status if banlist_entry else None
        payload["max_copies"] = banlist_entry.max_copies if banlist_entry else 3
    return payload


def apply_card_search(cards, query):
    tokens = re.findall(r"\w+", query, flags=re.UNICODE)
    if not tokens:
        return cards.none()

    def compact_expression(field):
        expression = Lower(field)
        for character in (" ", "-", "'", "’", ",", "."):
            expression = Replace(expression, Value(character), Value(""))
        return expression

    compact_query = "".join(tokens).lower()
    cards = cards.annotate(
        search_name_compact=compact_expression("name"),
        search_archetype_compact=compact_expression("archetype"),
    )

    any_field_match = Q()
    name_match = Q()
    archetype_match = Q()
    for token in tokens:
        any_field_match &= (
            Q(name__icontains=token)
            | Q(archetype__icontains=token)
            | Q(description__icontains=token)
        )
        name_match &= Q(name__icontains=token)
        archetype_match &= Q(archetype__icontains=token)

    compact_match = (
        Q(search_name_compact__icontains=compact_query)
        | Q(search_archetype_compact__icontains=compact_query)
    )
    return cards.filter(any_field_match | compact_match).annotate(
        search_rank=Case(
            When(name__iexact=query, then=Value(0)),
            When(search_name_compact__startswith=compact_query, then=Value(1)),
            When(name_match | Q(search_name_compact__icontains=compact_query), then=Value(2)),
            When(archetype_match | Q(search_archetype_compact__icontains=compact_query), then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        ),
        search_name_length=Length("name"),
    )


def card_list(request):
    if request.method != "GET":
        return api_error("Method not allowed.", status=405)

    cards = Card.objects.all()
    query = request.GET.get("q", "").strip()
    if query:
        cards = apply_card_search(cards, query)

    filter_fields = {
        "type": "card_type",
        "frame_type": "frame_type",
        "attribute": "attribute",
        "race": "race",
        "archetype": "archetype",
    }
    for parameter, field in filter_fields.items():
        value = request.GET.get(parameter, "").strip()
        if value:
            cards = cards.filter(**{f"{field}__iexact": value})

    allowed_ordering = {
        "name", "-name", "atk", "-atk", "level", "-level",
        "updated_at", "-updated_at",
    }
    requested_ordering = request.GET.get("ordering")
    ordering = requested_ordering or "name"
    if ordering not in allowed_ordering:
        return api_error("Unsupported ordering value.")

    if query and requested_ordering is None:
        cards = cards.order_by("search_rank", "search_name_length", "name", "pk")
    else:
        cards = cards.order_by(ordering, "pk")
    page, error = paginate(request, cards)
    if error:
        return error

    page_cards = list(page["items"])
    restriction_map = {}
    include_ban_status = False
    banlist_id = request.GET.get("ban_list", "").strip()
    if banlist_id:
        try:
            banlist_id = int(banlist_id)
        except (TypeError, ValueError):
            return api_error("ban_list must be an integer.")

        from banlists.models import BanList, BanListEntry

        if not BanList.objects.filter(pk=banlist_id).exists():
            return api_error("Ban list not found.", status=404)
        restriction_map = {
            entry.card_id: entry
            for entry in BanListEntry.objects.filter(
                ban_list_id=banlist_id,
                card_id__in=[card.pk for card in page_cards],
            ).only("card_id", "status", "max_copies")
        }
        include_ban_status = True

    return JsonResponse({
        "results": [
            serialize_card(
                card,
                banlist_entry=restriction_map.get(card.pk),
                include_ban_status=include_ban_status,
            )
            for card in page_cards
        ],
        "pagination": page["pagination"],
    })


def card_detail(request, card_id):
    if request.method != "GET":
        return api_error("Method not allowed.", status=405)
    card = get_object_or_404(Card, card_id=card_id)
    return JsonResponse({"card": serialize_card(card)})


def card_translation(request, card_id):
    if request.method != "POST":
        return api_error("Method not allowed.", status=405)

    card = get_object_or_404(Card, card_id=card_id)
    if not card.description:
        return JsonResponse({"translation": "", "cached": True})
    if card.description_th:
        return JsonResponse({"translation": card.description_th, "cached": True})

    try:
        translation = translate_description(card.description)
    except TranslationError as error:
        return api_error(str(error), status=503)

    card.description_th = translation
    card.save(update_fields=["description_th"])
    return JsonResponse({"translation": translation, "cached": False})


def card_catalog_page(request):
    cards = Card.objects.all()
    query = request.GET.get("q", "").strip()
    requested_type = request.GET.get("type", "").strip()
    selected_type = card_category_from_value(requested_type)
    uses_category_filter = requested_type.lower() in CARD_CATEGORIES
    facets = get_card_catalog_facets()
    attributes = facets["attributes"]
    monster_types = facets["monster_types"]
    spell_types = facets["spell_types"]
    trap_types = facets["trap_types"]
    monster_frames = facets["monster_frames"]

    if query:
        cards = apply_card_search(cards, query)

    if uses_category_filter and selected_type == "monster":
        cards = cards.filter(monster_card_filter())
    elif uses_category_filter and selected_type == "spell":
        cards = cards.filter(card_type__iexact="Spell Card")
    elif uses_category_filter and selected_type == "trap":
        cards = cards.filter(card_type__iexact="Trap Card")
    elif requested_type:
        cards = cards.filter(card_type__iexact=requested_type)

    selected_attribute = ""
    selected_race = ""
    selected_frame = ""
    requested_attribute = request.GET.get("attribute", "").strip()
    requested_race = request.GET.get("race", "").strip()
    requested_frame = request.GET.get("frame", "").strip().lower()

    if selected_type == "monster":
        if requested_attribute in attributes:
            selected_attribute = requested_attribute
            cards = cards.filter(attribute__iexact=selected_attribute)
        if requested_race in monster_types:
            selected_race = requested_race
            cards = cards.filter(race__iexact=selected_race)
        frame_map = {
            value: raw_frames
            for value, _, raw_frames in MONSTER_FRAME_GROUPS
        }
        if requested_frame in frame_map and requested_frame in {
            value for value, _ in monster_frames
        }:
            selected_frame = requested_frame
            cards = cards.filter(frame_type__in=frame_map[selected_frame])
    elif selected_type == "spell" and requested_race in spell_types:
        selected_race = requested_race
        cards = cards.filter(race__iexact=selected_race)
    elif selected_type == "trap" and requested_race in trap_types:
        selected_race = requested_race
        cards = cards.filter(race__iexact=selected_race)

    card_ordering = (
        ("search_rank", "search_name_length", "name", "pk")
        if query else ("name", "pk")
    )
    valid_filters = []
    if query:
        valid_filters.append(("q", query))
    if requested_type:
        valid_filters.append(("type", requested_type))
    if selected_attribute:
        valid_filters.append(("attribute", selected_attribute))
    if selected_race:
        valid_filters.append(("race", selected_race))
    if selected_frame:
        valid_filters.append(("frame", selected_frame))

    page_obj = paginate_queryset(
        request,
        cards.order_by(*card_ordering),
        page_size=30,
    )
    pagination_query = urlencode(valid_filters)
    if pagination_query:
        pagination_query += "&"
    archive_filters = list(valid_filters)
    if page_obj.number > 1:
        archive_filters.append(("page", page_obj.number))
    archive_query = urlencode(archive_filters)
    archive_url = reverse("cards_page:list")
    archive_return_url = f"{archive_url}?{archive_query}" if archive_query else archive_url

    return render(request, "cards/card_list.html", {
        "page_obj": page_obj,
        "archive_return_url": archive_return_url,
        "pagination_query": pagination_query,
        "query": query,
        "selected_attribute": selected_attribute,
        "selected_type": selected_type,
        "selected_race": selected_race,
        "selected_frame": selected_frame,
        "attributes": attributes,
        "monster_types": monster_types,
        "monster_frames": monster_frames,
        "spell_types": spell_types,
        "trap_types": trap_types,
        "has_active_filters": bool(valid_filters),
        "total_cards": facets["total_cards"],
    })


@ensure_csrf_cookie
def card_detail_page(request, card_id):
    card = get_object_or_404(Card, card_id=card_id)
    is_monster = "monster" in card.card_type.lower() or card.card_type.lower() == "token"
    archive_url = reverse("cards_page:list")
    return_url = request.GET.get("return", "")
    allowed_return_routes = {
        ("cards_page", "list"): "Back to archive",
        ("banlists_page", "list"): "Back to ban list",
        ("decks_page", "builder"): "Back to deck",
        ("decks_page", "create"): "Back to deck builder",
    }
    try:
        parsed_return_url = urlsplit(return_url)
        if parsed_return_url.scheme or parsed_return_url.netloc or not parsed_return_url.path.startswith("/"):
            raise Resolver404
        return_match = resolve(parsed_return_url.path)
        back_label = allowed_return_routes[
            (return_match.namespace, return_match.url_name)
        ]
    except (KeyError, Resolver404):
        return_url = archive_url
        back_label = "Back to archive"
    related_cards = Card.objects.exclude(pk=card.pk)
    if card.archetype:
        related_cards = related_cards.filter(archetype=card.archetype)
    else:
        related_cards = related_cards.filter(card_type=card.card_type)
    return render(request, "cards/card_detail.html", {
        "card": card,
        "show_monster_stats": is_monster,
        "atk_display": card.atk if card.atk is not None and card.atk >= 0 else "?",
        "defense_display": card.defense if card.defense is not None and card.defense >= 0 else "?",
        "level_label": "Rank" if card.frame_type.lower() == "xyz" else "Level",
        "level_stars": range(card.level or 0),
        "related_cards": related_cards.order_by("name")[:4],
        "archive_return_url": return_url,
        "back_label": back_label,
    })


def home(request):
    return render(request, "home.html")
