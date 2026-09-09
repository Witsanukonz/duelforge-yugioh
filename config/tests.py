from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.staticfiles import finders
from django.test import SimpleTestCase, override_settings
from django.urls import reverse


class TailwindIntegrationTests(SimpleTestCase):
    def test_compiled_tailwind_theme_is_discoverable(self):
        stylesheet = finders.find("css/dist/styles.css")

        self.assertIsNotNone(stylesheet)
        css = Path(stylesheet).read_text(encoding="utf-8")
        self.assertIn(".bg-arcane-ink", css)
        self.assertIn(".min-h-screen", css)
        self.assertIn(".focus-visible\\:ring-2", css)
        self.assertIn(".hover\\:shadow-lg", css)

    def test_real_forms_cover_six_tailwind_styled_control_types(self):
        project_root = Path(__file__).resolve().parent.parent
        templates = {
            "deck": (project_root / "templates/decks/deck_builder.html").read_text(
                encoding="utf-8"
            ),
            "cards": (project_root / "templates/cards/card_list.html").read_text(
                encoding="utf-8"
            ),
            "collection": (
                project_root / "templates/collects/collection_list.html"
            ).read_text(encoding="utf-8"),
        }

        expected_controls = {
            "text": ('type="text"', templates["deck"]),
            "textarea": ("<textarea", templates["deck"]),
            "checkbox": ('type="checkbox"', templates["deck"]),
            "select": ("<select", templates["cards"]),
            "search": ('type="search"', templates["cards"]),
            "number": ('type="number"', templates["collection"]),
        }
        for control_name, (markup, template) in expected_controls.items():
            with self.subTest(control=control_name):
                element = template[template.index(markup) - 300 : template.index(markup) + 300]
                self.assertIn("focus-visible:ring-2", element)


class AudioTrackTests(SimpleTestCase):
    def test_audio_endpoint_supports_byte_ranges(self):
        with TemporaryDirectory() as temporary_directory:
            audio_root = Path(temporary_directory)
            (audio_root / "gods-anger.mp3").write_bytes(b"0123456789")

            with override_settings(SITE_AUDIO_ROOT=audio_root):
                response = self.client.get(
                    reverse("site_audio", kwargs={"filename": "gods-anger.mp3"}),
                    headers={"Range": "bytes=2-5"},
                )

            self.assertEqual(response.status_code, 206)
            self.assertEqual(response["Accept-Ranges"], "bytes")
            self.assertEqual(response["Content-Range"], "bytes 2-5/10")
            self.assertEqual(response["Content-Length"], "4")
            self.assertEqual(b"".join(response.streaming_content), b"2345")

    def test_audio_endpoint_rejects_unknown_filename(self):
        response = self.client.get(
            reverse("site_audio", kwargs={"filename": "not-allowed.mp3"})
        )

        self.assertEqual(response.status_code, 404)
