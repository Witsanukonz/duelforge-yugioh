import io
import json
import zipfile
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import ANY, patch

from django.core.management import call_command
from django.test import SimpleTestCase

from .sample_downloader import (
    LICENSE_STATUS,
    SOURCE_LOCAL_ROOT,
    SOURCE_REPOSITORY,
    SampleDeckDownloadError,
    SampleDeckDownloadResult,
    download_sample_decks,
    inspect_source_archive,
)


VALID_YDK = b"#created by tests\n#main\n100\n#extra\n!side\n"


def make_archive(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for relative_path, content in files.items():
            archive.writestr(f"yugi-decks-main/{relative_path}", content)
    return stream.getvalue()


class SampleDeckDownloaderTests(SimpleTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_archive_inspection_selects_supported_eras_and_excludes_rush(self):
        archive = make_archive({
            "decks/dm/Atem.ydk": VALID_YDK,
            "decks/gx/Jaden.ydk": VALID_YDK,
            "decks/5ds/Yusei.ydk": VALID_YDK,
            "decks/zexal/Yuma.ydk": VALID_YDK,
            "decks/arcv/Yuya.ydk": VALID_YDK,
            "decks/vrains/Yusaku.ydk": VALID_YDK,
            "decks/rush/Yuga.ydk": VALID_YDK,
            "decks/sevens/Romin.ydk": VALID_YDK,
            "notes/not-a-deck.ydk": VALID_YDK,
        })

        selected, found, rush, unsupported = inspect_source_archive(archive)

        self.assertEqual(found, 8)
        self.assertEqual(len(selected), 6)
        self.assertEqual(rush, 1)
        self.assertEqual(unsupported, 1)
        self.assertEqual(
            {deck.era_folder for deck in selected},
            {"dm", "gx", "5ds", "zexal", "arcv", "vrains"},
        )

    def test_download_writes_deck_metadata_and_attributed_manifest(self):
        archive = make_archive({"decks/dm/Atem (DSOD).ydk": VALID_YDK})

        result = download_sample_decks(self.root, archive_bytes=archive)

        deck_path = self.root / SOURCE_LOCAL_ROOT / "dm" / "atem-dsod.ydk"
        metadata = json.loads((self.root / "metadata.json").read_text(encoding="utf-8"))
        manifest = json.loads(
            (self.root / "source_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(result.downloaded, 1)
        self.assertEqual(deck_path.read_bytes(), VALID_YDK)
        self.assertEqual(metadata["atem-dsod"]["name"], "Atem — DSOD")
        self.assertEqual(metadata["atem-dsod"]["era"], "DM")
        self.assertEqual(metadata["atem-dsod"]["source_path"], "decks/dm/Atem (DSOD).ydk")
        self.assertEqual(manifest["source_repository"], SOURCE_REPOSITORY)
        self.assertEqual(manifest["license_status"], LICENSE_STATUS)

    def test_second_download_is_unchanged_and_keeps_same_path(self):
        archive = make_archive({"decks/gx/Jaden.ydk": VALID_YDK})

        first = download_sample_decks(self.root, archive_bytes=archive)
        second = download_sample_decks(self.root, archive_bytes=archive)

        manifest = json.loads(
            (self.root / "source_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(first.downloaded, 1)
        self.assertEqual(second.unchanged, 1)
        self.assertEqual(len(list(self.root.rglob("*.ydk"))), 1)
        self.assertEqual(
            manifest["files"]["decks/gx/Jaden.ydk"]["local_path"],
            f"{SOURCE_LOCAL_ROOT}/gx/jaden.ydk",
        )

    def test_changed_source_updates_manifest_owned_file(self):
        first_archive = make_archive({"decks/dm/Atem.ydk": VALID_YDK})
        changed = VALID_YDK.replace(b"100", b"200")
        second_archive = make_archive({"decks/dm/Atem.ydk": changed})
        download_sample_decks(self.root, archive_bytes=first_archive)

        result = download_sample_decks(self.root, archive_bytes=second_archive)

        deck_path = self.root / SOURCE_LOCAL_ROOT / "dm" / "atem.ydk"
        self.assertEqual(result.updated, 1)
        self.assertEqual(deck_path.read_bytes(), changed)

    def test_existing_user_file_is_not_overwritten_or_deleted(self):
        user_path = self.root / SOURCE_LOCAL_ROOT / "dm" / "atem.ydk"
        user_path.parent.mkdir(parents=True)
        user_path.write_bytes(b"#main\n999\n")
        separate_user_path = self.root / "my-personal-deck.ydk"
        separate_user_path.write_bytes(b"#main\n777\n")
        archive = make_archive({"decks/dm/Atem.ydk": VALID_YDK})

        result = download_sample_decks(self.root, archive_bytes=archive)

        self.assertEqual(result.downloaded, 1)
        self.assertEqual(user_path.read_bytes(), b"#main\n999\n")
        self.assertEqual(separate_user_path.read_bytes(), b"#main\n777\n")
        self.assertEqual(len(list((self.root / SOURCE_LOCAL_ROOT / "dm").glob("*.ydk"))), 2)

    def test_slug_collision_gets_deterministic_hash_suffix(self):
        archive = make_archive({
            "decks/dm/A B.ydk": VALID_YDK,
            "decks/dm/A-B.ydk": VALID_YDK,
        })

        download_sample_decks(self.root, archive_bytes=archive)
        first_paths = sorted(path.name for path in self.root.rglob("*.ydk"))
        download_sample_decks(self.root, archive_bytes=archive)
        second_paths = sorted(path.name for path in self.root.rglob("*.ydk"))

        self.assertEqual(first_paths, second_paths)
        self.assertEqual(len(first_paths), 2)
        self.assertIn("a-b.ydk", first_paths)
        self.assertTrue(any(name.startswith("a-b-") for name in first_paths))

    def test_network_failure_leaves_existing_files_untouched(self):
        user_path = self.root / "my-deck.ydk"
        user_path.write_bytes(VALID_YDK)

        def failing_fetcher(**kwargs):
            raise SampleDeckDownloadError("offline")

        with self.assertRaisesMessage(SampleDeckDownloadError, "offline"):
            download_sample_decks(self.root, fetcher=failing_fetcher)

        self.assertEqual(user_path.read_bytes(), VALID_YDK)
        self.assertFalse((self.root / "source_manifest.json").exists())

    def test_malformed_supported_file_is_reported_and_not_written(self):
        archive = make_archive({"decks/dm/Broken.ydk": b"#main\nnot-an-id\n"})

        result = download_sample_decks(self.root, archive_bytes=archive)

        self.assertEqual(len(result.failed), 1)
        self.assertIn("invalid card ID", result.failed[0]["reason"])
        self.assertFalse(any(self.root.rglob("*.ydk")))

    def test_unsafe_previous_manifest_path_is_rejected_without_escape(self):
        (self.root / "source_manifest.json").write_text(json.dumps({
            "files": {
                "decks/dm/Atem.ydk": {"local_path": "../escaped.ydk"}
            }
        }), encoding="utf-8")
        archive = make_archive({"decks/dm/Atem.ydk": VALID_YDK})

        result = download_sample_decks(self.root, archive_bytes=archive)

        self.assertEqual(len(result.failed), 1)
        self.assertFalse((self.root.parent / "escaped.ydk").exists())


class SampleDeckDownloaderCommandTests(SimpleTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    @patch("decks.management.commands.download_sample_decks.download_sample_decks")
    def test_command_reports_counts_without_implicit_import(self, downloader):
        downloader.return_value = SampleDeckDownloadResult(
            upstream_found=52,
            selected=49,
            rush_excluded=3,
            downloaded=49,
        )
        output = StringIO()

        with patch("decks.management.commands.download_sample_decks.call_command") as nested:
            call_command("download_sample_decks", path=str(self.root), stdout=output)

        self.assertIn("Supported selected: 49", output.getvalue())
        self.assertIn("Rush excluded: 3", output.getvalue())
        nested.assert_not_called()

    @patch("decks.management.commands.download_sample_decks.download_sample_decks")
    def test_import_flag_explicitly_runs_existing_importer(self, downloader):
        downloader.return_value = SampleDeckDownloadResult()
        output = StringIO()

        with patch("decks.management.commands.download_sample_decks.call_command") as nested:
            call_command(
                "download_sample_decks",
                path=str(self.root),
                run_import=True,
                stdout=output,
            )

        nested.assert_called_once_with(
            "import_sample_decks", path=str(self.root.resolve()), stdout=ANY
        )
