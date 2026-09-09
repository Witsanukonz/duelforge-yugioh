from django.urls import path

from .views import (
    copy_sample_deck_page,
    deck_builder_page,
    deck_create_page,
    deck_export_page,
    deck_list_page,
)


app_name = "decks_page"

urlpatterns = [
    path("", deck_list_page, name="list"),
    path("new/", deck_create_page, name="create"),
    path("<int:deck_id>/copy/", copy_sample_deck_page, name="copy-sample"),
    path("<int:deck_id>/export/", deck_export_page, name="export"),
    path("<int:deck_id>/", deck_builder_page, name="builder"),
]
