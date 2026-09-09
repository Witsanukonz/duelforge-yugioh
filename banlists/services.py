import json
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from cards.models import Card

from .models import BanList, BanListEntry


STATUS_LIMITS = {
    "FORBIDDEN": 0,
    "LIMITED": 1,
    "SEMI_LIMITED": 2,
}
ACTIVE_BANLIST_CACHE_KEY = "banlists:active:{format}:v1"
BANLIST_STATUS_COUNTS_CACHE_KEY = "banlists:status-counts:{banlist_id}:v1"


class BanListImportError(ValueError):
    pass


def get_active_banlist(banlist_format):
    normalized_format = str(banlist_format).upper()
    cache_key = ACTIVE_BANLIST_CACHE_KEY.format(format=normalized_format)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached or None

    banlist = (
        BanList.objects.filter(format=normalized_format, is_active=True)
        .filter(Q(effective_date__lte=timezone.localdate()) | Q(effective_date__isnull=True))
        .order_by("-effective_date", "-updated_at", "-pk")
        .first()
    )
    cache.set(
        cache_key,
        banlist or False,
        timeout=getattr(settings, "DATA_CACHE_TIMEOUT", 900),
    )
    return banlist


def get_banlist_status_counts(banlist):
    cache_key = BANLIST_STATUS_COUNTS_CACHE_KEY.format(banlist_id=banlist.pk)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    counts = banlist.entries.aggregate(
        total=Count("pk"),
        forbidden=Count("pk", filter=Q(status="FORBIDDEN")),
        limited=Count("pk", filter=Q(status="LIMITED")),
        semi_limited=Count("pk", filter=Q(status="SEMI_LIMITED")),
    )
    cache.set(
        cache_key,
        counts,
        timeout=getattr(settings, "DATA_CACHE_TIMEOUT", 900),
    )
    return counts


def invalidate_banlist_cache(*, banlist_id=None):
    cache.delete_many([
        ACTIVE_BANLIST_CACHE_KEY.format(format="TCG"),
        ACTIVE_BANLIST_CACHE_KEY.format(format="OCG"),
    ])
    if banlist_id is not None:
        cache.delete(
            BANLIST_STATUS_COUNTS_CACHE_KEY.format(banlist_id=banlist_id)
        )


def banlist_metadata(banlist):
    if banlist is None:
        return None
    return {
        "id": banlist.pk,
        "name": banlist.name,
        "format": banlist.format,
        "effective_date": (
            banlist.effective_date.isoformat() if banlist.effective_date else None
        ),
        "source_url": banlist.source_url,
    }


def load_banlist_payload(path):
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise BanListImportError(f"Could not read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise BanListImportError(
            f"Malformed JSON in {path} at line {error.lineno}, column {error.colno}."
        ) from error
    return validate_banlist_payload(payload)


def validate_banlist_payload(payload):
    if not isinstance(payload, dict):
        raise BanListImportError("Ban list JSON must contain an object at the top level.")

    banlist_format = str(payload.get("format", "")).upper()
    if banlist_format not in {"TCG", "OCG"}:
        raise BanListImportError("format must be TCG or OCG.")

    effective_date = parse_date(str(payload.get("effective_date", "")))
    if effective_date is None:
        raise BanListImportError("effective_date must use YYYY-MM-DD format.")

    cards = payload.get("cards")
    if not isinstance(cards, list):
        raise BanListImportError("cards must be a JSON array.")

    normalized_cards = []
    seen_card_ids = set()
    for index, item in enumerate(cards):
        if not isinstance(item, dict):
            raise BanListImportError(f"cards[{index}] must be an object.")
        card_id = item.get("card_id")
        if isinstance(card_id, bool) or not isinstance(card_id, int) or card_id <= 0:
            raise BanListImportError(f"cards[{index}].card_id must be a positive integer.")
        if card_id in seen_card_ids:
            raise BanListImportError(f"Duplicate card_id {card_id} in snapshot.")
        seen_card_ids.add(card_id)

        status = str(item.get("status", "")).upper().replace("-", "_")
        if status not in STATUS_LIMITS:
            raise BanListImportError(
                f"cards[{index}].status must be FORBIDDEN, LIMITED, or SEMI_LIMITED."
            )
        normalized_cards.append({
            "card_id": card_id,
            "status": status,
            "note": str(item.get("note", "")),
        })

    source = str(payload.get("source", "Konami Official Forbidden & Limited List"))
    source_url = str(payload.get("source_url", ""))
    name = str(payload.get("name") or f"{banlist_format} - {effective_date.isoformat()}")
    return {
        "format": banlist_format,
        "effective_date": effective_date,
        "name": name,
        "source": source,
        "source_url": source_url,
        "cards": normalized_cards,
    }


@transaction.atomic
def import_banlist_payload(payload):
    payload = validate_banlist_payload(payload)
    card_ids = [item["card_id"] for item in payload["cards"]]
    cards_by_public_id = Card.objects.in_bulk(card_ids, field_name="card_id")
    missing_card_ids = sorted(set(card_ids) - set(cards_by_public_id))

    target = (
        BanList.objects.select_for_update()
        .filter(format=payload["format"], effective_date=payload["effective_date"])
        .order_by("pk")
        .first()
    )
    created = target is None
    if target is None:
        target = BanList(format=payload["format"], effective_date=payload["effective_date"])
    target.name = payload["name"]
    target.is_active = True
    target.source_url = payload["source_url"]
    try:
        target.full_clean()
    except ValidationError as error:
        raise BanListImportError(str(error)) from error
    target.save()

    BanList.objects.filter(format=payload["format"]).exclude(pk=target.pk).update(
        is_active=False
    )
    target.entries.all().delete()
    entries = []
    for item in payload["cards"]:
        card = cards_by_public_id.get(item["card_id"])
        if card is None:
            continue
        entries.append(BanListEntry(
            ban_list=target,
            card=card,
            status=item["status"],
            max_copies=STATUS_LIMITS[item["status"]],
            note=item["note"],
        ))
    BanListEntry.objects.bulk_create(entries)

    status_counts = Counter(item["status"] for item in payload["cards"])
    return {
        "banlist": target,
        "created": created,
        "total_cards": len(payload["cards"]),
        "forbidden": status_counts["FORBIDDEN"],
        "limited": status_counts["LIMITED"],
        "semi_limited": status_counts["SEMI_LIMITED"],
        "matched_cards": len(entries),
        "missing_card_ids": missing_card_ids,
    }


def import_banlist_file(path):
    return import_banlist_payload(load_banlist_payload(path))
