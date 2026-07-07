from __future__ import annotations

import unittest

from apple_photos_to_immich.matching import extract_uuid, match_assets


class MatchingTests(unittest.TestCase):
    def test_extract_uuid(self) -> None:
        value = extract_uuid("20240101-120000_12345678-1234-1234-1234-1234567890ab_IMG_0001.JPG")
        self.assertEqual(value, "12345678-1234-1234-1234-1234567890AB")

    def test_match_assets_prefers_uuid_then_filename_date(self) -> None:
        apple_assets = {
            "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA": {
                "originalFilename": "IMG_0001.JPG",
                "date": "2024-02-03 10:11:12",
            },
            "BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB": {
                "originalFilename": "IMG_0002.JPG",
                "date": "2024-02-04 10:11:12",
            },
        }
        immich_assets = [
            {
                "id": "uuid-match",
                "originalFileName": "20240203_AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA_IMG_0001.JPG",
                "fileCreatedAt": "2024-02-03T10:11:12Z",
            },
            {
                "id": "fallback-match",
                "originalFileName": "IMG_0002.JPG",
                "fileCreatedAt": "2024-02-04T10:11:12Z",
            },
        ]

        result = match_assets(apple_assets, immich_assets)

        self.assertEqual(result.uuid_to_asset_id["AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"], "uuid-match")
        self.assertEqual(result.uuid_to_asset_id["BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB"], "fallback-match")
        self.assertEqual(result.matched_by["AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"], "uuid")
        self.assertEqual(result.matched_by["BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB"], "filename_date")
        self.assertEqual(result.missing_uuids, [])

    def test_match_assets_reports_duplicate_uuid_candidates(self) -> None:
        apple_assets = {
            "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA": {
                "originalFilename": "IMG_0001.JPG",
                "date": "2024-02-03 10:11:12",
            }
        }
        immich_assets = [
            {
                "id": "asset-1",
                "originalFileName": "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA_IMG_0001.JPG",
                "fileCreatedAt": "2024-02-03T10:11:12Z",
            },
            {
                "id": "asset-2",
                "originalFileName": "copy_AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA_IMG_0001.JPG",
                "fileCreatedAt": "2024-02-03T10:11:12Z",
            },
        ]

        result = match_assets(apple_assets, immich_assets)

        self.assertEqual(result.duplicate_uuids, {"AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA": 2})


if __name__ == "__main__":
    unittest.main()
