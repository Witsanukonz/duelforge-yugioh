from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Max, Q

from .models import Card


CARD_CATEGORIES = {"monster", "spell", "trap"}
CARD_CATALOG_FACETS_CACHE_KEY = "cards:catalog-facets:v1"
MONSTER_FRAME_GROUPS = (
    ("normal", "Normal", ("normal", "normal_pendulum")),
    ("effect", "Effect", ("effect", "effect_pendulum")),
    ("ritual", "Ritual", ("ritual", "ritual_pendulum")),
    ("fusion", "Fusion", ("fusion", "fusion_pendulum")),
    ("synchro", "Synchro", ("synchro", "synchro_pendulum")),
    ("xyz", "Xyz", ("xyz", "xyz_pendulum")),
    (
        "pendulum",
        "Pendulum",
        (
            "normal_pendulum",
            "effect_pendulum",
            "ritual_pendulum",
            "fusion_pendulum",
            "synchro_pendulum",
            "xyz_pendulum",
        ),
    ),
    ("link", "Link", ("link",)),
)


def monster_card_filter():
    return Q(card_type__icontains="Monster") | Q(card_type="Token")


def card_category_from_value(value):
    normalized = value.strip().lower()
    if normalized in CARD_CATEGORIES:
        return normalized
    if "monster" in normalized or normalized == "token":
        return "monster"
    if normalized == "spell card":
        return "spell"
    if normalized == "trap card":
        return "trap"
    return ""


def distinct_card_values(cards, field):
    return list(
        cards.exclude(**{field: ""})
        .values_list(field, flat=True)
        .order_by(field)
        .distinct()
    )


def get_card_catalog_facets():
    revision = Card.objects.aggregate(
        total=Count("pk"),
        latest_update=Max("updated_at"),
    )
    revision_key = (
        revision["total"],
        revision["latest_update"].isoformat() if revision["latest_update"] else None,
    )
    cached = cache.get(CARD_CATALOG_FACETS_CACHE_KEY)
    if cached is not None and cached.get("_revision") == revision_key:
        return cached

    monster_cards = Card.objects.filter(monster_card_filter())
    available_frames = set(distinct_card_values(monster_cards, "frame_type"))
    facets = {
        "attributes": distinct_card_values(monster_cards, "attribute"),
        "monster_types": distinct_card_values(monster_cards, "race"),
        "spell_types": distinct_card_values(
            Card.objects.filter(card_type__iexact="Spell Card"), "race"
        ),
        "trap_types": distinct_card_values(
            Card.objects.filter(card_type__iexact="Trap Card"), "race"
        ),
        "monster_frames": [
            (value, label)
            for value, label, raw_frames in MONSTER_FRAME_GROUPS
            if available_frames.intersection(raw_frames)
        ],
        "total_cards": revision["total"],
        "_revision": revision_key,
    }
    cache.set(
        CARD_CATALOG_FACETS_CACHE_KEY,
        facets,
        timeout=getattr(settings, "DATA_CACHE_TIMEOUT", 900),
    )
    return facets


def invalidate_card_catalog_cache():
    cache.delete(CARD_CATALOG_FACETS_CACHE_KEY)
