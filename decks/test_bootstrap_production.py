from unittest.mock import patch

from django.core.management.base import CommandError
from django.test import SimpleTestCase

from decks.management.commands.bootstrap_production import Command


class BootstrapProductionCommandTests(SimpleTestCase):
    @patch("decks.management.commands.bootstrap_production.Deck.objects.filter")
    @patch("decks.management.commands.bootstrap_production.BanList.objects.filter")
    @patch("decks.management.commands.bootstrap_production.call_command")
    @patch("decks.management.commands.bootstrap_production.Card.objects.count")
    def test_skips_public_seed_data_when_production_is_ready(
        self, card_count, call_command, banlist_filter, deck_filter
    ):
        card_count.return_value = 14_520
        banlist_filter.return_value.exists.return_value = True
        deck_filter.return_value.count.return_value = 48

        Command().handle()

        call_command.assert_not_called()

    @patch("decks.management.commands.bootstrap_production.call_command")
    @patch("decks.management.commands.bootstrap_production.Card.objects.count")
    def test_stops_when_card_download_does_not_populate_database(
        self, card_count, call_command
    ):
        card_count.side_effect = [0, 0]

        with self.assertRaises(CommandError):
            Command().handle()

        call_command.assert_called_once_with("import_cards")

    @patch("decks.management.commands.bootstrap_production.Deck.objects.filter")
    @patch("decks.management.commands.bootstrap_production.BanList.objects.filter")
    @patch("decks.management.commands.bootstrap_production.call_command")
    @patch("decks.management.commands.bootstrap_production.Card.objects.count")
    def test_refresh_reloads_all_public_seed_data(
        self, card_count, call_command, banlist_filter, deck_filter
    ):
        card_count.return_value = 14_520

        Command().handle(refresh=True)

        self.assertEqual(call_command.call_count, 5)
        call_command.assert_any_call("import_cards")
        call_command.assert_any_call("import_banlist", "tcg")
        call_command.assert_any_call("import_banlist", "ocg")
        call_command.assert_any_call("import_sample_decks", "--allow-missing")
        call_command.assert_any_call("download_character_covers")
        banlist_filter.assert_not_called()
        deck_filter.assert_not_called()
