from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from banlists.models import BanList
from cards.models import Card
from decks.models import Deck


MINIMUM_CARD_COUNT = 10_000
MINIMUM_SAMPLE_DECK_COUNT = 48


class Command(BaseCommand):
    help = (
        "Seed a new production database with public cards, ban lists, and "
        "read-only sample decks without copying local user accounts."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Refresh public seed data even when production is already ready.",
        )

    def handle(self, *args, **options):
        refresh = options.get("refresh", False)
        if refresh or Card.objects.count() < MINIMUM_CARD_COUNT:
            call_command("import_cards")

        card_count = Card.objects.count()
        if card_count < MINIMUM_CARD_COUNT:
            raise CommandError(
                "Card bootstrap did not complete; refusing to publish an empty archive."
            )

        if refresh or not BanList.objects.filter(format="TCG").exists():
            call_command("import_banlist", "tcg")
        if refresh or not BanList.objects.filter(format="OCG").exists():
            call_command("import_banlist", "ocg")

        if refresh or Deck.objects.filter(is_sample=True).count() < MINIMUM_SAMPLE_DECK_COUNT:
            call_command("import_sample_decks", "--allow-missing")
            call_command("download_character_covers")

        self.stdout.write(
            self.style.SUCCESS(
                f"Production public data is ready with {card_count} cards."
            )
        )
