import time
from pathlib import Path

import requests

from django.conf import settings
from django.core.management.base import BaseCommand

from cards.models import Card


class Command(BaseCommand):
    help = "Download full-size Yu-Gi-Oh card images"

    def handle(self, *args, **options):

        # media/cards/
        output_dir = Path(settings.MEDIA_ROOT) / "cards"

        # ถ้ายังไม่มี folder ให้สร้างให้อัตโนมัติ
        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        # เอาเฉพาะ Card ที่มี image_url
        cards = Card.objects.exclude(
            image_url=""
        ).order_by("id")

        total = cards.count()

        downloaded = 0
        skipped = 0
        errors = 0

        self.stdout.write(
            f"Found {total} cards with image URLs"
        )

        session = requests.Session()

        session.headers.update({
            "User-Agent": "YuGiOhDeckBuilder/1.0"
        })

        for index, card in enumerate(
            cards,
            start=1
        ):

            # ชื่อไฟล์ใช้ card_id
            file_path = (
                output_dir /
                f"{card.card_id}.jpg"
            )

            # --------------------------
            # มีไฟล์แล้ว = ข้าม
            # --------------------------

            if (
                file_path.exists()
                and file_path.stat().st_size > 0
            ):
                skipped += 1

                if index % 100 == 0:
                    self.print_progress(
                        index,
                        total,
                        downloaded,
                        skipped,
                        errors
                    )

                continue

            # --------------------------
            # Download
            # --------------------------

            try:

                response = session.get(
                    card.image_url,
                    timeout=60
                )

                response.raise_for_status()

                # ตรวจว่า server ส่งรูปจริง
                content_type = (
                    response.headers.get(
                        "Content-Type",
                        ""
                    )
                )

                if (
                    "image"
                    not in content_type.lower()
                ):
                    raise ValueError(
                        "Response is not an image"
                    )

                # เขียนรูปลง disk
                with open(
                    file_path,
                    "wb"
                ) as image_file:

                    image_file.write(
                        response.content
                    )

                downloaded += 1

            except Exception as error:

                errors += 1

                self.stderr.write(
                    self.style.ERROR(
                        f"[{index}/{total}] "
                        f"{card.name} "
                        f"({card.card_id}) "
                        f"ERROR: {error}"
                    )
                )

            # แสดงสถานะทุก 100 ใบ
            if index % 100 == 0:

                self.print_progress(
                    index,
                    total,
                    downloaded,
                    skipped,
                    errors
                )

            # หน่วงการ request
            time.sleep(0.15)

        # --------------------------
        # สรุปผล
        # --------------------------

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "Image download completed!"
            )
        )

        self.stdout.write(
            f"Downloaded: {downloaded}"
        )

        self.stdout.write(
            f"Skipped: {skipped}"
        )

        self.stdout.write(
            f"Errors: {errors}"
        )

        self.stdout.write(
            f"Images directory: {output_dir}"
        )

    def print_progress(
        self,
        index,
        total,
        downloaded,
        skipped,
        errors
    ):

        self.stdout.write(
            f"Processed {index}/{total}"
            f" | Downloaded: {downloaded}"
            f" | Skipped: {skipped}"
            f" | Errors: {errors}"
        )