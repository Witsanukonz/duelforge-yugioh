from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cards.models import Card
from decks.models import Deck, DeckCard
from decks.views import deck_breakdown


class DeckBreakdownTests(TestCase):
    def test_groups_archetypes_and_card_types_by_quantity(self):
        result = deck_breakdown({
            "cards": [
                {
                    "quantity": 2,
                    "card": {
                        "archetype": "Sky Striker",
                        "card_type": "Effect Monster",
                    },
                },
                {
                    "quantity": 3,
                    "card": {
                        "archetype": "Sky Striker",
                        "card_type": "Spell Card",
                    },
                },
                {
                    "quantity": 1,
                    "card": {"archetype": "", "card_type": "Trap Card"},
                },
            ]
        })

        self.assertEqual(result["total_cards"], 6)
        self.assertEqual(
            [(item["label"], item["count"]) for item in result["archetypes"]],
            [("Sky Striker", 5), ("ไม่มี Archetype", 1)],
        )
        self.assertEqual(
            [(item["label"], item["count"]) for item in result["card_types"]],
            [("Monsters", 2), ("Spells", 3), ("Traps", 1)],
        )


class DeckBreakdownPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="owner", password="password123"
        )
        card = Card.objects.create(
            card_id=71001,
            name="Chart Dragon",
            card_type="Effect Monster",
            archetype="Chart",
        )
        cls.deck = Deck.objects.create(
            owner=cls.owner,
            name="Chart Deck",
            is_public=True,
        )
        DeckCard.objects.create(
            deck=cls.deck,
            card=card,
            section="MAIN",
            quantity=2,
        )

    def test_public_read_only_deck_shows_breakdown(self):
        response = self.client.get(
            reverse("decks_page:builder", args=[self.deck.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ภาพรวมสัดส่วนเด็ค")
        self.assertContains(response, "Archetype Breakdown")
        self.assertContains(response, "Card Type Breakdown")
        self.assertEqual(response.context["deck_breakdown"]["total_cards"], 2)

    def test_owner_deck_builder_does_not_show_breakdown(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("decks_page:builder", args=[self.deck.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["can_edit"])
        self.assertIsNone(response.context["deck_breakdown"])
        self.assertNotContains(response, "Card Type Breakdown")

