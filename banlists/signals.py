from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import BanList, BanListEntry
from .services import invalidate_banlist_cache


@receiver([post_save, post_delete], sender=BanList)
def clear_banlist_cache_for_list(instance, **kwargs):
    invalidate_banlist_cache(banlist_id=instance.pk)


@receiver([post_save, post_delete], sender=BanListEntry)
def clear_banlist_cache_for_entry(instance, **kwargs):
    invalidate_banlist_cache(banlist_id=instance.ban_list_id)
