from django.contrib import admin

from .models import BanList, BanListEntry


@admin.register(BanList)
class BanListAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "format",
        "effective_date",
        "is_active",
    )

    list_filter = (
        "format",
        "is_active",
    )

    search_fields = (
        "name",
    )


@admin.register(BanListEntry)
class BanListEntryAdmin(admin.ModelAdmin):
    list_display = (
        "card",
        "ban_list",
        "status",
        "max_copies",
    )

    list_filter = (
        "status",
        "ban_list__format",
    )

    search_fields = (
        "card__name",
        "ban_list__name",
    )