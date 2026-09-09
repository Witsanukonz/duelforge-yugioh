from django.contrib import admin

from .models import Collection


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "card",
        "quantity",
        "condition",
        "is_favorite",
    )

    list_filter = (
        "condition",
        "is_favorite",
    )

    search_fields = (
        "user__username",
        "card__name",
    )