from django.urls import path

from .views import collection_detail, collection_list


app_name = "collects"

urlpatterns = [
    path("", collection_list, name="list"),
    path("<int:item_id>/", collection_detail, name="detail"),
]
