from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.forms import SetPasswordForm
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from banlists.services import get_active_banlist
from cards.models import Card
from collects.models import Collection
from config.api import api_error, api_login_required, parse_json
from decks.models import Deck

from .forms import AccountSignupForm, DemoPasswordResetRequestForm
from .featured_monsters import FEATURED_MONSTERS


PASSWORD_RESET_SESSION_KEY = "demo_password_reset_user_id"


def home_view(request):
    card_archive_url = reverse("cards_page:list")
    featured_monsters = [
        {
            **monster,
            "imageUrl": static(monster["image"]),
            "exploreUrl": (
                f"{card_archive_url}?{urlencode({'q': monster['searchQuery']})}"
            ),
        }
        for monster in FEATURED_MONSTERS
    ]
    return render(request, "home.html", {
        "featured_monsters": featured_monsters,
    })


def about_view(request):
    return render(request, "accounts/about.html")


@staff_member_required(login_url="login")
def admin_dashboard_view(request):
    user_model = get_user_model()
    thirty_days_ago = timezone.now() - timedelta(days=30)
    deck_totals = Deck.objects.aggregate(
        total=Count("pk"),
        public=Count("pk", filter=Q(is_public=True)),
        without_banlist=Count("pk", filter=Q(ban_list__isnull=True)),
    )
    collection_totals = Collection.objects.aggregate(
        unique_cards=Count("pk"),
        total_copies=Sum("quantity"),
    )
    active_banlists = [
        banlist
        for banlist in (get_active_banlist("TCG"), get_active_banlist("OCG"))
        if banlist is not None
    ]
    for banlist in active_banlists:
        banlist.entry_count = banlist.entries.count()

    return render(request, "accounts/admin_dashboard.html", {
        "stats": {
            "users": user_model.objects.count(),
            "new_users": user_model.objects.filter(date_joined__gte=thirty_days_ago).count(),
            "cards": Card.objects.count(),
            "decks": deck_totals["total"],
            "public_decks": deck_totals["public"],
            "collection_copies": collection_totals["total_copies"] or 0,
        },
        "decks_without_banlist": deck_totals["without_banlist"],
        "unique_collection_cards": collection_totals["unique_cards"],
        "active_banlists": active_banlists,
        "recent_decks": Deck.objects.select_related("owner", "ban_list").order_by(
            "-updated_at", "-pk"
        )[:8],
        "recent_users": user_model.objects.order_by("-date_joined", "-pk")[:6],
    })


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = AccountSignupForm(request.POST)

        if form.is_valid():
            user = form.save()

            login(request, user)

            return redirect('home')

    else:
        form = AccountSignupForm()

    return render(
        request,
        'registration/signup.html',
        {
            'form': form
        }
    )


def password_reset_view(request):
    if request.method == "POST":
        form = DemoPasswordResetRequestForm(request.POST)
        if form.is_valid():
            request.session[PASSWORD_RESET_SESSION_KEY] = form.user.pk
            return redirect("password_reset_confirm")
    else:
        form = DemoPasswordResetRequestForm()

    return render(request, "registration/password_reset_form.html", {"form": form})


def password_reset_confirm_view(request):
    user_id = request.session.get(PASSWORD_RESET_SESSION_KEY)
    if not user_id:
        return redirect("password_reset")

    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        request.session.pop(PASSWORD_RESET_SESSION_KEY, None)
        return redirect("password_reset")

    if request.method == "POST":
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            request.session.pop(PASSWORD_RESET_SESSION_KEY, None)
            return redirect("password_reset_complete")
    else:
        form = SetPasswordForm(user)

    return render(
        request,
        "registration/password_reset_confirm.html",
        {"form": form, "reset_email": user.email},
    )


def serialize_user(user):
    return {
        "id": user.pk,
        "username": user.get_username(),
        "email": user.email,
    }


@ensure_csrf_cookie
def csrf_view(request):
    if request.method != "GET":
        return api_error("Method not allowed.", status=405)
    return JsonResponse({"detail": "CSRF cookie set."})


def api_signup_view(request):
    if request.method != "POST":
        return api_error("Method not allowed.", status=405)
    if request.user.is_authenticated:
        return JsonResponse({"user": serialize_user(request.user)})

    payload, error = parse_json(request)
    if error:
        return error

    form = AccountSignupForm(payload)
    if not form.is_valid():
        return api_error(
            "Could not create account.",
            errors=form.errors.get_json_data(),
        )

    user = form.save()
    login(request, user)
    return JsonResponse({"user": serialize_user(user)}, status=201)


def api_login_view(request):
    if request.method != "POST":
        return api_error("Method not allowed.", status=405)

    payload, error = parse_json(request)
    if error:
        return error

    username = payload.get("username", "")
    password = payload.get("password", "")
    if not username or not password:
        return api_error("username and password are required.")

    user = authenticate(request, username=username, password=password)
    if user is None:
        return api_error("Invalid username or password.", status=401)

    login(request, user)
    return JsonResponse({"user": serialize_user(user)})


def api_logout_view(request):
    if request.method != "POST":
        return api_error("Method not allowed.", status=405)
    logout(request)
    return JsonResponse({}, status=204)


@api_login_required
def api_me_view(request):
    if request.method != "GET":
        return api_error("Method not allowed.", status=405)
    return JsonResponse({"user": serialize_user(request.user)})
