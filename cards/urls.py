from django.urls import path

from .views import card_detail, card_list, card_translation


app_name = "cards"

urlpatterns = [
    path("", card_list, name="list"),
    path("<int:card_id>/translation/", card_translation, name="translation"),
    path("<int:card_id>/", card_detail, name="detail"),
]
