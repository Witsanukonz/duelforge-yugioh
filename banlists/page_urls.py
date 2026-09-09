from django.urls import path

from .views import banlist_page


app_name = "banlists_page"

urlpatterns = [
    path("", banlist_page, name="list"),
]
