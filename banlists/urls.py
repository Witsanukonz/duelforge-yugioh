from django.urls import path

from .views import banlist_detail, banlist_list, current_banlist


app_name = "banlists"

urlpatterns = [
    path("", banlist_list, name="list"),
    path("current/", current_banlist, name="current"),
    path("<int:banlist_id>/", banlist_detail, name="detail"),
]
