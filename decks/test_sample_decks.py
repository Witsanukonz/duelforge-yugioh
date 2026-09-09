import json
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase, SimpleTestCase
from django.urls import reverse

from cards.models import Card

from .models import Deck, DeckCard
from .sample_decks import (
    SAMPLE_OWNER_USERNAME,
    import_sample_deck,
    load_sample_metadata,
)
from .ydk import YDKParseError, parse_ydk, serialize_ydk


class YDKParserTests(SimpleTestCase):
    def test_parses_main_extra_and_side_sections(self):
        parsed = parse_ydk("#main\n100\n#extra\n200\n!side\n300\n")

        self.assertEqual(parsed.sections["MAIN"][100], 1)
        self.assertEqual(parsed.sections["EXTRA"][200], 1)
        self.assertEqual(parsed.sections["SIDE"][300], 1)

    def test_duplicate_ids_are_aggregated(self):
        parsed = parse_ydk("#main\n100\n100\n100\n")

        self.assertEqual(parsed.sections["MAIN"][100], 3)
        self.assertEqual(parsed.totals["MAIN"], 3)

    def test_blank_lines_creator_and_comments_are_ignored(self):
        parsed = parse_ydk("#created by Unit Test\n\n# note\n#main\n100\n")

        self.assertEqual(parsed.creator, "Unit Test")
        self.assertEqual(parsed.sections["MAIN"][100], 1)

    def test_malformed_card_id_is_reported(self):
        with self.assertRaises(YDKParseError) as context:
            parse_ydk("#main\nnot-a-card\n")

        self.assertIn("invalid card ID", str(context.exception))

    def test_card_before_section_is_reported(self):
        with self.assertRaises(YDKParseError) as context:
            parse_ydk("100\n#main\n101\n")

        self.assertIn("before a deck section", str(context.exception))

    def test_serializes_standard_sections_and_repeated_quantities(self):
        content = serialize_ydk(
            {
                "MAIN": {100: 2},
                "EXTRA": {200: 1},
                "SIDE": {300: 2},
            }
        )

        self.assertEqual(
            content,
            "#created by DUELFORGE\n"
            "#main\n100\n100\n"
            "#extra\n200\n"
            "!side\n300\n300\n",
        )
        self.assertEqual(parse_ydk(content).totals, {"MAIN": 2, "EXTRA": 1, "SIDE": 2})


class SampleDeckImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.main_cards = [
            Card.objects.create(
                card_id=51000 + index,
                name=f"Sample Main {index}",
                card_type="Effect Monster",
            )
            for index in range(14)
        ]
        cls.extra_card = Card.objects.create(
            card_id=52000,
            name="Sample Fusion",
            card_type="Fusion Monster",
            frame_type="fusion",
        )
        cls.side_card = Card.objects.create(
            card_id=53000,
            name="Sample Side",
            card_type="Spell Card",
        )

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def valid_ydk(self):
        main_ids = []
        for card in self.main_cards[:13]:
            main_ids.extend([card.card_id] * 3)
        main_ids.append(self.main_cards[13].card_id)
        return "\n".join([
            "#created by tests",
            "#main",
            *(str(card_id) for card_id in main_ids),
            "#extra",
            str(self.extra_card.card_id),
            "!side",
            str(self.side_card.card_id),
            "",
        ])

    def write_deck(self, name="blue-eyes", content=None):
        path = self.root / f"{name}.ydk"
        path.write_text(content or self.valid_ydk(), encoding="utf-8")
        return path

    def write_metadata(self):
        (self.root / "metadata.json").write_text(json.dumps({
            "blue-eyes": {
                "name": "Blue-Eyes Sample",
                "archetype": "Blue-Eyes",
                "description": "Local sample deck.",
                "format": "TCG",
            }
        }), encoding="utf-8")

    def test_strict_import_skips_missing_card_id(self):
        content = self.valid_ydk().replace("!side", "!side\n99999999")
        path = self.write_deck(content=content)

        result = import_sample_deck(path, directory=self.root)

        self.assertEqual(result.status, "SKIPPED")
        self.assertEqual(result.missing_card_ids, [99999999])
        self.assertFalse(Deck.objects.exists())

    def test_character_deck_import_does_not_claim_tournament_legality(self):
        path = self.write_deck(content=(
            "#created by anime character\n"
            "#main\n"
            f"{self.main_cards[0].card_id}\n"
            "#extra\n"
            "!side\n"
        ))

        result = import_sample_deck(path, directory=self.root)

        self.assertEqual(result.status, "CREATED")
        self.assertEqual(result.totals["MAIN"], 1)
        self.assertEqual(DeckCard.objects.get().quantity, 1)

    def test_import_creates_sample_deck_and_correct_deck_cards(self):
        self.write_metadata()
        path = self.write_deck()

        result = import_sample_deck(
            path,
            directory=self.root,
            metadata=load_sample_metadata(self.root),
        )
        deck = Deck.objects.get()

        self.assertEqual(result.status, "CREATED")
        self.assertTrue(deck.is_sample)
        self.assertTrue(deck.is_public)
        self.assertEqual(deck.sample_source, "blue-eyes.ydk")
        self.assertEqual(deck.sample_archetype, "Blue-Eyes")
        self.assertEqual(deck.deck_cards.count(), 16)
        self.assertEqual(deck.deck_cards.get(card=self.main_cards[0]).quantity, 3)
        self.assertEqual(deck.deck_cards.get(card=self.extra_card).section, "EXTRA")
        self.assertEqual(deck.deck_cards.get(card=self.side_card).section, "SIDE")

    def test_second_import_is_unchanged_and_does_not_duplicate(self):
        path = self.write_deck()

        first = import_sample_deck(path, directory=self.root)
        second = import_sample_deck(path, directory=self.root)

        self.assertEqual(first.status, "CREATED")
        self.assertEqual(second.status, "UNCHANGED")
        self.assertEqual(Deck.objects.count(), 1)
        self.assertEqual(DeckCard.objects.count(), 16)

    def test_changed_source_updates_existing_deck(self):
        path = self.write_deck()
        import_sample_deck(path, directory=self.root)
        self.write_metadata()

        result = import_sample_deck(
            path,
            directory=self.root,
            metadata=load_sample_metadata(self.root),
        )

        self.assertEqual(result.status, "UPDATED")
        self.assertEqual(Deck.objects.get().name, "Blue-Eyes Sample")
        self.assertEqual(Deck.objects.count(), 1)

    def test_system_owner_is_not_duplicated(self):
        path = self.write_deck()
        import_sample_deck(path, directory=self.root)
        import_sample_deck(path, directory=self.root)

        users = get_user_model().objects.filter(username=SAMPLE_OWNER_USERNAME)
        self.assertEqual(users.count(), 1)
        self.assertFalse(users.get().has_usable_password())

    def test_each_deck_update_rolls_back_if_cards_fail(self):
        path = self.write_deck()
        import_sample_deck(path, directory=self.root)
        deck = Deck.objects.get()
        original_name = deck.name
        self.write_metadata()

        with patch(
            "decks.sample_decks.DeckCard.objects.bulk_create",
            side_effect=IntegrityError("simulated failure"),
        ):
            with self.assertRaises(IntegrityError):
                import_sample_deck(
                    path,
                    directory=self.root,
                    metadata=load_sample_metadata(self.root),
                )

        deck.refresh_from_db()
        self.assertEqual(deck.name, original_name)
        self.assertEqual(deck.deck_cards.count(), 16)

    def test_management_command_reports_and_is_idempotent(self):
        self.write_deck()
        first_output = StringIO()
        second_output = StringIO()

        call_command("import_sample_decks", path=str(self.root), stdout=first_output)
        call_command("import_sample_decks", path=str(self.root), stdout=second_output)

        self.assertIn("Created: 1", first_output.getvalue())
        self.assertIn("Unchanged: 1", second_output.getvalue())
        self.assertEqual(Deck.objects.count(), 1)


class SampleDeckWebTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.system_owner = get_user_model().objects.create_user(username="DUELFORGE")
        cls.user = get_user_model().objects.create_user(
            username="duelist", password="password123"
        )
        cls.card = Card.objects.create(
            card_id=61001,
            name="Library Card",
            card_type="Effect Monster",
        )
        cls.sample = Deck.objects.create(
            owner=cls.system_owner,
            name="Library Sample",
            description="A local example.",
            format="TCG",
            is_public=True,
            is_sample=True,
            sample_source="library-sample.ydk",
            sample_archetype="Library",
        )
        cls.sample_entry = DeckCard.objects.create(
            deck=cls.sample,
            card=cls.card,
            section="MAIN",
            quantity=3,
        )

    def test_sample_deck_is_visible_to_anonymous_user(self):
        listing = self.client.get(reverse("decks_page:list"))
        detail = self.client.get(reverse("decks_page:builder", args=[self.sample.pk]))

        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, "Featured Decks")
        self.assertContains(listing, "Library Sample")
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Featured sample deck")
        self.assertContains(detail, "Sign in to copy")
        self.assertContains(detail, '<span aria-label="Deck format">TCG</span>', html=True)
        self.assertNotContains(detail, "Deck setup")
        self.assertNotContains(detail, "ตั้งค่าเด็ค")

    def test_sample_deck_is_read_only_even_for_logged_in_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("decks_page:builder", args=[self.sample.pk]))

        self.assertContains(response, "Copy to My Decks")
        self.assertNotContains(response, "data-delete-deck")
        self.assertContains(response, 'data-can-edit="false"')

    def test_normal_user_cannot_edit_or_delete_sample_deck(self):
        self.client.force_login(self.user)
        update = self.client.patch(
            reverse("decks:detail", args=[self.sample.pk]),
            data=json.dumps({"name": "Stolen"}),
            content_type="application/json",
        )
        delete = self.client.delete(reverse("decks:detail", args=[self.sample.pk]))

        self.assertEqual(update.status_code, 404)
        self.assertEqual(delete.status_code, 404)
        self.sample.refresh_from_db()
        self.assertEqual(self.sample.name, "Library Sample")

    def test_normal_user_cannot_mutate_sample_cards(self):
        self.client.force_login(self.user)
        add = self.client.post(
            reverse("decks:cards", args=[self.sample.pk]),
            data=json.dumps({"card_id": self.card.card_id}),
            content_type="application/json",
        )
        remove = self.client.delete(
            reverse("decks:card-detail", args=[self.sample.pk, self.sample_entry.pk])
        )

        self.assertEqual(add.status_code, 404)
        self.assertEqual(remove.status_code, 404)
        self.assertEqual(self.sample.deck_cards.get().quantity, 3)

    def test_anonymous_user_cannot_copy_sample(self):
        response = self.client.post(
            reverse("decks_page:copy-sample", args=[self.sample.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        self.assertEqual(Deck.objects.count(), 1)

    def test_logged_in_user_can_copy_with_independent_cards(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("decks_page:copy-sample", args=[self.sample.pk])
        )
        copied = Deck.objects.get(owner=self.user)

        self.assertRedirects(
            response,
            reverse("decks_page:builder", args=[copied.pk]),
            fetch_redirect_response=False,
        )
        self.assertFalse(copied.is_sample)
        self.assertFalse(copied.is_public)
        self.assertEqual(copied.name, "Library Sample - Copy")
        copied_entry = copied.deck_cards.get()
        self.assertNotEqual(copied_entry.pk, self.sample_entry.pk)
        copied_entry.quantity = 1
        copied_entry.save()
        self.sample_entry.refresh_from_db()
        self.assertEqual(self.sample_entry.quantity, 3)

    def test_copy_name_is_stable_when_user_already_has_a_copy(self):
        Deck.objects.create(owner=self.user, name="Library Sample - Copy")
        self.client.force_login(self.user)

        self.client.post(reverse("decks_page:copy-sample", args=[self.sample.pk]))

        self.assertTrue(
            Deck.objects.filter(owner=self.user, name="Library Sample - Copy (2)").exists()
        )

    def test_user_decks_and_featured_decks_are_separate(self):
        Deck.objects.create(owner=self.user, name="Personal Deck")
        self.client.force_login(self.user)

        response = self.client.get(reverse("decks_page:list"))
        content = response.content.decode()

        self.assertLess(content.index("My Decks"), content.index("Featured Decks"))
        self.assertContains(response, "Personal Deck")
        self.assertContains(response, "Library Sample")

    def test_featured_library_tabs_separate_character_and_player_decks(self):
        player_deck = Deck.objects.create(
            owner=self.user,
            name="Public Player Strategy",
            is_public=True,
        )

        character_response = self.client.get(reverse("decks_page:list"))
        player_response = self.client.get(
            reverse("decks_page:list"), {"library": "player"}
        )

        self.assertEqual(character_response.context["library_tab"], "character")
        self.assertContains(character_response, "Character Deck")
        self.assertContains(character_response, "Player Deck")
        self.assertContains(character_response, self.sample.name)
        self.assertNotContains(character_response, player_deck.name)

        self.assertEqual(player_response.context["library_tab"], "player")
        self.assertContains(player_response, "Player Decks")
        self.assertContains(player_response, player_deck.name)
        self.assertNotContains(player_response, self.sample.name)

    def test_featured_decks_are_paginated_twelve_per_page(self):
        for index in range(12):
            Deck.objects.create(
                owner=self.system_owner,
                name=f"Sample {index}",
                is_public=True,
                is_sample=True,
                sample_source=f"sample-{index}.ydk",
            )

        first_page = self.client.get(reverse("decks_page:list"))
        second_page = self.client.get(
            reverse("decks_page:list"), {"sample_page": 2}
        )

        self.assertEqual(len(first_page.context["featured_page"]), 12)
        self.assertEqual(len(second_page.context["featured_page"]), 1)

    def test_featured_decks_can_be_searched_by_archetype(self):
        response = self.client.get(reverse("decks_page:list"), {"q": "Library"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["featured_page"].paginator.count, 1)
        self.assertContains(response, "Library Sample")
        self.assertContains(response, "type=\"submit\">Search</button>")


class CharacterCoverCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="cover-owner")
        cls.deck = Deck.objects.create(
            owner=cls.owner,
            name="Yugi — Test Deck",
            is_public=True,
            is_sample=True,
            sample_source="yugi-test.ydk",
        )

    def test_command_downloads_once_and_assigns_cover_to_matching_sample_decks(self):
        png = b"\x89PNG\r\n\x1a\nunit-test-image"
        with TemporaryDirectory() as temporary_media:
            with self.settings(MEDIA_ROOT=temporary_media):
                with patch(
                    "decks.management.commands.download_character_covers.urlopen",
                    return_value=BytesIO(png),
                ) as mocked_urlopen:
                    call_command("download_character_covers", stdout=StringIO())
                    call_command("download_character_covers", stdout=StringIO())

                self.deck.refresh_from_db()
                self.assertEqual(
                    self.deck.cover_image.name,
                    "deck_covers/characters/yugi.png",
                )
                self.assertTrue(
                    (Path(temporary_media) / self.deck.cover_image.name).exists()
                )
                self.assertEqual(mocked_urlopen.call_count, 1)
