from django.conf import settings
from django.db import models


class Card(models.Model):
    EXTRA_DECK_FRAME_PREFIXES = frozenset({"fusion", "synchro", "xyz", "link"})

    card_id = models.BigIntegerField(unique=True)

    name = models.CharField(
        max_length=255
    )

    card_type = models.CharField(
        max_length=100
    )

    frame_type = models.CharField(
        max_length=50,
        blank=True
    )

    description = models.TextField(
        blank=True
    )

    description_th = models.TextField(
        blank=True,
        help_text="Cached automatic Thai translation of the card text.",
    )

    race = models.CharField(
        max_length=100,
        blank=True
    )

    attribute = models.CharField(
        max_length=50,
        blank=True
    )

    archetype = models.CharField(
        max_length=255,
        blank=True
    )

    atk = models.IntegerField(
        null=True,
        blank=True
    )

    defense = models.IntegerField(
        null=True,
        blank=True
    )

    level = models.IntegerField(
        null=True,
        blank=True
    )

    image_url = models.URLField(
        max_length=500,
        blank=True
    )

    image_url_small = models.URLField(
        max_length=500,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.name

    @property
    def is_extra_deck_card(self):
        frame_prefix = self.frame_type.strip().lower().split("_", 1)[0]
        return frame_prefix in self.EXTRA_DECK_FRAME_PREFIXES

    @property
    def local_image_url(self):
        if getattr(settings, "USE_REMOTE_CARD_IMAGES", False):
            return self.image_url or self.image_url_small
        return f"{settings.MEDIA_URL}cards/{self.card_id}.jpg"
