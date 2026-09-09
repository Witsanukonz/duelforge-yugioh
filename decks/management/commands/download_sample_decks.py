from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from decks.sample_decks import DEFAULT_SAMPLE_DIRECTORY
from decks.sample_downloader import SampleDeckDownloadError, download_sample_decks


class Command(BaseCommand):
    help = "Download supported character .ydk sources into the local sample library."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(DEFAULT_SAMPLE_DIRECTORY),
            help="Local sample_decks directory.",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=60,
            help="Network timeout in seconds.",
        )
        parser.add_argument(
            "--import",
            action="store_true",
            dest="run_import",
            help="Run the existing import_sample_decks command after download.",
        )

    def handle(self, *args, **options):
        directory = Path(options["path"]).resolve()
        try:
            result = download_sample_decks(
                directory,
                timeout=max(1, options["timeout"]),
            )
        except SampleDeckDownloadError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(f"Upstream .ydk found: {result.upstream_found}")
        self.stdout.write(f"Supported selected: {result.selected}")
        self.stdout.write(f"Rush excluded: {result.rush_excluded}")
        self.stdout.write(f"Unsupported excluded: {result.unsupported_excluded}")
        self.stdout.write(f"Downloaded: {result.downloaded}")
        self.stdout.write(f"Updated: {result.updated}")
        self.stdout.write(f"Unchanged: {result.unchanged}")
        self.stdout.write(f"Failed: {len(result.failed)}")
        for failure in result.failed:
            self.stdout.write(self.style.WARNING(
                f"  {failure['source_path']}: {failure['reason']}"
            ))

        if options["run_import"]:
            self.stdout.write("")
            self.stdout.write("Running existing import_sample_decks...")
            call_command("import_sample_decks", path=str(directory), stdout=self.stdout)
