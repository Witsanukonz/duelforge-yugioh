from django.urls import path

from .views import card_catalog_page, card_detail_page


app_name = "cards_page"

urlpatterns = [
    path("", card_catalog_page, name="list"),
    path("<int:card_id>/", card_detail_page, name="detail"),
]
