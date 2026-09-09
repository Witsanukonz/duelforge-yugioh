import os

import django
from django.core.management import call_command


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    # Normal requests use Neon's pooled DATABASE_URL. Schema and seed work must
    # use the direct endpoint to avoid PgBouncer transaction-mode limitations.
    direct_database_url = os.environ.get("DATABASE_URL_UNPOOLED")
    if direct_database_url:
        os.environ["DATABASE_URL"] = direct_database_url

    django.setup()
    call_command("migrate", interactive=False)
    call_command("bootstrap_production")


if __name__ == "__main__":
    main()
