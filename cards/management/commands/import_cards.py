import requests

from django.core.management.base import BaseCommand, CommandError

from cards.models import Card


API_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"


class Command(BaseCommand):
    help = "Import all Yu-Gi-Oh cards from YGOPRODeck API"

    def handle(self, *args, **options):
        self.stdout.write("Downloading card database...")

        try:
            response = requests.get(API_URL, timeout=120)
            response.raise_for_status()
        except requests.RequestException as error:
            self.stderr.write(
                self.style.ERROR(
                    f"Failed to download card database: {error}"
                )
            )
            return

        try:
            data = response.json()
            cards = data.get("data", [])
        except ValueError as error:
            self.stderr.write(
                self.style.ERROR(
                    f"Invalid JSON response: {error}"
                )
            )
            return

        if not cards:
            self.stderr.write(
                self.style.ERROR(
                    "No card data found from API."
                )
            )
            return

        total_cards = len(cards)

        self.stdout.write(
            self.style.SUCCESS(
                f"Found {total_cards} cards"
            )
        )

        existing_ids = set(Card.objects.values_list("card_id", flat=True))
        card_objects = []
        error_count = 0

        for index, card in enumerate(cards, start=1):
            try:
                card_id = card.get("id")

                if not card_id:
                    error_count += 1
                    self.stderr.write(
                        self.style.WARNING(
                            f"Skipped #{index}: missing card ID"
                        )
                    )
                    continue

                images = card.get("card_images") or []

                image_url = ""
                image_url_small = ""

                if images:
                    first_image = images[0] or {}

                    image_url = (
                        first_image.get("image_url") or ""
                    )

                    image_url_small = (
                        first_image.get("image_url_small") or ""
                    )

                card_objects.append(
                    Card(
                        card_id=card_id,
                        name=card.get("name") or "",
                        card_type=card.get("type") or "",
                        frame_type=card.get("frameType") or "",
                        description=card.get("desc") or "",
                        race=card.get("race") or "",
                        attribute=card.get("attribute") or "",
                        archetype=card.get("archetype") or "",
                        atk=card.get("atk"),
                        defense=card.get("def"),
                        level=card.get("level"),
                        image_url=image_url,
                        image_url_small=image_url_small,
                    )
                )

            except Exception as error:
                error_count += 1

                self.stderr.write(
                    self.style.ERROR(
                        f"Error #{index} "
                        f"{card.get('name') or 'Unknown'}: {error}"
                    )
                )

                continue

        if not card_objects:
            raise CommandError("No valid card data was available to import.")

        update_fields = [
            "name",
            "card_type",
            "frame_type",
            "description",
            "race",
            "attribute",
            "archetype",
            "atk",
            "defense",
            "level",
            "image_url",
            "image_url_small",
        ]
        Card.objects.bulk_create(
            card_objects,
            batch_size=1_000,
            update_conflicts=True,
            unique_fields=["card_id"],
            update_fields=update_fields,
        )

        imported_ids = {card.card_id for card in card_objects}
        updated_count = len(imported_ids & existing_ids)
        created_count = len(imported_ids - existing_ids)
        self.stdout.write(f"Processed {len(card_objects)}/{total_cards}")

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "Import completed!"
            )
        )

        self.stdout.write(
            f"Created: {created_count}"
        )

        self.stdout.write(
            f"Updated: {updated_count}"
        )

        self.stdout.write(
            f"Errors: {error_count}"
        )

        self.stdout.write(
            f"Total cards in database: {Card.objects.count()}"
        )
        
