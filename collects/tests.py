import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cards.models import Card

from .models import Collection


class CollectionApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="collector", password="password123"
        )
        cls.other_user = get_user_model().objects.create_user(
            username="other", password="password123"
        )
        cls.card = Card.objects.create(
            card_id=1001, name="Collected Card", card_type="Monster"
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_authentication_is_required(self):
        self.client.logout()
        response = self.client.get(reverse("collects:list"))
        self.assertEqual(response.status_code, 401)

    def test_create_filter_update_and_delete_collection_item(self):
        create = self.client.post(
            reverse("collects:list"),
            data=json.dumps({
                "card_id": self.card.card_id,
                "quantity": 2,
                "condition": "NM",
                "is_favorite": True,
            }),
            content_type="application/json",
        )
        self.assertEqual(create.status_code, 201)
        item_id = create.json()["collection_item"]["id"]

        listing = self.client.get(reverse("collects:list"), {"favorite": "true"})
        self.assertEqual(listing.json()["pagination"]["total"], 1)

        update = self.client.patch(
            reverse("collects:detail", args=[item_id]),
            data=json.dumps({"quantity": 4, "note": "Binder one"}),
            content_type="application/json",
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.json()["collection_item"]["quantity"], 4)

        delete = self.client.delete(reverse("collects:detail", args=[item_id]))
        self.assertEqual(delete.status_code, 204)
        self.assertFalse(Collection.objects.filter(pk=item_id).exists())

    def test_duplicate_card_returns_conflict(self):
        Collection.objects.create(user=self.user, card=self.card)
        response = self.client.post(
            reverse("collects:list"),
            data=json.dumps({"card_id": self.card.card_id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)

    def test_other_users_item_is_hidden(self):
        item = Collection.objects.create(user=self.other_user, card=self.card)
        response = self.client.get(reverse("collects:detail", args=[item.pk]))
        self.assertEqual(response.status_code, 404)

    def test_collection_page_renders_owned_items(self):
        Collection.objects.create(user=self.user, card=self.card, quantity=2)
        response = self.client.get(reverse("collects_page:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Collected Card")
        self.assertContains(response, "Total copies")

    def test_collection_page_is_paginated_twenty_four_per_page(self):
        cards = Card.objects.bulk_create([
            Card(
                card_id=94000 + index,
                name=f"Collected Page Card {index:02d}",
                card_type="Monster",
            )
            for index in range(25)
        ])
        Collection.objects.bulk_create([
            Collection(user=self.user, card=card)
            for card in cards
        ])

        response = self.client.get(reverse("collects_page:list"), {"page": 2})

        self.assertEqual(response.context["page_obj"].paginator.count, 25)
        self.assertEqual(len(response.context["page_obj"]), 1)
        self.assertContains(response, "Page 2")
