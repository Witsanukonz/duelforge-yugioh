from django.contrib import admin

from .models import Deck, DeckCard


@admin.register(Deck)
class DeckAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner",
        "format",
        "ban_list",
        "is_sample",
        "is_public",
        "updated_at",
    )

    list_filter = (
        "format",
        "is_sample",
        "is_public",
    )

    search_fields = (
        "name",
        "owner__username",
    )


@admin.register(DeckCard)
class DeckCardAdmin(admin.ModelAdmin):
    list_display = (
        "deck",
        "card",
        "quantity",
        "section",
    )

    list_filter = (
        "section",
    )

    search_fields = (
        "deck__name",
        "card__name",
    )
