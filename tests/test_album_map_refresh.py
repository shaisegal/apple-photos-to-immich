from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from apple_photos_to_immich.config import Config
from apple_photos_to_immich.commands import apply_albums, verify


class LoggerStub:
    def info(self, *args, **kwargs) -> None:
        return None

    def warning(self, *args, **kwargs) -> None:
        return None

    def error(self, *args, **kwargs) -> None:
        return None


class StubClient:
    def iter_all_assets(self) -> list[dict[str, str]]:
        return []

    def get_albums(self) -> list[dict[str, str]]:
        return []

    def get_album_assets(self, album_id: str) -> dict[str, list[dict[str, str]]]:
        return {"assets": []}


class AlbumMapRefreshTests(unittest.TestCase):
    def test_apply_albums_generates_missing_album_map(self) -> None:
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
            config.meta_dir.mkdir(parents=True)

            import apple_photos_to_immich.commands as commands

            called: list[str] = []
            originals = {
                "make_album_map": commands.make_album_map,
                "_make_client": commands._make_client,
                "build_match_report": commands.build_match_report,
            }

            def fake_make_map(config, logger):
                called.append("make-map")
                config.album_map_path.write_text(
                    json.dumps({"albums": {}, "assets": {}}),
                    encoding="utf-8",
                )
                return 0

            commands.make_album_map = fake_make_map
            commands._make_client = lambda config, logger: StubClient()
            commands.build_match_report = lambda config, client, logger: {"uuidToAssetId": {}}
            try:
                exit_code = apply_albums(config, LoggerStub(), dry_run=True)
            finally:
                for name, original in originals.items():
                    setattr(commands, name, original)

            self.assertEqual(exit_code, 0)
            self.assertEqual(called, ["make-map"])

    def test_verify_regenerates_stale_album_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta_dir = root / "meta"
            export_dir = root / "export"
            meta_dir.mkdir(parents=True)
            export_dir.mkdir(parents=True)

            config = Config(
                immich_server="https://example.com",
                immich_api_key="secret",
                photos_library="/tmp/library.photoslibrary",
                export_dir=export_dir,
                meta_dir=meta_dir,
                album_prefix="Apple Photos",
            )

            config.album_map_path.write_text(
                json.dumps({"assetCount": 0, "albumCount": 0, "albums": {}, "assets": {}}),
                encoding="utf-8",
            )
            time.sleep(0.01)
            (export_dir / "newer.jpg").write_text("x", encoding="utf-8")

            import apple_photos_to_immich.commands as commands

            called: list[str] = []
            originals = {
                "make_album_map": commands.make_album_map,
                "_make_client": commands._make_client,
            }

            def fake_make_map(config, logger):
                called.append("make-map")
                config.album_map_path.write_text(
                    json.dumps({"assetCount": 0, "albumCount": 0, "albums": {}, "assets": {}}),
                    encoding="utf-8",
                )
                return 0

            commands.make_album_map = fake_make_map
            commands._make_client = lambda config, logger: StubClient()
            try:
                exit_code = verify(config, LoggerStub())
            finally:
                for name, original in originals.items():
                    setattr(commands, name, original)

            self.assertEqual(called, ["make-map"])
            self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
