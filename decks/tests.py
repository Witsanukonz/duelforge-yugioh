import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from banlists.models import BanList, BanListEntry
from cards.models import Card

from .models import Deck, DeckCard
from .services import validate_deck


class DeckApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="owner", password="password123"
        )
        cls.other = get_user_model().objects.create_user(
            username="other", password="password123"
        )
        cls.card = Card.objects.create(
            card_id=2001, name="Unlimited Card", card_type="Monster"
        )
        cls.limited_card = Card.objects.create(
            card_id=2002, name="Limited Card", card_type="Spell"
        )
        cls.forbidden_card = Card.objects.create(
            card_id=2003, name="Forbidden Card", card_type="Spell"
        )
        cls.fusion_card = Card.objects.create(
            card_id=2004,
            name="Fusion Card",
            card_type="Fusion Monster",
            frame_type="fusion",
        )
        cls.banlist = BanList.objects.create(name="Test TCG", format="TCG")
        BanListEntry.objects.create(
            ban_list=cls.banlist,
            card=cls.limited_card,
            status="LIMITED",
            max_copies=1,
        )
        BanListEntry.objects.create(
            ban_list=cls.banlist,
            card=cls.forbidden_card,
            status="FORBIDDEN",
            max_copies=0,
        )

    def setUp(self):
        self.client.force_login(self.owner)

    def create_deck(self, **overrides):
        data = {
            "name": "Control Deck",
            "format": "TCG",
            "ban_list": self.banlist.pk,
            "is_public": False,
        }
        data.update(overrides)
        return self.client.post(
            reverse("decks:collection"),
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_create_update_and_delete_owned_deck(self):
        create = self.create_deck(description="Opening combo and recovery plan.")
        self.assertEqual(create.status_code, 201)
        deck_id = create.json()["deck"]["id"]
        self.assertEqual(
            create.json()["deck"]["description"],
            "Opening combo and recovery plan.",
        )

        update = self.client.patch(
            reverse("decks:detail", args=[deck_id]),
            data=json.dumps(
                {
                    "name": "Updated Deck",
                    "description": "Updated strategy notes.",
                    "is_public": True,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.json()["deck"]["name"], "Updated Deck")
        self.assertEqual(update.json()["deck"]["description"], "Updated strategy notes.")
        self.assertEqual(
            Deck.objects.get(pk=deck_id).description,
            "Updated strategy notes.",
        )

        delete = self.client.delete(reverse("decks:detail", args=[deck_id]))
        self.assertEqual(delete.status_code, 204)
        self.assertFalse(Deck.objects.filter(pk=deck_id).exists())

    def test_private_deck_is_hidden_but_public_deck_is_visible(self):
        private = Deck.objects.create(owner=self.owner, name="Private")
        public = Deck.objects.create(owner=self.owner, name="Public", is_public=True)
        self.client.force_login(self.other)

        self.assertEqual(
            self.client.get(reverse("decks:detail", args=[private.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("decks:detail", args=[public.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.patch(
                reverse("decks:detail", args=[public.pk]),
                data=json.dumps({"name": "Stolen"}),
                content_type="application/json",
            ).status_code,
            404,
        )

    def test_create_requires_authentication(self):
        self.client.logout()
        response = self.create_deck()
        self.assertEqual(response.status_code, 401)

    def test_add_card_and_enforce_three_copy_limit_across_sections(self):
        deck_id = self.create_deck().json()["deck"]["id"]
        add = self.client.post(
            reverse("decks:cards", args=[deck_id]),
            data=json.dumps({
                "card_id": self.card.card_id,
                "quantity": 3,
                "section": "MAIN",
            }),
            content_type="application/json",
        )
        self.assertEqual(add.status_code, 201)

        over_limit = self.client.post(
            reverse("decks:cards", args=[deck_id]),
            data=json.dumps({
                "card_id": self.card.card_id,
                "quantity": 1,
                "section": "SIDE",
            }),
            content_type="application/json",
        )
        self.assertEqual(over_limit.status_code, 400)
        self.assertIn("limited to 3 copies", str(over_limit.json()))

    def test_banlist_limits_are_enforced(self):
        deck_id = self.create_deck().json()["deck"]["id"]
        limited = self.client.post(
            reverse("decks:cards", args=[deck_id]),
            data=json.dumps({
                "card_id": self.limited_card.card_id,
                "quantity": 2,
            }),
            content_type="application/json",
        )
        forbidden = self.client.post(
            reverse("decks:cards", args=[deck_id]),
            data=json.dumps({"card_id": self.forbidden_card.card_id}),
            content_type="application/json",
        )

        self.assertEqual(limited.status_code, 400)
        self.assertEqual(forbidden.status_code, 400)
        self.assertEqual(DeckCard.objects.filter(deck_id=deck_id).count(), 0)

    def test_existing_card_is_updated_and_can_be_removed(self):
        deck_id = self.create_deck().json()["deck"]["id"]
        url = reverse("decks:cards", args=[deck_id])
        first = self.client.post(
            url,
            data=json.dumps({"card_id": self.card.card_id, "quantity": 1}),
            content_type="application/json",
        )
        second = self.client.post(
            url,
            data=json.dumps({"card_id": self.card.card_id, "quantity": 2}),
            content_type="application/json",
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(DeckCard.objects.get(deck_id=deck_id).quantity, 2)

        entry_id = first.json()["deck_card"]["id"]
        deleted = self.client.delete(
            reverse("decks:card-detail", args=[deck_id, entry_id])
        )
        self.assertEqual(deleted.status_code, 204)

    def test_extra_deck_card_section_rules_are_enforced(self):
        deck_id = self.create_deck().json()["deck"]["id"]
        url = reverse("decks:cards", args=[deck_id])

        normal_in_extra = self.client.post(
            url,
            data=json.dumps({"card_id": self.card.card_id, "section": "EXTRA"}),
            content_type="application/json",
        )
        fusion_in_main = self.client.post(
            url,
            data=json.dumps({"card_id": self.fusion_card.card_id, "section": "MAIN"}),
            content_type="application/json",
        )
        fusion_in_extra = self.client.post(
            url,
            data=json.dumps({"card_id": self.fusion_card.card_id, "section": "EXTRA"}),
            content_type="application/json",
        )

        self.assertEqual(normal_in_extra.status_code, 400)
        self.assertIn("Only Fusion, Synchro, Xyz, and Link", str(normal_in_extra.json()))
        self.assertEqual(fusion_in_main.status_code, 400)
        self.assertIn("can only be added to the Extra Deck", str(fusion_in_main.json()))
        self.assertEqual(fusion_in_extra.status_code, 201)

    def test_existing_normal_card_can_move_from_main_to_side(self):
        deck_id = self.create_deck().json()["deck"]["id"]
        created = self.client.post(
            reverse("decks:cards", args=[deck_id]),
            data=json.dumps({"card_id": self.card.card_id, "section": "MAIN"}),
            content_type="application/json",
        )

        moved = self.client.patch(
            reverse(
                "decks:card-detail",
                args=[deck_id, created.json()["deck_card"]["id"]],
            ),
            data=json.dumps({"section": "SIDE"}),
            content_type="application/json",
        )

        self.assertEqual(moved.status_code, 200)
        self.assertEqual(moved.json()["deck_card"]["section"], "SIDE")

    def test_one_copy_can_move_without_moving_the_whole_stack(self):
        deck_id = self.create_deck().json()["deck"]["id"]
        created = self.client.post(
            reverse("decks:cards", args=[deck_id]),
            data=json.dumps({
                "card_id": self.card.card_id,
                "quantity": 3,
                "section": "MAIN",
            }),
            content_type="application/json",
        )

        moved = self.client.patch(
            reverse(
                "decks:card-detail",
                args=[deck_id, created.json()["deck_card"]["id"]],
            ),
            data=json.dumps({"section": "SIDE", "move_quantity": 1}),
            content_type="application/json",
        )

        self.assertEqual(moved.status_code, 200)
        self.assertEqual(
            DeckCard.objects.get(deck_id=deck_id, section="MAIN").quantity,
            2,
        )
        self.assertEqual(
            DeckCard.objects.get(deck_id=deck_id, section="SIDE").quantity,
            1,
        )
        self.assertEqual(len(moved.json()["deck_cards"]), 2)

        moved_again = self.client.patch(
            reverse(
                "decks:card-detail",
                args=[deck_id, created.json()["deck_card"]["id"]],
            ),
            data=json.dumps({"section": "SIDE", "move_quantity": 1}),
            content_type="application/json",
        )

        self.assertEqual(moved_again.status_code, 200)
        self.assertEqual(
            DeckCard.objects.get(deck_id=deck_id, section="MAIN").quantity,
            1,
        )
        self.assertEqual(
            DeckCard.objects.get(deck_id=deck_id, section="SIDE").quantity,
            2,
        )

    def test_validation_reports_incomplete_main_deck(self):
        deck_id = self.create_deck().json()["deck"]["id"]
        response = self.client.get(reverse("decks:validate", args=[deck_id]))

        self.assertEqual(response.status_code, 200)
        report = response.json()["validation"]
        self.assertFalse(report["is_valid"])
        self.assertEqual(report["counts"]["MAIN"], 0)
        self.assertEqual(report["issues"][0]["code"], "main_deck_size")

    def test_rejects_banlist_from_wrong_format(self):
        ocg = BanList.objects.create(name="OCG List", format="OCG")
        response = self.create_deck(format="TCG", ban_list=ocg.pk)
        self.assertEqual(response.status_code, 400)

    def test_deck_can_be_created_without_a_banlist(self):
        response = self.create_deck(ban_list=None)

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()["deck"]["ban_list"])

    def test_deck_defaults_to_current_format_banlist_when_field_is_omitted(self):
        response = self.client.post(
            reverse("decks:collection"),
            data=json.dumps({"name": "Default List", "format": "TCG"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["deck"]["ban_list"]["id"], self.banlist.pk)

    def test_deck_pages_render_for_owner(self):
        BanList.objects.create(name="Test OCG", format="OCG")
        deck = Deck.objects.create(owner=self.owner, name="Visual Test Deck")
        listing = self.client.get(reverse("decks_page:list"))
        builder = self.client.get(reverse("decks_page:builder", args=[deck.pk]))
        create = self.client.get(reverse("decks_page:create"))

        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, "Visual Test Deck")
        self.assertEqual(builder.status_code, 200)
        self.assertContains(builder, "Deck editor")
        content = builder.content.decode()
        self.assertLess(content.index("ตั้งค่าเด็ค"), content.index("Main Deck"))
        self.assertContains(builder, 'class="builder-content"')
        self.assertContains(builder, "data-drop-zone", count=3)
        self.assertContains(builder, "deck-builder.css")
        self.assertContains(builder, "ค้นหาการ์ด")
        self.assertContains(builder, "data-delete-deck")
        self.assertContains(builder, ">Ban List\n", html=False)
        self.assertContains(builder, ">N/A</option>", html=False)
        self.assertContains(builder, ">TCG</option>", html=False)
        self.assertContains(builder, ">OCG</option>", html=False)
        self.assertContains(builder, 'data-field="ruleset"')
        self.assertContains(builder, reverse("decks_page:export", args=[deck.pk]))
        self.assertContains(builder, "EXPORT .YDK")
        self.assertNotContains(builder, 'data-field="format"')
        self.assertNotContains(builder, 'data-field="ban_list"')
        self.assertEqual(create.status_code, 200)

    def test_public_deck_hides_setup_from_non_owner_and_shows_only_format(self):
        deck = Deck.objects.create(
            owner=self.owner,
            name="Public OCG Deck",
            format="OCG",
            is_public=True,
        )
        self.client.force_login(self.other)

        response = self.client.get(reverse("decks_page:builder", args=[deck.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<span aria-label="Deck format">OCG</span>', html=True)
        self.assertNotContains(response, "Deck setup")
        self.assertNotContains(response, "ตั้งค่าเด็ค")
        self.assertNotContains(response, "Drag mode")
        self.assertNotContains(response, 'aria-label="Deck settings"')
        self.assertContains(response, reverse("decks_page:export", args=[deck.pk]))

    def test_export_downloads_main_extra_side_and_repeats_quantity(self):
        deck = Deck.objects.create(
            owner=self.owner,
            name="Blue-Eyes: Test?",
            is_public=False,
        )
        DeckCard.objects.bulk_create(
            [
                DeckCard(deck=deck, card=self.card, section="MAIN", quantity=2),
                DeckCard(deck=deck, card=self.fusion_card, section="EXTRA", quantity=1),
                DeckCard(deck=deck, card=self.limited_card, section="SIDE", quantity=1),
            ]
        )

        response = self.client.get(reverse("decks_page:export", args=[deck.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/octet-stream")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="Blue-Eyes_Test.ydk"',
        )
        self.assertEqual(
            response.content.decode(),
            "#created by DUELFORGE\n"
            "#main\n2001\n2001\n"
            "#extra\n2004\n"
            "!side\n2002\n",
        )

    def test_export_uses_existing_deck_visibility_permissions(self):
        private_deck = Deck.objects.create(owner=self.owner, name="Private Export")
        public_deck = Deck.objects.create(
            owner=self.owner,
            name="Public Export",
            is_public=True,
        )
        sample_deck = Deck.objects.create(
            owner=self.owner,
            name="Sample Export",
            is_public=True,
            is_sample=True,
            sample_source="sample-export.ydk",
        )

        self.client.force_login(self.other)
        self.assertEqual(
            self.client.get(
                reverse("decks_page:export", args=[private_deck.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("decks_page:export", args=[public_deck.pk])
            ).status_code,
            200,
        )

        self.client.logout()
        self.assertEqual(
            self.client.get(
                reverse("decks_page:export", args=[sample_deck.pk])
            ).status_code,
            200,
        )

    def test_my_decks_are_paginated_twelve_per_page(self):
        Deck.objects.bulk_create([
            Deck(owner=self.owner, name=f"Owned Deck {index:02d}")
            for index in range(13)
        ])

        response = self.client.get(reverse("decks_page:list"), {"my_page": 2})

        self.assertEqual(response.context["my_page"].paginator.count, 13)
        self.assertEqual(len(response.context["my_page"]), 1)
        self.assertContains(response, "Page 2")


class StructuredDeckValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="validator", password="password123"
        )
        cls.limited = Card.objects.create(
            card_id=42001, name="Cross Section Limited", card_type="Spell"
        )
        cls.semi = Card.objects.create(
            card_id=42002, name="Cross Section Semi", card_type="Spell"
        )
        cls.forbidden = Card.objects.create(
            card_id=42003, name="Validation Forbidden", card_type="Spell"
        )
        cls.unlimited = Card.objects.create(
            card_id=42004, name="Validation Unlimited", card_type="Spell"
        )
        cls.tcg = BanList.objects.create(name="TCG - Test", format="TCG")
        cls.ocg = BanList.objects.create(name="OCG - Test", format="OCG")
        BanListEntry.objects.create(
            ban_list=cls.tcg, card=cls.limited, status="LIMITED", max_copies=1
        )
        BanListEntry.objects.create(
            ban_list=cls.tcg, card=cls.semi, status="SEMI_LIMITED", max_copies=2
        )
        BanListEntry.objects.create(
            ban_list=cls.tcg, card=cls.forbidden, status="FORBIDDEN", max_copies=0
        )
        BanListEntry.objects.create(
            ban_list=cls.ocg, card=cls.limited, status="SEMI_LIMITED", max_copies=2
        )

    def make_deck(self, banlist=None, deck_format="TCG"):
        return Deck.objects.create(
            owner=self.owner,
            name="Validation Deck",
            format=deck_format,
            ban_list=self.tcg if banlist is None else banlist,
        )

    def fill_main(self, deck, count):
        entries = []
        sequence = 0
        while count:
            quantity = min(3, count)
            card = Card.objects.create(
                card_id=43000 + (deck.pk * 100) + sequence,
                name=f"Validation Filler {deck.pk}-{sequence}",
                card_type="Monster",
            )
            entries.append(DeckCard(
                deck=deck, card=card, section="MAIN", quantity=quantity
            ))
            count -= quantity
            sequence += 1
        DeckCard.objects.bulk_create(entries)

    def copy_violation(self, report, card):
        return next(
            item for item in report["violations"] if item.get("card_id") == card.card_id
        )

    def test_limited_count_combines_main_and_side(self):
        deck = self.make_deck()
        self.fill_main(deck, 39)
        DeckCard.objects.bulk_create([
            DeckCard(deck=deck, card=self.limited, section="MAIN", quantity=1),
            DeckCard(deck=deck, card=self.limited, section="SIDE", quantity=1),
        ])

        report = validate_deck(deck)
        violation = self.copy_violation(report, self.limited)
        self.assertFalse(report["is_legal"])
        self.assertEqual((violation["used"], violation["allowed"]), (2, 1))

    def test_semi_limited_total_two_is_legal(self):
        deck = self.make_deck()
        self.fill_main(deck, 39)
        DeckCard.objects.bulk_create([
            DeckCard(deck=deck, card=self.semi, section="MAIN", quantity=1),
            DeckCard(deck=deck, card=self.semi, section="SIDE", quantity=1),
        ])

        report = validate_deck(deck)
        self.assertTrue(report["is_legal"])
        self.assertEqual(report["counts"], {"MAIN": 40, "EXTRA": 0, "SIDE": 1})

    def test_semi_limited_total_three_is_illegal(self):
        deck = self.make_deck()
        self.fill_main(deck, 39)
        DeckCard.objects.bulk_create([
            DeckCard(deck=deck, card=self.semi, section="MAIN", quantity=1),
            DeckCard(deck=deck, card=self.semi, section="SIDE", quantity=2),
        ])

        violation = self.copy_violation(validate_deck(deck), self.semi)
        self.assertEqual((violation["used"], violation["allowed"]), (3, 2))

    def test_forbidden_one_is_illegal(self):
        deck = self.make_deck()
        self.fill_main(deck, 39)
        DeckCard.objects.create(
            deck=deck, card=self.forbidden, section="MAIN", quantity=1
        )

        violation = self.copy_violation(validate_deck(deck), self.forbidden)
        self.assertEqual(violation["status"], "FORBIDDEN")
        self.assertEqual(violation["allowed"], 0)

    def test_unlisted_card_uses_generic_three_copy_limit(self):
        deck = self.make_deck()
        self.fill_main(deck, 37)
        DeckCard.objects.bulk_create([
            DeckCard(deck=deck, card=self.unlimited, section="MAIN", quantity=3),
            DeckCard(deck=deck, card=self.unlimited, section="SIDE", quantity=1),
        ])

        violation = self.copy_violation(validate_deck(deck), self.unlimited)
        self.assertEqual(violation["type"], "COPY_LIMIT")
        self.assertEqual(violation["allowed"], 3)

    def test_same_card_can_have_different_tcg_and_ocg_status(self):
        tcg_deck = self.make_deck()
        ocg_deck = self.make_deck(banlist=self.ocg, deck_format="OCG")
        for deck in (tcg_deck, ocg_deck):
            self.fill_main(deck, 39)
            DeckCard.objects.bulk_create([
                DeckCard(deck=deck, card=self.limited, section="MAIN", quantity=1),
                DeckCard(deck=deck, card=self.limited, section="SIDE", quantity=1),
            ])

        self.assertFalse(validate_deck(tcg_deck)["is_legal"])
        self.assertTrue(validate_deck(ocg_deck)["is_legal"])

    def test_validation_response_extends_legacy_shape(self):
        deck = self.make_deck()
        report = validate_deck(deck)

        self.assertIn("is_valid", report)
        self.assertIn("issues", report)
        self.assertEqual(report["is_valid"], report["is_legal"])
        self.assertEqual(report["issues"], report["violations"])
        self.assertEqual(report["format"], "TCG")
        self.assertEqual(report["banlist"]["id"], self.tcg.pk)
        self.assertEqual(report["section_counts"]["main"], 0)
