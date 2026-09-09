from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from decks.sample_decks import (
    DEFAULT_SAMPLE_DIRECTORY,
    SampleDeckImportError,
    SampleDeckImportResult,
    import_sample_deck,
    load_sample_metadata,
)


class Command(BaseCommand):
    help = "Import local .ydk files as idempotent system-owned sample decks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(DEFAULT_SAMPLE_DIRECTORY),
            help="Directory containing .ydk files and optional metadata.json.",
        )
        parser.add_argument(
            "--allow-missing",
            action="store_true",
            help="Import known cards even when some Card IDs are missing locally.",
        )

    def handle(self, *args, **options):
        directory = Path(options["path"]).resolve()
        if not directory.exists() or not directory.is_dir():
            raise CommandError(f"Sample deck directory does not exist: {directory}")
        try:
            metadata = load_sample_metadata(directory)
        except SampleDeckImportError as error:
            raise CommandError(str(error)) from error

        paths = sorted(directory.rglob("*.ydk"), key=lambda item: item.as_posix().lower())
        self.stdout.write(f"Found {len(paths)} sample deck file(s) in {directory}.")
        summary = {
            "CREATED": 0,
            "UPDATED": 0,
            "UNCHANGED": 0,
            "SKIPPED": 0,
            "ERROR": 0,
        }
        missing_ids = set()

        for index, path in enumerate(paths, start=1):
            try:
                result = import_sample_deck(
                    path,
                    directory=directory,
                    metadata=metadata,
                    allow_missing=options["allow_missing"],
                )
            except Exception as error:
                result = SampleDeckImportResult(
                    source=path.name,
                    name=path.stem,
                    status="ERROR",
                    messages=[str(error)],
                )
            summary[result.status] += 1
            missing_ids.update(result.missing_card_ids)
            totals = result.totals or {"MAIN": 0, "EXTRA": 0, "SIDE": 0}
            self.stdout.write(
                f"[{index:02d}/{len(paths):02d}] {result.name} "
                f"| Main {totals['MAIN']} | Extra {totals['EXTRA']} | Side {totals['SIDE']} "
                f"| {result.status}"
            )
            for card_id in result.missing_card_ids:
                self.stdout.write(self.style.WARNING(f"  Missing Card ID: {card_id}"))
            for message in result.messages:
                self.stdout.write(self.style.WARNING(f"  {message}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Sample deck import completed."))
        self.stdout.write(f"Created: {summary['CREATED']}")
        self.stdout.write(f"Updated: {summary['UPDATED']}")
        self.stdout.write(f"Unchanged: {summary['UNCHANGED']}")
        self.stdout.write(f"Skipped: {summary['SKIPPED']}")
        self.stdout.write(f"Errors: {summary['ERROR']}")
        self.stdout.write(f"Missing card IDs: {len(missing_ids)}")
