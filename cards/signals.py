from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .catalog import invalidate_card_catalog_cache
from .models import Card


@receiver([post_save, post_delete], sender=Card)
def clear_card_catalog_cache(**kwargs):
    invalidate_card_catalog_cache()
