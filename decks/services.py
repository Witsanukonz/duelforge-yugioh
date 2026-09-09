from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from banlists.services import banlist_metadata

from .models import Deck, DeckCard


SECTION_LIMITS = {
    "MAIN": 60,
    "EXTRA": 15,
    "SIDE": 15,
}


def card_copy_limit(deck, card):
    if not deck.ban_list_id:
        return 3
    entry = deck.ban_list.entries.filter(card=card).only("max_copies").first()
    return entry.max_copies if entry else 3


def section_counts(deck):
    counts = {section: 0 for section in SECTION_LIMITS}
    rows = (
        deck.deck_cards.values("section")
        .annotate(total=Sum("quantity"))
    )
    for row in rows:
        counts[row["section"]] = row["total"] or 0
    return counts


def validate_deck(deck):
    deck_entries = list(deck.deck_cards.select_related("card"))
    counts = {section: 0 for section in SECTION_LIMITS}
    totals_by_card = {}
    cards_by_id = {}
    for entry in deck_entries:
        counts[entry.section] += entry.quantity
        totals_by_card[entry.card_id] = totals_by_card.get(entry.card_id, 0) + entry.quantity
        cards_by_id[entry.card_id] = entry.card

    restriction_map = {}
    if deck.ban_list_id and totals_by_card:
        restriction_map = {
            entry.card_id: entry
            for entry in deck.ban_list.entries.filter(card_id__in=totals_by_card).only(
                "card_id", "status", "max_copies"
            )
        }
    issues = []

    if not 40 <= counts["MAIN"] <= 60:
        issues.append({
            "code": "main_deck_size",
            "type": "DECK_SIZE",
            "section": "MAIN",
            "used": counts["MAIN"],
            "allowed_min": 40,
            "allowed_max": 60,
            "message": "Main Deck must contain 40 to 60 cards.",
        })
    if counts["EXTRA"] > 15:
        issues.append({
            "code": "extra_deck_size",
            "type": "DECK_SIZE",
            "section": "EXTRA",
            "used": counts["EXTRA"],
            "allowed_max": 15,
            "message": "Extra Deck cannot contain more than 15 cards.",
        })
    if counts["SIDE"] > 15:
        issues.append({
            "code": "side_deck_size",
            "type": "DECK_SIZE",
            "section": "SIDE",
            "used": counts["SIDE"],
            "allowed_max": 15,
            "message": "Side Deck cannot contain more than 15 cards.",
        })
    if deck.ban_list_id and deck.ban_list.format != deck.format:
        issues.append({
            "code": "banlist_format",
            "type": "BANLIST_FORMAT",
            "message": "Ban list format does not match the deck format.",
        })

    for entry in deck_entries:
        if entry.card.is_extra_deck_card and entry.section != "EXTRA":
            issues.append({
                "code": "invalid_card_section",
                "type": "PLACEMENT",
                "card_id": entry.card.card_id,
                "card_name": entry.card.name,
                "section": entry.section,
                "message": f"{entry.card.name} can only be placed in the Extra Deck.",
            })
        elif not entry.card.is_extra_deck_card and entry.section == "EXTRA":
            issues.append({
                "code": "invalid_card_section",
                "type": "PLACEMENT",
                "card_id": entry.card.card_id,
                "card_name": entry.card.name,
                "section": entry.section,
                "message": f"{entry.card.name} is not an Extra Deck card.",
            })

    for card_pk, total in totals_by_card.items():
        card = cards_by_id[card_pk]
        restriction = restriction_map.get(card_pk)
        limit = restriction.max_copies if restriction else 3
        if total > limit:
            status = restriction.status if restriction else "UNLIMITED"
            issues.append({
                "code": "copy_limit",
                "type": "BANLIST" if restriction else "COPY_LIMIT",
                "card_id": card.card_id,
                "card_name": card.name,
                "status": status,
                "used": total,
                "allowed": limit,
                "message": f"{card.name}: {total} used, maximum {limit} ({status.replace('_', '-').title()}).",
            })

    return {
        "is_valid": not issues,
        "is_legal": not issues,
        "format": deck.format,
        "banlist": banlist_metadata(deck.ban_list if deck.ban_list_id else None),
        "counts": counts,
        "section_counts": {key.lower(): value for key, value in counts.items()},
        "issues": issues,
        "violations": issues,
    }


