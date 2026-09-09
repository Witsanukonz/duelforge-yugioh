from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from cards.models import Card


class Collection(models.Model):
    CONDITION_CHOICES = [
        ("NM", "Near Mint"),
        ("LP", "Lightly Played"),
        ("MP", "Moderately Played"),
        ("HP", "Heavily Played"),
        ("DMG", "Damaged"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="card_collection",
    )

    card = models.ForeignKey(
        Card,
        on_delete=models.CASCADE,
        related_name="collections",
    )

    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )

    condition = models.CharField(
        max_length=30,
        choices=CONDITION_CHOICES,
        blank=True,
    )

    is_favorite = models.BooleanField(
        default=False,
    )

    note = models.TextField(blank=True)

    added_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "card"],
                name="unique_card_per_user_collection",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name="collection_quantity_at_least_1",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.card.name}"
