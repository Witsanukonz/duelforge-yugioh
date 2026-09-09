from django.contrib import admin
from .models import Card


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "card_type",
        "attribute",
        "race",
        "atk",
        "defense",
        "level",
    )

    search_fields = (
        "name",
        "archetype",
        "description",
        "description_th",
    )

    list_filter = (
        "card_type",
        "attribute",
        "race",
    )

    ordering = ("name",)
