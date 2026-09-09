import json
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from banlists.models import BanList
from cards.models import Card

from .featured_monsters import ERA_SIZE, FEATURED_MONSTERS


class AccountApiTests(TestCase):
    def test_csrf_endpoint_sets_cookie(self):
        response = self.client.get(reverse("account_api:csrf"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)

    def test_signup_creates_authenticated_session(self):
        response = self.client.post(
            reverse("account_api:signup"),
            data=json.dumps({
                "username": "duelist",
                "email": "duelist@example.com",
                "password1": "StrongPass!2468",
                "password2": "StrongPass!2468",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user"]["username"], "duelist")
        self.assertEqual(response.json()["user"]["email"], "duelist@example.com")
        me = self.client.get(reverse("account_api:me"))
        self.assertEqual(me.status_code, 200)

    def test_login_and_logout(self):
        get_user_model().objects.create_user(
            username="yugi", password="StrongPass!2468"
        )
        login_response = self.client.post(
            reverse("account_api:login"),
            data=json.dumps({"username": "yugi", "password": "StrongPass!2468"}),
            content_type="application/json",
        )
        self.assertEqual(login_response.status_code, 200)

        logout_response = self.client.post(reverse("account_api:logout"))
        self.assertEqual(logout_response.status_code, 204)
        self.assertEqual(self.client.get(reverse("account_api:me")).status_code, 401)

    def test_invalid_login_returns_401(self):
        response = self.client.post(
            reverse("account_api:login"),
            data=json.dumps({"username": "missing", "password": "wrong"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)


class PasswordManagementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="kaiba",
            email="kaiba@example.com",
            password="CurrentPass!2468",
        )

    def test_password_change_requires_login(self):
        response = self.client.get(reverse("password_change"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('password_change')}",
        )

    def test_logged_in_user_can_change_password_and_keep_session(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("password_change"), {
            "old_password": "CurrentPass!2468",
            "new_password1": "NewSecurePass!9753",
            "new_password2": "NewSecurePass!9753",
        })

        self.assertRedirects(response, reverse("password_change_done"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewSecurePass!9753"))
        self.assertEqual(
            str(self.client.session.get("_auth_user_id")),
            str(self.user.pk),
        )

    def test_existing_email_can_set_a_new_password_immediately(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": "KAIBA@example.com"},
        )

        self.assertRedirects(response, reverse("password_reset_confirm"))
        confirm_response = self.client.get(reverse("password_reset_confirm"))
        self.assertContains(confirm_response, "kaiba@example.com")
        set_password_response = self.client.post(
            reverse("password_reset_confirm"),
            {
            "new_password1": "RecoveredPass!8642",
            "new_password2": "RecoveredPass!8642",
            },
        )

        self.assertRedirects(
            set_password_response,
            reverse("password_reset_complete"),
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("RecoveredPass!8642"))
        self.assertTrue(
            self.client.login(username="kaiba", password="RecoveredPass!8642")
        )

    def test_unknown_email_shows_not_found_error(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": "unknown@example.com"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No account was found with this email.")

    def test_new_password_page_requires_a_checked_email(self):
        response = self.client.get(reverse("password_reset_confirm"))

        self.assertRedirects(response, reverse("password_reset"))

    def test_signup_requires_a_unique_email(self):
        missing_email = self.client.post(reverse("signup"), {
            "username": "joey",
            "password1": "StrongPass!2468",
            "password2": "StrongPass!2468",
        })
        duplicate_email = self.client.post(reverse("signup"), {
            "username": "yugi",
            "email": "KAIBA@example.com",
            "password1": "StrongPass!2468",
            "password2": "StrongPass!2468",
        })

        self.assertEqual(missing_email.status_code, 200)
        self.assertContains(missing_email, "This field is required.")
        self.assertEqual(duplicate_email.status_code, 200)
        self.assertContains(
            duplicate_email,
            "An account with this email already exists.",
        )

    def test_signup_accepts_a_simple_demo_password(self):
        response = self.client.post(reverse("signup"), {
            "username": "simpleduelist",
            "email": "simple@example.com",
            "password1": "1",
            "password2": "1",
        })

        self.assertRedirects(response, reverse("home"))
        user = get_user_model().objects.get(username="simpleduelist")
        self.assertTrue(user.check_password("1"))

    def test_signup_still_requires_matching_passwords(self):
        response = self.client.post(reverse("signup"), {
            "username": "mismatch",
            "email": "mismatch@example.com",
            "password1": "1",
            "password2": "2",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "password fields")
        self.assertFalse(get_user_model().objects.filter(username="mismatch").exists())


class HomeAndLoginPresentationTests(TestCase):
    def test_base_layout_renders_global_soundtrack_player(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-music-player')
        self.assertContains(response, "God's Anger")
        self.assertContains(response, "/audio/gods-anger.mp3/")
        self.assertContains(response, "/audio/track-05.mp3/")
        self.assertContains(response, "data-music-power")
        self.assertContains(response, "data-music-next")
        self.assertContains(response, "data-music-expand")

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="pegasus",
            email="pegasus@example.com",
            password="StrongPass!2468",
        )
        Card.objects.create(
            card_id=89631139,
            name="Blue-Eyes White Dragon",
            card_type="Normal Monster",
            archetype="Blue-Eyes",
        )

    def test_home_renders_42_monsters_in_six_ordered_eras(self):
        response = self.client.get(reverse("home"))
        monsters = response.context["featured_monsters"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(FEATURED_MONSTERS), 42)
        self.assertEqual(len(monsters), 42)
        self.assertEqual(ERA_SIZE, 7)
        self.assertEqual(
            [monsters[index]["era"] for index in range(0, 42, ERA_SIZE)],
            ["DUEL MONSTERS", "GX", "5D'S", "ZEXAL", "ARC-V", "VRAINS"],
        )
        self.assertContains(response, "01 / 42")
        self.assertContains(response, 'id="featured-monsters-data"')

    def test_every_featured_monster_uses_an_existing_local_artwork(self):
        missing = [
            monster["image"]
            for monster in FEATURED_MONSTERS
            if finders.find(monster["image"]) is None
        ]

        self.assertEqual(missing, [])

    def test_hero_explore_url_reuses_card_archive_q_search(self):
        response = self.client.get(reverse("home"))
        first_monster = response.context["featured_monsters"][0]
        parsed_url = urlparse(first_monster["exploreUrl"])

        self.assertEqual(parsed_url.path, reverse("cards_page:list"))
        self.assertEqual(parse_qs(parsed_url.query), {"q": ["Blue-Eyes"]})
        archive = self.client.get(first_monster["exploreUrl"])
        self.assertEqual(archive.context["query"], "Blue-Eyes")
        self.assertContains(archive, "Blue-Eyes White Dragon")

    def test_missing_optional_artwork_path_does_not_break_home_render(self):
        fallback_monster = {
            **FEATURED_MONSTERS[0],
            "image": "monsters/not-present.png",
        }
        with patch("accounts.views.FEATURED_MONSTERS", (fallback_monster,)):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not-present.png")

    def test_home_keeps_anonymous_and_authenticated_navigation(self):
        anonymous = self.client.get(reverse("home"))
        self.assertContains(anonymous, f'href="{reverse("login")}">Login</a>')

        self.client.force_login(self.user)
        authenticated = self.client.get(reverse("home"))
        self.assertContains(authenticated, ">Logout</button>")
        self.assertNotContains(authenticated, f'href="{reverse("login")}">Login</a>')

    def test_login_renders_dark_magician_girl_and_existing_auth_links(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/monsters/dark-magician-girl.png")
        self.assertContains(response, "Forgot your password?")
        self.assertContains(response, "Create an account")
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')

    def test_signup_renders_dark_magician_girl_without_strict_password_rules(self):
        response = self.client.get(reverse("signup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/monsters/dark-magician-girl.png")
        self.assertContains(response, "Demo: use any password you like.")
        self.assertNotContains(response, "at least 8 characters")
        self.assertNotContains(response, "entirely numeric")

    def test_login_post_still_authenticates_and_redirects(self):
        response = self.client.post(reverse("login"), {
            "username": "pegasus",
            "password": "StrongPass!2468",
        })

        self.assertRedirects(response, reverse("home"))
        self.assertEqual(
            str(self.client.session.get("_auth_user_id")),
            str(self.user.pk),
        )


class AdminDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            username="admin", password="admin", email=""
        )
        cls.duelist = get_user_model().objects.create_user(
            username="duelist", password="StrongPass!2468"
        )
        Card.objects.create(
            card_id=55001,
            name="Dashboard Test Card",
            card_type="Spell Card",
        )
        BanList.objects.create(name="TCG - Dashboard", format="TCG", is_active=True)
        BanList.objects.create(name="OCG - Dashboard", format="OCG", is_active=True)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("admin_dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('admin_dashboard')}",
        )

    def test_regular_user_cannot_open_dashboard_or_see_menu(self):
        self.client.force_login(self.duelist)

        dashboard = self.client.get(reverse("admin_dashboard"))
        home = self.client.get(reverse("home"))

        self.assertEqual(dashboard.status_code, 302)
        self.assertNotContains(home, "Dashboard")

    def test_admin_credentials_can_open_dashboard_and_see_system_summary(self):
        self.assertTrue(self.client.login(username="admin", password="admin"))

        response = self.client.get(reverse("admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ADMIN")
        self.assertContains(response, "DASHBOARD")
        self.assertContains(response, "STAFF AUTHORIZED")
        self.assertContains(response, "TCG - Dashboard")
        self.assertContains(response, "OCG - Dashboard")
        self.assertContains(response, "Dashboard")
