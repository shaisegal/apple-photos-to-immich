from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from apple_photos_to_immich.commands import apply_albums, verify
from apple_photos_to_immich.config import Config


class LoggerStub:
    def info(self, *args, **kwargs) -> None:
        return None

    def warning(self, *args, **kwargs) -> None:
        return None

    def error(self, *args, **kwargs) -> None:
        return None


class RenameClient:
    def __init__(self) -> None:
        self.renames: list[tuple[str, str]] = []

    def iter_all_assets(self) -> list[dict[str, str]]:
        return []

    def get_albums(self) -> list[dict[str, str]]:
        return [{"albumName": "Apple Photos/Albums/Trip", "id": "album-1"}]

    def update_album(self, album_id: str, title: str) -> dict[str, str]:
        self.renames.append((album_id, title))
        return {"id": album_id, "albumName": title}

    def get_album_assets(self, album_id: str) -> dict[str, list[dict[str, str]]]:
        return {"assets": []}

    def add_assets_to_album(self, album_id: str, asset_ids: list[str]) -> None:
        return None

    def create_album(self, title: str) -> dict[str, str]:
        raise AssertionError("create_album should not be called when a legacy album can be renamed")


class VerifyClient:
    def __init__(self) -> None:
        self.albums = [
            {"albumName": "Apple Photos/Albums/Trip", "id": "album-1"},
            {"albumName": "Apple Photos: Videos", "id": "album-2"},
        ]
        self.album_payloads = {
            "album-1": {"assets": [{"id": "asset-1"}]},
            "album-2": {"assets": [{"id": "asset-2"}]},
        }

    def iter_all_assets(self) -> list[dict[str, str]]:
        return [
            {
                "id": "asset-1",
                "originalFileName": "AAAABBBB-1111-2222-3333-444455556666_IMG_1.JPG",
                "fileCreatedAt": "2024-01-02T10:00:00Z",
            },
            {
                "id": "asset-2",
                "originalFileName": "BBBBCCCC-1111-2222-3333-444455556666_IMG_2.MOV",
                "fileCreatedAt": "2024-01-03T10:00:00Z",
            },
        ]

    def get_albums(self) -> list[dict[str, str]]:
        return self.albums

    def get_album_assets(self, album_id: str) -> dict[str, list[dict[str, str]]]:
        return self.album_payloads[album_id]


class AlbumNamingTests(unittest.TestCase):
    def test_apply_albums_renames_legacy_album_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta_dir = root / "meta"
            meta_dir.mkdir(parents=True)
            album_map = {
                "assetCount": 1,
                "albumCount": 1,
                "albums": {
                    "Trip": {
                        "title": "Trip",
                        "assetUuids": ["AAAABBBB-1111-2222-3333-444455556666"],
                    }
                },
                "assets": {
                    "AAAABBBB-1111-2222-3333-444455556666": {
                        "originalFilename": "IMG_1.JPG",
                        "date": "2024-01-02 10:00:00",
                    }
                },
            }
            (meta_dir / "album-map.json").write_text(json.dumps(album_map), encoding="utf-8")
            config = Config(
                immich_server="https://example.com",
                immich_api_key="secret",
                photos_library="/tmp/library.photoslibrary",
                export_dir=root / "export",
                meta_dir=meta_dir,
                album_prefix="Apple Photos",
                system_album_prefix="Apple Photos",
            )

            import apple_photos_to_immich.commands as commands

            client = RenameClient()
            originals = {
                "_make_client": commands._make_client,
                "build_match_report": commands.build_match_report,
            }
            commands._make_client = lambda config, logger: client
            commands.build_match_report = lambda config, client, logger: {
                "uuidToAssetId": {"AAAABBBB-1111-2222-3333-444455556666": "asset-1"}
            }
            try:
                exit_code = apply_albums(config, LoggerStub(), dry_run=False)
            finally:
                for name, original in originals.items():
                    setattr(commands, name, original)

            self.assertEqual(exit_code, 0)
            self.assertEqual(client.renames, [("album-1", "Trip")])

    def test_verify_accepts_legacy_and_new_album_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta_dir = root / "meta"
            meta_dir.mkdir(parents=True)
            album_map = {
                "assetCount": 2,
                "albumCount": 2,
                "albums": {
                    "Trip": {
                        "title": "Trip",
                        "assetUuids": ["AAAABBBB-1111-2222-3333-444455556666"],
                    },
                    "Apple Photos: Videos": {
                        "title": "Apple Photos: Videos",
                        "assetUuids": ["BBBBCCCC-1111-2222-3333-444455556666"],
                    },
                },
                "assets": {
                    "AAAABBBB-1111-2222-3333-444455556666": {
                        "originalFilename": "IMG_1.JPG",
                        "date": "2024-01-02 10:00:00",
                    },
                    "BBBBCCCC-1111-2222-3333-444455556666": {
                        "originalFilename": "IMG_2.MOV",
                        "date": "2024-01-03 10:00:00",
                    },
                },
            }
            (meta_dir / "album-map.json").write_text(json.dumps(album_map), encoding="utf-8")
            config = Config(
                immich_server="https://example.com",
                immich_api_key="secret",
                photos_library="/tmp/library.photoslibrary",
                export_dir=root / "export",
                meta_dir=meta_dir,
                album_prefix="Apple Photos",
                system_album_prefix="Apple Photos",
            )

            import apple_photos_to_immich.commands as commands

            original = commands._make_client
            commands._make_client = lambda config, logger: VerifyClient()
            try:
                exit_code = verify(config, LoggerStub())
            finally:
                commands._make_client = original

            report = json.loads(config.verify_report_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(report["albumsPresentInImmich"], 2)
            self.assertEqual(report["albumsMissingInImmich"], 0)


if __name__ == "__main__":
    unittest.main()
