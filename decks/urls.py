from django.urls import path

from .views import (
    deck_card_detail,
    deck_cards,
    deck_collection,
    deck_detail,
    deck_validation,
)


app_name = "decks"

urlpatterns = [
    path("", deck_collection, name="collection"),
    path("<int:deck_id>/validate/", deck_validation, name="validate"),
    path("<int:deck_id>/cards/", deck_cards, name="cards"),
    path("<int:deck_id>/cards/<int:entry_id>/", deck_card_detail, name="card-detail"),
    path("<int:deck_id>/", deck_detail, name="detail"),
]
