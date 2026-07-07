from __future__ import annotations

import logging
import unittest
from unittest.mock import MagicMock

from apple_photos_to_immich import immich as immich_module

if immich_module.requests is not None:
    import requests

    ImmichClient = immich_module.ImmichClient
else:
    requests = None
    ImmichClient = None


def make_response(status_code: int, payload: dict | None = None, text: str | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    if payload is not None:
        response.json.return_value = payload
        response.text = text if text is not None else "json"
    else:
        response.text = text or ""
    return response


@unittest.skipIf(ImmichClient is None, "requests not installed")
class ImmichClientTests(unittest.TestCase):
    def test_request_retries_transient_errors(self) -> None:
        client = ImmichClient(
            "https://example.com",
            "secret",
            retry_attempts=2,
            retry_backoff_seconds=0,
            logger=logging.getLogger("test"),
        )
        client.session.request = MagicMock(
            side_effect=[
                requests.ConnectionError("temporary"),
                make_response(200, {"ok": True}),
            ]
        )

        result = client.request("GET", "/albums")

        self.assertEqual(result, {"ok": True})
        self.assertEqual(client.session.request.call_count, 2)

    def test_iter_all_assets_paginates(self) -> None:
        client = ImmichClient(
            "https://example.com",
            "secret",
            page_size=2,
            retry_backoff_seconds=0,
            logger=logging.getLogger("test"),
        )
        client.request = MagicMock(
            side_effect=[
                {"assets": {"items": [{"id": "1"}, {"id": "2"}], "total": 3}},
                {"assets": {"items": [{"id": "3"}], "total": 3}},
            ]
        )

        items = client.iter_all_assets()

        self.assertEqual([item["id"] for item in items], ["1", "2", "3"])
        self.assertEqual(client.request.call_count, 2)

    def test_iter_all_assets_prefers_next_page_over_total(self) -> None:
        client = ImmichClient(
            "https://example.com",
            "secret",
            page_size=2,
            retry_backoff_seconds=0,
            logger=logging.getLogger("test"),
        )
        client.request = MagicMock(
            side_effect=[
                {"assets": {"items": [{"id": "1"}, {"id": "2"}], "total": 2, "nextPage": 2}},
                {"assets": {"items": [{"id": "3"}, {"id": "4"}], "total": 2, "nextPage": None}},
            ]
        )

        items = client.iter_all_assets()

        self.assertEqual([item["id"] for item in items], ["1", "2", "3", "4"])
        self.assertEqual(client.request.call_count, 2)


if __name__ == "__main__":
    unittest.main()
