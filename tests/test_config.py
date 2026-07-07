from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apple_photos_to_immich.config import find_config_file, load_config


class ConfigTests(unittest.TestCase):
    def test_load_config_reads_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.toml"
            config_path.write_text(
                """
[immich]
server = "https://example.com"
api_key = "secret"
skip_verify_ssl = true

[photos]
library = "/Users/test/Pictures/Photos Library.photoslibrary"
album_prefix = "My Import"

[paths]
export_dir = "./export"
meta_dir = "./meta"
""".strip(),
                encoding="utf-8",
            )

            config = load_config(config_path)

            self.assertEqual(config.immich_server, "https://example.com")
            self.assertTrue(config.skip_verify_ssl)
            self.assertEqual(config.album_prefix, "My Import")
            self.assertEqual(config.export_dir, (config_path.parent / "export").resolve())
            self.assertEqual(config.meta_dir, (config_path.parent / "meta").resolve())

    def test_find_config_file_searches_parents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "a" / "b"
            nested.mkdir(parents=True)
            (root / "config.toml").write_text(
                """
[immich]
server = "https://example.com"
api_key = "secret"

[photos]
library = "/Users/test/Pictures/Photos Library.photoslibrary"
album_prefix = "My Import"

[paths]
export_dir = "./export"
meta_dir = "./meta"
""".strip(),
                encoding="utf-8",
            )

            found = find_config_file(start_dir=nested)
            self.assertEqual(found.resolve(), (root / "config.toml").resolve())


if __name__ == "__main__":
    unittest.main()