@transaction.atomic
def copy_sample_deck(*, sample_deck, owner):
    sample_deck = (
        Deck.objects.select_for_update()
        .select_related("ban_list")
        .get(pk=sample_deck.pk, is_sample=True, is_public=True)
    )
    base_name = f"{sample_deck.name} - Copy"
    name = base_name
    suffix = 2
    while Deck.objects.filter(owner=owner, name=name).exists():
        name = f"{base_name} ({suffix})"
        suffix += 1

    copy = Deck.objects.create(
        owner=owner,
        name=name,
        description=sample_deck.description,
        deck_type=sample_deck.sample_archetype or sample_deck.deck_type,
        format=sample_deck.format,
        ban_list=sample_deck.ban_list,
        is_public=False,
        is_sample=False,
    )
    source_cards = list(sample_deck.deck_cards.select_related("card"))
    DeckCard.objects.bulk_create([
        DeckCard(
            deck=copy,
            card=entry.card,
            quantity=entry.quantity,
            section=entry.section,
            note=entry.note,
        )
        for entry in source_cards
    ])
    return copy


@transaction.atomic
def save_deck_card(*, deck, card, quantity, section, note="", entry=None):
    deck = Deck.objects.select_for_update().select_related("ban_list").get(pk=deck.pk)

    if section not in SECTION_LIMITS:
        raise ValidationError({"section": "Invalid deck section."})
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise ValidationError({"quantity": "Quantity must be an integer."})
    if not 1 <= quantity <= 3:
        raise ValidationError({"quantity": "Quantity must be between 1 and 3."})

    created = entry is None
    if entry is None:
        entry = DeckCard.objects.select_for_update().filter(
            deck=deck, card=card, section=section
        ).first()
        if entry is not None:
            created = False
        else:
            entry = DeckCard(deck=deck, card=card, section=section)
    else:
        entry = DeckCard.objects.select_for_update().get(pk=entry.pk, deck=deck)

    excluded_entry = DeckCard.objects.filter(deck=deck)
    if entry.pk:
        excluded_entry = excluded_entry.exclude(pk=entry.pk)

    duplicate = excluded_entry.filter(card=card, section=section).exists()
    if duplicate:
        raise ValidationError({
            "section": "This card already exists in the requested section."
        })

    other_copies = (
        excluded_entry.filter(card=card).aggregate(total=Sum("quantity"))["total"]
        or 0
    )
    limit = card_copy_limit(deck, card)
    if other_copies + quantity > limit:
        raise ValidationError({
            "quantity": f"This card is limited to {limit} copies in this deck."
        })

    other_section_cards = (
        excluded_entry.filter(section=section).aggregate(total=Sum("quantity"))["total"]
        or 0
    )
    if other_section_cards + quantity > SECTION_LIMITS[section]:
        raise ValidationError({
            "section": f"{section.title()} Deck cannot exceed {SECTION_LIMITS[section]} cards."
        })

    entry.deck = deck
    entry.card = card
    entry.quantity = quantity
    entry.section = section
    entry.note = note
    entry.full_clean()
    entry.save()
    return entry, created


@transaction.atomic
def move_deck_card_copy(*, deck, entry, section):
    deck = Deck.objects.select_for_update().select_related("ban_list").get(pk=deck.pk)
    entry = (
        DeckCard.objects.select_for_update()
        .select_related("card")
        .get(pk=entry.pk, deck=deck)
    )
    if section == entry.section:
        return entry

    card = entry.card
    note = entry.note
    if entry.quantity == 1:
        entry.delete()
    else:
        entry.quantity -= 1
        entry.full_clean()
        entry.save(update_fields=["quantity"])

    destination = DeckCard.objects.select_for_update().filter(
        deck=deck,
        card=card,
        section=section,
    ).first()
    quantity = destination.quantity + 1 if destination else 1
    moved, _ = save_deck_card(
        deck=deck,
        card=card,
        quantity=quantity,
        section=section,
        note=note,
        entry=destination,
    )
    return moved
