from django.urls import path

from .views import collection_page


app_name = "collects_page"

urlpatterns = [
    path("", collection_page, name="list"),
]
