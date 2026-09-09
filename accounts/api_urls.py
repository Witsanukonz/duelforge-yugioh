from django.urls import path

from .views import (
    api_login_view,
    api_logout_view,
    api_me_view,
    api_signup_view,
    csrf_view,
)


app_name = "account_api"

urlpatterns = [
    path("csrf/", csrf_view, name="csrf"),
    path("signup/", api_signup_view, name="signup"),
    path("login/", api_login_view, name="login"),
    path("logout/", api_logout_view, name="logout"),
    path("me/", api_me_view, name="me"),
]
