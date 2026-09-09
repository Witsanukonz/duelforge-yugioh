from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum

from cards.models import Card
from banlists.models import BanList


class Deck(models.Model):
    FORMAT_CHOICES = [
        ("TCG", "TCG"),
        ("OCG", "OCG"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="decks",
    )

    name = models.CharField(max_length=255)

    description = models.TextField(blank=True)

    deck_type = models.CharField(
        max_length=100,
        blank=True,
    )

    format = models.CharField(
        max_length=10,
        choices=FORMAT_CHOICES,
        default="TCG",
    )

    ban_list = models.ForeignKey(
        BanList,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decks",
    )

    is_public = models.BooleanField(
        default=False,
    )

    is_sample = models.BooleanField(
        default=False,
        db_index=True,
        help_text="System-owned deck imported from a local sample source.",
    )

    sample_source = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        help_text="Stable relative .ydk source path used for idempotent imports.",
    )

    sample_archetype = models.CharField(
        max_length=255,
        blank=True,
    )

    cover_image = models.ImageField(
        upload_to="deck_covers/",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.name

    @property
    def listing_cover_url(self):
        if self.cover_image:
            if getattr(settings, "SERVE_DECK_COVERS_AS_STATIC", False):
                filename = self.cover_image.name.removeprefix("deck_covers/")
                return f"{settings.STATIC_URL}deck_covers/{filename}"
            return self.cover_image.url
        card_id = getattr(self, "cover_card_ygo_id", None)
        if card_id:
            card = Card.objects.filter(card_id=card_id).only(
                "image_url", "image_url_small"
            ).first()
            if card:
                return card.local_image_url
            return f"{settings.MEDIA_URL}cards/{card_id}.jpg"
        return ""

    def clean(self):
        super().clean()
        if self.is_sample and not self.sample_source:
            raise ValidationError({
                "sample_source": "Sample decks require a stable local source identifier."
            })
        if self.ban_list_id and self.ban_list.format != self.format:
            raise ValidationError({
                "ban_list": "Ban list format must match the deck format."
            })


class DeckCard(models.Model):
    SECTION_LIMITS = {
        "MAIN": 60,
        "EXTRA": 15,
        "SIDE": 15,
    }

    SECTION_CHOICES = [
        ("MAIN", "Main Deck"),
        ("EXTRA", "Extra Deck"),
        ("SIDE", "Side Deck"),
    ]

    deck = models.ForeignKey(
        Deck,
        on_delete=models.CASCADE,
        related_name="deck_cards",
    )

    card = models.ForeignKey(
        Card,
        on_delete=models.CASCADE,
        related_name="deck_cards",
    )

    quantity = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(3)],
    )

    section = models.CharField(
        max_length=20,
        choices=SECTION_CHOICES,
        default="MAIN",
    )

    note = models.TextField(blank=True)

    added_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["deck", "card", "section"],
                name="unique_card_per_deck_section",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1, quantity__lte=3),
                name="deck_card_quantity_between_1_and_3",
            ),
        ]

    def __str__(self):
        return f"{self.deck.name} - {self.card.name} x{self.quantity}"

    def clean(self):
        super().clean()
        if not self.deck_id or not self.card_id or not self.quantity:
            return

        if self.card.is_extra_deck_card and self.section != "EXTRA":
            raise ValidationError({
                "section": "Fusion, Synchro, Xyz, and Link cards can only be added to the Extra Deck."
            })
        if not self.card.is_extra_deck_card and self.section == "EXTRA":
            raise ValidationError({
                "section": "Only Fusion, Synchro, Xyz, and Link cards can be added to the Extra Deck."
            })

        other_entries = DeckCard.objects.filter(deck_id=self.deck_id)
        if self.pk:
            other_entries = other_entries.exclude(pk=self.pk)

        copies = (
            other_entries.filter(card_id=self.card_id)
            .aggregate(total=Sum("quantity"))["total"]
            or 0
        )
        limit = 3
        if self.deck.ban_list_id:
            banlist_entry = self.deck.ban_list.entries.filter(
                card_id=self.card_id
            ).only("max_copies").first()
            if banlist_entry:
                limit = banlist_entry.max_copies
        if copies + self.quantity > limit:
            raise ValidationError({
                "quantity": f"This card is limited to {limit} copies in this deck."
            })

        section_total = (
            other_entries.filter(section=self.section)
            .aggregate(total=Sum("quantity"))["total"]
            or 0
        )
        section_limit = self.SECTION_LIMITS.get(self.section)
        if section_limit is not None and section_total + self.quantity > section_limit:
            raise ValidationError({
                "section": f"{self.get_section_display()} cannot exceed {section_limit} cards."
            })
