from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import app_config


class AppConfigMigrationTests(unittest.TestCase):
    def test_wordpress_database_credentials_are_atomically_remapped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "wp-config.php"
            path.write_text(
                "<?php\n"
                "define('DB_NAME', 'old_db');\n"
                "define('DB_USER', 'old_user');\n"
                "define('DB_PASSWORD', 'old_pass');\n",
                encoding="utf-8",
            )
            app_config.rewrite_wordpress_config(
                path, "newdb", "newuser", "p@ss'word"
            )
            text = path.read_text(encoding="utf-8")
            self.assertIn("define('DB_NAME', 'newdb');", text)
            self.assertIn("define('DB_USER', 'newuser');", text)
            self.assertIn("p@ss\\'word", text)
            self.assertNotIn("old_pass", text)

    def test_dotenv_database_triplet_and_site_url_are_remapped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / ".env"
            path.write_text(
                "DB_DATABASE=old_db\n"
                "DB_USERNAME='old_user'\n"
                'DB_PASSWORD="old pass"\n'
                "APP_URL=https://old.example.com\n",
                encoding="utf-8",
            )
            changed = app_config.rewrite_dotenv(
                path,
                "newdb",
                "newuser",
                "new pass",
                "old.example.com",
                "new.example.com",
            )
            self.assertTrue(changed)
            text = path.read_text(encoding="utf-8")
            self.assertIn("DB_DATABASE=newdb", text)
            self.assertIn("DB_USERNAME='newuser'", text)
            self.assertIn('DB_PASSWORD="new pass"', text)
            self.assertIn("APP_URL=https://new.example.com", text)

    def test_database_url_is_percent_encoded_and_preserves_scheme_host(self) -> None:
        value = app_config._rewrite_database_url(
            "mysql://old:old@127.0.0.1:3306/old_db?charset=utf8mb4",
            "new db",
            "new user",
            "p@ss:/word",
        )
        self.assertTrue(value.startswith("mysql://new%20user:p%40ss%3A%2Fword@127.0.0.1:3306/"))
        self.assertIn("new%20db", value)
        self.assertTrue(value.endswith("?charset=utf8mb4"))

    def test_unknown_application_config_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config.php").write_text("<?php\n", encoding="utf-8")
            with self.assertRaises(app_config.AppConfigError):
                app_config.rewrite_application_database_config(
                    root,
                    "old.example.com",
                    "new.example.com",
                    "newdb",
                    "newuser",
                    "newpass",
                )


if __name__ == "__main__":
    unittest.main()
