import json
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cards.models import Card

from .models import BanList, BanListEntry
from .services import get_active_banlist, import_banlist_payload


class BanListApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.card = Card.objects.create(
            card_id=3001,
            name="Restricted Dragon",
            card_type="Effect Monster",
            archetype="Dragon",
        )
        cls.old = BanList.objects.create(
            name="Old TCG",
            format="TCG",
            effective_date=timezone.localdate() - timedelta(days=30),
            is_active=True,
        )
        cls.current = BanList.objects.create(
            name="Current TCG",
            format="TCG",
            effective_date=timezone.localdate(),
            is_active=True,
        )
        BanListEntry.objects.create(
            ban_list=cls.current,
            card=cls.card,
            status="LIMITED",
            max_copies=1,
        )

    def setUp(self):
        cache.clear()

    def test_active_banlist_is_cached_and_invalidated(self):
        with self.assertNumQueries(1):
            first = get_active_banlist("TCG")
        with self.assertNumQueries(0):
            second = get_active_banlist("TCG")

        self.assertEqual(first.pk, second.pk)

        replacement = BanList.objects.create(
            name="Replacement TCG",
            format="TCG",
            effective_date=timezone.localdate(),
            is_active=True,
        )
        self.assertEqual(get_active_banlist("TCG").pk, replacement.pk)

    def test_current_returns_latest_effective_list(self):
        response = self.client.get(reverse("banlists:current"), {"format": "TCG"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["banlist"]["id"], self.current.pk)

    def test_current_rejects_invalid_format(self):
        response = self.client.get(reverse("banlists:current"), {"format": "MD"})
        self.assertEqual(response.status_code, 400)

    def test_detail_filters_entries(self):
        response = self.client.get(
            reverse("banlists:detail", args=[self.current.pk]),
            {"q": "dragon", "status": "limited"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()["banlist"]
        self.assertEqual(payload["pagination"]["total"], 1)
        self.assertEqual(payload["entries"][0]["max_copies"], 1)

    def test_banlist_page_renders_card_gallery_with_status_badge(self):
        response = self.client.get(reverse("banlists_page:list"), {"format": "TCG"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ban-card-grid")
        self.assertContains(response, "Limited")
        self.assertContains(response, "Restricted Dragon")

    def test_banlist_page_filters_gallery_by_status(self):
        response = self.client.get(
            reverse("banlists_page:list"),
            {"format": "TCG", "status": "FORBIDDEN"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Restricted Dragon")
        self.assertContains(response, "Showing 0 restricted cards")

    def test_banlist_page_is_paginated_thirty_per_page(self):
        cards = Card.objects.bulk_create([
            Card(
                card_id=93000 + index,
                name=f"Paginated Restricted {index:02d}",
                card_type="Spell Card",
            )
            for index in range(30)
        ])
        BanListEntry.objects.bulk_create([
            BanListEntry(
                ban_list=self.current,
                card=card,
                status="LIMITED",
                max_copies=1,
            )
            for card in cards
        ])

        response = self.client.get(
            reverse("banlists_page:list"),
            {"format": "TCG", "page": 2},
        )

        self.assertEqual(response.context["page_obj"].paginator.count, 31)
        self.assertEqual(len(response.context["page_obj"]), 1)
        self.assertContains(response, "Page 2")

    def test_card_detail_returns_to_the_filtered_banlist(self):
        banlist_page = self.client.get(
            reverse("banlists_page:list"),
            {"format": "TCG", "status": "LIMITED", "q": "Dragon"},
        )
        return_url = banlist_page.context["banlist_return_url"]

        self.assertContains(banlist_page, "return=/ban-list/%3Fformat%3DTCG")

        detail = self.client.get(
            reverse("cards_page:detail", args=[self.card.card_id]),
            {"return": return_url},
        )

        self.assertContains(detail, "← Back to ban list")
        self.assertContains(detail, f'href="{return_url.replace("&", "&amp;")}"')


class BanListImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.forbidden = Card.objects.create(
            card_id=41001, name="Import Forbidden", card_type="Spell"
        )
        cls.limited = Card.objects.create(
            card_id=41002, name="Import Limited", card_type="Spell"
        )
        cls.semi_limited = Card.objects.create(
            card_id=41003, name="Import Semi", card_type="Spell"
        )

    def payload(self, banlist_format="TCG"):
        return {
            "format": banlist_format,
            "effective_date": "2026-05-18" if banlist_format == "TCG" else "2026-07-01",
            "source": "Konami Official Forbidden & Limited List",
            "source_url": "https://www.yugioh-card.com/",
            "cards": [
                {"card_id": self.forbidden.card_id, "status": "FORBIDDEN"},
                {"card_id": self.limited.card_id, "status": "LIMITED"},
                {"card_id": self.semi_limited.card_id, "status": "SEMI_LIMITED"},
            ],
        }

    def test_import_tcg_maps_all_copy_limits(self):
        report = import_banlist_payload(self.payload("TCG"))

        self.assertTrue(report["created"])
        self.assertEqual(report["matched_cards"], 3)
        self.assertEqual(
            dict(report["banlist"].entries.values_list("status", "max_copies")),
            {"FORBIDDEN": 0, "LIMITED": 1, "SEMI_LIMITED": 2},
        )

    def test_import_ocg_creates_active_ocg_list(self):
        report = import_banlist_payload(self.payload("OCG"))

        self.assertEqual(report["banlist"].format, "OCG")
        self.assertEqual(report["banlist"].effective_date, date(2026, 7, 1))
        self.assertTrue(report["banlist"].is_active)

    def test_reimport_updates_without_duplicate_entries(self):
        first = import_banlist_payload(self.payload())
        second = import_banlist_payload(self.payload())

        self.assertFalse(second["created"])
        self.assertEqual(first["banlist"].pk, second["banlist"].pk)
        self.assertEqual(BanList.objects.filter(format="TCG").count(), 1)
        self.assertEqual(BanListEntry.objects.filter(ban_list=second["banlist"]).count(), 3)

    def test_missing_card_is_reported_without_crashing(self):
        payload = self.payload()
        payload["cards"].append({"card_id": 99999999, "status": "LIMITED"})

        report = import_banlist_payload(payload)

        self.assertEqual(report["missing_card_ids"], [99999999])
        self.assertEqual(report["total_cards"], 4)
        self.assertEqual(report["matched_cards"], 3)

    def test_malformed_json_fails_without_changing_existing_list(self):
        existing = import_banlist_payload(self.payload())["banlist"]
        original_entry_ids = list(existing.entries.values_list("pk", flat=True))
        with TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text('{"format": "TCG",', encoding="utf-8")
            with self.assertRaises(CommandError):
                call_command("import_banlist", str(path))

        existing.refresh_from_db()
        self.assertTrue(existing.is_active)
        self.assertEqual(
            list(existing.entries.values_list("pk", flat=True)), original_entry_ids
        )

    def test_database_failure_rolls_back_replacement(self):
        existing = import_banlist_payload(self.payload())["banlist"]
        original_count = existing.entries.count()
        with patch(
            "banlists.services.BanListEntry.objects.bulk_create",
            side_effect=IntegrityError("simulated failure"),
        ):
            with self.assertRaises(IntegrityError):
                import_banlist_payload(self.payload())

        self.assertEqual(existing.entries.count(), original_count)

    def test_management_command_prints_import_summary(self):
        output = StringIO()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "tcg.json"
            path.write_text(json.dumps(self.payload()), encoding="utf-8")
            call_command("import_banlist", str(path), stdout=output)

        summary = output.getvalue()
        self.assertIn("TCG Ban List", summary)
        self.assertIn("Forbidden: 1", summary)
        self.assertIn("Missing card IDs: 0", summary)
