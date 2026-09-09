from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from banlists.services import BanListImportError, import_banlist_file


class Command(BaseCommand):
    help = "Import a local TCG or OCG ban list JSON snapshot."

    def add_arguments(self, parser):
        parser.add_argument(
            "snapshot",
            help="Path to a snapshot JSON file, or the alias 'tcg'/'ocg'.",
        )

    def handle(self, *args, **options):
        snapshot = options["snapshot"]
        if snapshot.lower() in {"tcg", "ocg"}:
            filename = f"{snapshot.lower()}_current.json"
            snapshot = Path(__file__).resolve().parents[2] / "data" / filename

        try:
            report = import_banlist_file(snapshot)
        except BanListImportError as error:
            raise CommandError(str(error)) from error

        banlist = report["banlist"]
        action = "Created" if report["created"] else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} {banlist.format} Ban List"))
        self.stdout.write(f"Effective date: {banlist.effective_date.isoformat()}")
        self.stdout.write(f"Total cards: {report['total_cards']}")
        self.stdout.write(f"Forbidden: {report['forbidden']}")
        self.stdout.write(f"Limited: {report['limited']}")
        self.stdout.write(f"Semi-Limited: {report['semi_limited']}")
        self.stdout.write(f"Matched cards: {report['matched_cards']}")
        missing = report["missing_card_ids"]
        self.stdout.write(
            "Missing card IDs: " + (", ".join(map(str, missing)) if missing else "0")
        )
