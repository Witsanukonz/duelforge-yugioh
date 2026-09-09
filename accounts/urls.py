from django.contrib.auth import views as auth_views
from django.urls import path
from django.urls import reverse_lazy

from .views import (
    admin_dashboard_view,
    home_view,
    password_reset_confirm_view,
    password_reset_view,
    signup_view,
)


urlpatterns = [
    path(
        'dashboard/',
        admin_dashboard_view,
        name='admin_dashboard'
    ),

    path(
        '',
        home_view,
        name='home'
    ),

    path(
        'signup/',
        signup_view,
        name='signup'
    ),

    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='registration/login.html'
        ),
        name='login'
    ),

    path(
        'logout/',
        auth_views.LogoutView.as_view(),
        name='logout'
    ),

    path(
        'password/change/',
        auth_views.PasswordChangeView.as_view(
            template_name='registration/password_change_form.html',
            success_url=reverse_lazy('password_change_done'),
        ),
        name='password_change'
    ),
    path(
        'password/change/done/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='registration/password_change_done.html',
        ),
        name='password_change_done'
    ),
    path(
        'password/reset/',
        password_reset_view,
        name='password_reset'
    ),
    path(
        'password/reset/new/',
        password_reset_confirm_view,
        name='password_reset_confirm'
    ),
    path(
        'password/reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html',
        ),
        name='password_reset_complete'
    ),
]
