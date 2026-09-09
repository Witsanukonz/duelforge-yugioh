import os
from unittest.mock import call, patch

from django.test import SimpleTestCase

import build


class VercelBuildTests(SimpleTestCase):
    @patch("build.django.setup")
    @patch("build.call_command")
    def test_build_uses_direct_database_for_migrations_and_public_seed(
        self, command, django_setup
    ):
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://pooled/database",
                "DATABASE_URL_UNPOOLED": "postgresql://direct/database",
            },
        ):
            build.main()
            self.assertEqual(
                os.environ["DATABASE_URL"], "postgresql://direct/database"
            )

        self.assertEqual(
            command.call_args_list,
            [call("migrate", interactive=False), call("bootstrap_production")],
        )
        django_setup.assert_called_once_with()
