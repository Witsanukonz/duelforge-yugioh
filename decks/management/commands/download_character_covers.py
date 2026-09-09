from urllib.parse import urlparse
from urllib.request import Request, urlopen

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from decks.models import Deck


KONAMI_CHARACTER_BASE = (
    "https://www.konami.com/yugioh/duel_links/en/series/images/character/"
)

CHARACTER_COVERS = {
    "Akiza": KONAMI_CHARACTER_BASE + "5ds04.png",
    "Aoi": KONAMI_CHARACTER_BASE + "vrains04.png",
    "Aporia": KONAMI_CHARACTER_BASE + "5ds16.png",
    "Aster": KONAMI_CHARACTER_BASE + "gx03.png",
    "Atem": KONAMI_CHARACTER_BASE + "dm01.png",
    "Bakura": KONAMI_CHARACTER_BASE + "dm11.png",
    "Bastion": KONAMI_CHARACTER_BASE + "gx10.png",
    "Chazz": KONAMI_CHARACTER_BASE + "gx05.png",
    "Crow": KONAMI_CHARACTER_BASE + "5ds03.png",
    "Dark Jaden": KONAMI_CHARACTER_BASE + "gx55.png",
    "Ishizu": KONAMI_CHARACTER_BASE + "dm13.png",
    "Jack": KONAMI_CHARACTER_BASE + "5ds02.png",
    "Jaden": KONAMI_CHARACTER_BASE + "gx01.png",
    "Joey": KONAMI_CHARACTER_BASE + "dm03.png",
    "Kaiba": KONAMI_CHARACTER_BASE + "dm02.png",
    "Kaito": KONAMI_CHARACTER_BASE + "zexal07.png",
    "Leo": KONAMI_CHARACTER_BASE + "5ds05.png",
    "Luna": KONAMI_CHARACTER_BASE + "5ds06.png",
    "Mai": KONAMI_CHARACTER_BASE + "dm04.png",
    "Marik": KONAMI_CHARACTER_BASE + "dm10.png",
    "Pegasus": KONAMI_CHARACTER_BASE + "dm15.png",
    "Revolver": KONAMI_CHARACTER_BASE + "vrains05.png",
    "Yubel": KONAMI_CHARACTER_BASE + "gx09.png",
    "Yugi": KONAMI_CHARACTER_BASE + "dm06.png",
    "Yugo": KONAMI_CHARACTER_BASE + "arcv10.png",
    "Yuma": KONAMI_CHARACTER_BASE + "zexal01.png",
    "Yuri": KONAMI_CHARACTER_BASE + "arcv14.png",
    "Yusaku": KONAMI_CHARACTER_BASE + "vrains01.png",
    "Yusei": KONAMI_CHARACTER_BASE + "5ds01.png",
    "Yuto": KONAMI_CHARACTER_BASE + "arcv06.png",
    "Yuya": KONAMI_CHARACTER_BASE + "arcv01.png",
    "Z-ARC": (
        "https://static.wikia.nocookie.net/yugioh-arcv/images/1/1d/"
        "Zarc_139-00.png/revision/latest?format=original"
    ),
    "Zane": KONAMI_CHARACTER_BASE + "gx02.png",
}

ALLOWED_IMAGE_HOSTS = {"www.konami.com", "static.wikia.nocookie.net"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def character_slug(name):
    return name.lower().replace(" ", "-")


def sample_decks_for_character(name):
    return Deck.objects.filter(is_sample=True).filter(
        Q(name=name) | Q(name__startswith=f"{name} — ")
    )


def download_png(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_IMAGE_HOSTS:
        raise CommandError(f"Unsupported character image source: {url}")
    request = Request(url, headers={"User-Agent": "YuGiOhDeckBuilder/1.0"})
    with urlopen(request, timeout=30) as response:
        payload = response.read(MAX_IMAGE_BYTES + 1)
    if len(payload) > MAX_IMAGE_BYTES:
        raise CommandError(f"Character image is larger than 5 MB: {url}")
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise CommandError(f"Character image is not a PNG: {url}")
    return payload


class Command(BaseCommand):
    help = "Download local character covers for imported sample decks."

    def handle(self, *args, **options):
        downloaded = 0
        assigned = 0

        for character, url in CHARACTER_COVERS.items():
            decks = sample_decks_for_character(character)
            if not decks.exists():
                continue

            image_name = f"deck_covers/characters/{character_slug(character)}.png"
            if not default_storage.exists(image_name):
                saved_name = default_storage.save(image_name, ContentFile(download_png(url)))
                if saved_name != image_name:
                    raise CommandError(f"Could not save stable cover path: {image_name}")
                downloaded += 1

            assigned += decks.exclude(cover_image=image_name).update(cover_image=image_name)
            self.stdout.write(f"{character}: {decks.count()} deck(s)")

        self.stdout.write(
            self.style.SUCCESS(
                f"Character covers ready. Downloaded {downloaded}; assigned {assigned}."
            )
        )
