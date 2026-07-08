from __future__ import annotations

import logging
import time
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover - exercised in dependency-light environments
    requests = None

try:
    from urllib3.exceptions import InsecureRequestWarning
except ImportError:  # pragma: no cover - dependency-light environments
    InsecureRequestWarning = None


class ImmichClient:
    def __init__(
        self,
        server: str,
        api_key: str,
        *,
        verify_ssl: bool = True,
        page_size: int = 250,
        retry_attempts: int = 5,
        retry_backoff_seconds: float = 1.0,
        logger: logging.Logger | None = None,
    ) -> None:
        if requests is None:
            raise ModuleNotFoundError(
                "Missing requests package. Install with: python3 -m pip install requests"
            )
        self.base = server.rstrip("/") + "/api"
        self.verify_ssl = verify_ssl
        self.page_size = page_size
        self.retry_attempts = retry_attempts
        self.retry_backoff_seconds = retry_backoff_seconds
        self.logger = logger or logging.getLogger("apple_photos_to_immich")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "x-api-key": api_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )
        self._warned_insecure_ssl = False
        if not self.verify_ssl and InsecureRequestWarning is not None:
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = self.base + path
        last_error: Exception | None = None

        for attempt in range(1, self.retry_attempts + 1):
            try:
                if not self.verify_ssl and not self._warned_insecure_ssl:
                    self.logger.warning(
                        "SSL certificate verification is disabled for Immich requests to %s.",
                        self.base,
                    )
                    self._warned_insecure_ssl = True
                response = self.session.request(
                    method,
                    url,
                    verify=self.verify_ssl,
                    timeout=60,
                    **kwargs,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    raise requests.HTTPError(
                        f"Transient Immich response {response.status_code}: {response.text[:500]}",
                        response=response,
                    )
                if response.status_code >= 400:
                    raise RuntimeError(
                        f"{method} {path} failed: HTTP {response.status_code}: {response.text[:500]}"
                    )
                return response.json() if response.text else None
            except (requests.RequestException, RuntimeError) as exc:
                last_error = exc
                is_retryable = not isinstance(exc, RuntimeError) or "HTTP 4" not in str(exc)
                if attempt >= self.retry_attempts or not is_retryable:
                    break
                delay = self.retry_backoff_seconds * attempt
                self.logger.warning(
                    "Immich request failed on attempt %s/%s: %s. Retrying in %.1fs.",
                    attempt,
                    self.retry_attempts,
                    exc,
                    delay,
                )
                time.sleep(delay)

        assert last_error is not None
        error_text = str(last_error)
        if "Failed to resolve" in error_text or "NameResolutionError" in error_text:
            raise RuntimeError(
                f"Could not resolve Immich host '{self.base}'. Check IMMICH_SERVER / [immich].server and local DNS."
            ) from last_error
        raise RuntimeError(f"Immich API request failed after retries: {last_error}") from last_error

    def get_albums(self) -> list[dict[str, Any]]:
        return self.request("GET", "/albums")

    def create_album(self, title: str) -> dict[str, Any]:
        return self.request("POST", "/albums", json={"albumName": title})

    def update_album(self, album_id: str, title: str) -> dict[str, Any]:
        return self.request("PATCH", f"/albums/{album_id}", json={"albumName": title})

    def get_album_assets(self, album_id: str) -> list[dict[str, Any]]:
        return self.request("GET", f"/albums/{album_id}")

    def add_assets_to_album(self, album_id: str, asset_ids: list[str]) -> Any:
        return self.request("PUT", f"/albums/{album_id}/assets", json={"ids": asset_ids})

    def get_jobs(self) -> dict[str, Any]:
        return self.request("GET", "/jobs")

    def iter_all_assets(self, page_size: int | None = None) -> list[dict[str, Any]]:
        size = page_size or self.page_size
        assets: list[dict[str, Any]] = []
        page = 1

        while True:
            result = self.request("POST", "/search/metadata", json={"page": page, "size": size})
            assets_obj = result.get("assets", result)
            items = assets_obj.get("items", []) if isinstance(assets_obj, dict) else []
            if not items:
                break

            assets.extend(items)
            next_page = assets_obj.get("nextPage") if isinstance(assets_obj, dict) else None
            if next_page is not None:
                page = int(next_page)
                continue

            total = assets_obj.get("total") if isinstance(assets_obj, dict) else None
            if total is not None and page * size >= int(total):
                break
            if len(items) < size:
                break
            page += 1

        return assets
