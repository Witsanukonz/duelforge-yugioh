import json
from dataclasses import dataclass, field
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import transaction

from cards.models import Card

from .models import Deck, DeckCard
from .ydk import YDKParseError, parse_ydk_file


SAMPLE_OWNER_USERNAME = "DUELFORGE"
DEFAULT_SAMPLE_DIRECTORY = Path(__file__).resolve().parent / "data" / "sample_decks"


class SampleDeckImportError(ValueError):
    pass


@dataclass
class SampleDeckImportResult:
    source: str
    name: str
    status: str
    totals: dict[str, int] = field(default_factory=dict)
    missing_card_ids: list[int] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


def load_sample_metadata(directory):
    metadata_path = Path(directory) / "metadata.json"
    if not metadata_path.exists():
        return {}
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SampleDeckImportError(
            f"Could not read sample deck metadata at {metadata_path}: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise SampleDeckImportError("Sample deck metadata must be a JSON object.")
    return payload


def get_sample_deck_owner():
    user_model = get_user_model()
    owner, created = user_model.objects.get_or_create(
        username=SAMPLE_OWNER_USERNAME,
        defaults={"is_staff": False, "is_superuser": False},
    )
    if created:
        owner.set_unusable_password()
        owner.save(update_fields=["password"])
    return owner


def sample_source_id(path, directory):
    return Path(path).resolve().relative_to(Path(directory).resolve()).as_posix().lower()


def sample_metadata_for(path, metadata):
    stem = Path(path).stem
    value = metadata.get(stem, metadata.get(stem.lower(), {}))
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SampleDeckImportError(f"Metadata for {stem!r} must be a JSON object.")
    return value


def default_deck_name(path):
    return Path(path).stem.replace("-", " ").replace("_", " ").strip().title()


def validate_parsed_deck(parsed, cards_by_ygo_id):
    errors = []
    for section, card_counts in parsed.sections.items():
        for ygo_id, quantity in card_counts.items():
            if quantity > 3:
                errors.append(
                    f"Card ID {ygo_id} appears {quantity} times in {section}; "
                    "the current DeckCard storage supports at most 3 per section."
                )
    return errors


def desired_card_rows(parsed, cards_by_ygo_id):
    return sorted(
        (
            section,
            ygo_id,
            quantity,
            cards_by_ygo_id[ygo_id],
        )
        for section, card_counts in parsed.sections.items()
        for ygo_id, quantity in card_counts.items()
        if ygo_id in cards_by_ygo_id
    )


def import_sample_deck(path, *, directory, metadata=None, allow_missing=False):
    path = Path(path)
    directory = Path(directory)
    metadata = metadata or {}
    source = sample_source_id(path, directory)
    deck_metadata = sample_metadata_for(path, metadata)
    name = str(deck_metadata.get("name") or default_deck_name(path)).strip()

    try:
        parsed = parse_ydk_file(path)
    except YDKParseError as error:
        return SampleDeckImportResult(
            source=source,
            name=name,
            status="SKIPPED",
            messages=list(error.errors),
        )

    card_ids = parsed.unique_card_ids
    cards_by_ygo_id = Card.objects.in_bulk(card_ids, field_name="card_id")
    missing = sorted(card_ids - cards_by_ygo_id.keys())
    errors = validate_parsed_deck(parsed, cards_by_ygo_id)
    if missing and not allow_missing:
        errors.append("Missing card IDs prevent a strict import.")
    if errors:
        return SampleDeckImportResult(
            source=source,
            name=name,
            status="SKIPPED",
            totals=parsed.totals,
            missing_card_ids=missing,
            messages=errors,
        )

    deck_format = str(deck_metadata.get("format", "TCG")).upper()
    if deck_format not in {choice[0] for choice in Deck.FORMAT_CHOICES}:
        return SampleDeckImportResult(
            source=source,
            name=name,
            status="SKIPPED",
            totals=parsed.totals,
            missing_card_ids=missing,
            messages=["format must be TCG or OCG."],
        )

    rows = desired_card_rows(parsed, cards_by_ygo_id)
    owner = get_sample_deck_owner()
    desired_fields = {
        "owner": owner,
        "name": name,
        "description": str(deck_metadata.get("description", "")).strip(),
        "deck_type": str(deck_metadata.get("deck_type") or "Sample Deck").strip(),
        "format": deck_format,
        "ban_list": None,
        "is_public": True,
        "is_sample": True,
        "sample_archetype": str(deck_metadata.get("archetype", "")).strip(),
    }

    with transaction.atomic():
        deck = Deck.objects.select_for_update().filter(sample_source=source).first()
        if deck is None:
            deck = Deck(sample_source=source, **desired_fields)
            deck.full_clean()
            deck.save()
            status = "CREATED"
        else:
            current_rows = sorted(
                deck.deck_cards.values_list("section", "card__card_id", "quantity")
            )
            target_rows = [(section, ygo_id, quantity) for section, ygo_id, quantity, _ in rows]
            fields_changed = any(
                getattr(deck, field_name) != value
                for field_name, value in desired_fields.items()
            )
            if not fields_changed and current_rows == target_rows:
                return SampleDeckImportResult(
                    source=source,
                    name=name,
                    status="UNCHANGED",
                    totals=parsed.totals,
                    missing_card_ids=missing,
                )
            for field_name, value in desired_fields.items():
                setattr(deck, field_name, value)
            deck.full_clean()
            deck.save()
            deck.deck_cards.all().delete()
            status = "UPDATED"

        DeckCard.objects.bulk_create([
            DeckCard(deck=deck, card=card, section=section, quantity=quantity)
            for section, _, quantity, card in rows
        ])

    return SampleDeckImportResult(
        source=source,
        name=name,
        status=status,
        totals=parsed.totals,
        missing_card_ids=missing,
    )
