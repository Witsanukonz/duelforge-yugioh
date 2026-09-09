from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase

from cards.models import Card


class ImportCardsCommandTests(TestCase):
    @patch("cards.management.commands.import_cards.requests.get")
    def test_bulk_import_creates_updates_and_preserves_thai_text(self, get):
        Card.objects.create(
            card_id=100,
            name="Old name",
            card_type="Normal Monster",
            description_th="ข้อความเดิม",
        )
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "data": [
                {
                    "id": 100,
                    "name": "Updated card",
                    "type": "Effect Monster",
                    "frameType": "effect",
                    "desc": "Updated effect",
                    "race": "Dragon",
                    "attribute": "LIGHT",
                    "atk": 2500,
                    "def": 2000,
                    "level": 8,
                    "card_images": [
                        {
                            "image_url": "https://example.com/100.jpg",
                            "image_url_small": "https://example.com/100-small.jpg",
                        }
                    ],
                },
                {
                    "id": 200,
                    "name": "New card",
                    "type": "Spell Card",
                    "frameType": "spell",
                    "desc": "New effect",
                    "race": "Normal",
                    "card_images": [],
                },
            ]
        }
        get.return_value = response
        output = StringIO()

        call_command("import_cards", stdout=output)

        self.assertEqual(Card.objects.count(), 2)
        updated = Card.objects.get(card_id=100)
        self.assertEqual(updated.name, "Updated card")
        self.assertEqual(updated.description_th, "ข้อความเดิม")
        self.assertEqual(Card.objects.get(card_id=200).name, "New card")
        self.assertIn("Created: 1", output.getvalue())
        self.assertIn("Updated: 1", output.getvalue())

