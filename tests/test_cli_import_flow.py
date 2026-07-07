from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apple_photos_to_immich.config import Config


class CliImportFlowTests(unittest.TestCase):
    def test_import_assets_waits_by_default_without_running_make_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = Config(
                immich_server="https://example.com",
                immich_api_key="secret",
                photos_library="/tmp/library.photoslibrary",
                export_dir=root / "export",
                meta_dir=root / "meta",
                album_prefix="Apple Photos",
            )

            import apple_photos_to_immich.cli as cli

            called: list[str] = []
            originals = {
                "find_config_file": cli.find_config_file,
                "load_config": cli.load_config,
                "setup_logging": cli.setup_logging,
                "import_assets": cli.import_assets,
                "wait_for_immich": cli.wait_for_immich,
                "make_album_map": cli.make_album_map,
            }
            cli.find_config_file = lambda path: root / "config.toml"
            cli.load_config = lambda path: config
            cli.setup_logging = lambda *args, **kwargs: object()
            cli.import_assets = lambda *args, **kwargs: called.append("import-assets") or 0
            cli.wait_for_immich = lambda *args, **kwargs: called.append("wait-for-immich") or 0
            cli.make_album_map = lambda *args, **kwargs: called.append("make-map") or 0
            try:
                exit_code = cli.main(["import-assets"])
            finally:
                for name, original in originals.items():
                    setattr(cli, name, original)

            self.assertEqual(exit_code, 0)
            self.assertEqual(called, ["import-assets", "wait-for-immich"])

    def test_import_assets_no_wait_skips_wait_for_immich(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = Config(
                immich_server="https://example.com",
                immich_api_key="secret",
                photos_library="/tmp/library.photoslibrary",
                export_dir=root / "export",
                meta_dir=root / "meta",
                album_prefix="Apple Photos",
            )

            import apple_photos_to_immich.cli as cli

            called: list[str] = []
            originals = {
                "find_config_file": cli.find_config_file,
                "load_config": cli.load_config,
                "setup_logging": cli.setup_logging,
                "import_assets": cli.import_assets,
                "wait_for_immich": cli.wait_for_immich,
            }
            cli.find_config_file = lambda path: root / "config.toml"
            cli.load_config = lambda path: config
            cli.setup_logging = lambda *args, **kwargs: object()
            cli.import_assets = lambda *args, **kwargs: called.append("import-assets") or 0
            cli.wait_for_immich = lambda *args, **kwargs: called.append("wait-for-immich") or 0
            try:
                exit_code = cli.main(["import-assets", "--no-wait"])
            finally:
                for name, original in originals.items():
                    setattr(cli, name, original)

            self.assertEqual(exit_code, 0)
            self.assertEqual(called, ["import-assets"])


if __name__ == "__main__":
    unittest.main()
