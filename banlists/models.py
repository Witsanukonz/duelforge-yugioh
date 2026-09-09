from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator

from cards.models import Card


class BanList(models.Model):
    FORMAT_CHOICES = [
        ("TCG", "TCG"),
        ("OCG", "OCG"),
    ]

    name = models.CharField(max_length=255)

    format = models.CharField(
        max_length=10,
        choices=FORMAT_CHOICES,
    )

    effective_date = models.DateField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    source_url = models.URLField(
        max_length=500,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"{self.name} ({self.format})"


class BanListEntry(models.Model):
    STATUS_CHOICES = [
        ("FORBIDDEN", "Forbidden"),
        ("LIMITED", "Limited"),
        ("SEMI_LIMITED", "Semi-Limited"),
    ]

    ban_list = models.ForeignKey(
        BanList,
        on_delete=models.CASCADE,
        related_name="entries",
    )

    card = models.ForeignKey(
        Card,
        on_delete=models.CASCADE,
        related_name="banlist_entries",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
    )

    max_copies = models.PositiveSmallIntegerField(
        default=3,
        validators=[MaxValueValidator(3)],
    )

    note = models.TextField(blank=True)

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["ban_list", "card"],
                name="unique_card_per_banlist",
            ),
            models.CheckConstraint(
                condition=models.Q(max_copies__gte=0, max_copies__lte=3),
                name="banlist_max_copies_between_0_and_3",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="FORBIDDEN", max_copies=0)
                    | models.Q(status="LIMITED", max_copies=1)
                    | models.Q(status="SEMI_LIMITED", max_copies=2)
                ),
                name="banlist_status_matches_copy_limit",
            ),
        ]

    def __str__(self):
        return f"{self.card.name} - {self.ban_list.format} - {self.status}"

    def clean(self):
        super().clean()
        expected_limits = {
            "FORBIDDEN": 0,
            "LIMITED": 1,
            "SEMI_LIMITED": 2,
        }
        expected = expected_limits.get(self.status)
        if expected is not None and self.max_copies != expected:
            raise ValidationError({
                "max_copies": f"{self.get_status_display()} cards must allow {expected} copies."
            })
