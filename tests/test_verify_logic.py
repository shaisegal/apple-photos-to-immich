from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from apple_photos_to_immich.commands import verify
from apple_photos_to_immich.config import Config


class StubClient:
    def __init__(self) -> None:
        self.albums = [
            {"albumName": "Apple Photos/Albums/Trip", "id": "album-1"},
        ]
        self.album_payloads = {
            "album-1": {
                "assets": [
                    {"id": "asset-1"},
                    {"id": "extra-asset"},
                ]
            }
        }

    def iter_all_assets(self) -> list[dict[str, str]]:
        return [
            {
                "id": "asset-1",
                "originalFileName": "AAAABBBB-1111-2222-3333-444455556666_IMG_1.JPG",
                "fileCreatedAt": "2024-01-02T10:00:00Z",
            }
        ]

    def get_albums(self) -> list[dict[str, str]]:
        return self.albums

    def get_album_assets(self, album_id: str) -> dict[str, list[dict[str, str]]]:
        return self.album_payloads[album_id]


class LoggerStub:
    def info(self, *args, **kwargs) -> None:
        return None

    def warning(self, *args, **kwargs) -> None:
        return None

    def error(self, *args, **kwargs) -> None:
        return None


class VerifyLogicTests(unittest.TestCase):
    def test_verify_report_contains_album_drift_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            meta_dir = Path(tmp) / "meta"
            meta_dir.mkdir(parents=True)
            album_map = {
                "assetCount": 2,
                "albumCount": 1,
                "albums": {
                    "Apple Photos/Albums/Trip": {
                        "title": "Apple Photos/Albums/Trip",
                        "assetUuids": [
                            "AAAABBBB-1111-2222-3333-444455556666",
                            "BBBBCCCC-1111-2222-3333-444455556666",
                        ],
                    }
                },
                "assets": {
                    "AAAABBBB-1111-2222-3333-444455556666": {
                        "originalFilename": "IMG_1.JPG",
                        "date": "2024-01-02 10:00:00",
                    },
                    "BBBBCCCC-1111-2222-3333-444455556666": {
                        "originalFilename": "IMG_2.JPG",
                        "date": "2024-01-03 10:00:00",
                    },
                },
            }
            (meta_dir / "album-map.json").write_text(json.dumps(album_map), encoding="utf-8")

            config = Config(
                immich_server="https://example.com",
                immich_api_key="secret",
                photos_library="/tmp/library.photoslibrary",
                export_dir=Path(tmp) / "export",
                meta_dir=meta_dir,
                album_prefix="Apple Photos",
            )

            import apple_photos_to_immich.commands as commands

            original = commands._make_client
            commands._make_client = lambda config, logger: StubClient()
            try:
                exit_code = verify(config, LoggerStub())
            finally:
                commands._make_client = original

            report = json.loads(config.verify_report_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 2)
            self.assertEqual(report["albumsPresentInImmich"], 1)
            self.assertEqual(report["albumsWithMissingAssets"], 0)
            self.assertEqual(report["albumsWithExtraAssets"], 1)
            album_stat = report["albumStats"][0]
            self.assertEqual(album_stat["missingAssetIdCount"], 0)
            self.assertEqual(album_stat["extraAssetIdCount"], 1)
            self.assertEqual(album_stat["unmatchedUuidCount"], 1)


if __name__ == "__main__":
    unittest.main()
