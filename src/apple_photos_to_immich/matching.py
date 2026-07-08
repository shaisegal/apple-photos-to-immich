from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any


UUID_RE = re.compile(
    r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}"
)
EXPORT_NAME_RE = re.compile(
    r"^\d{8}-\d{6}_[0-9A-Fa-f-]{36}_(.+)$"
)


def extract_uuid(filename: str) -> str | None:
    match = UUID_RE.search(filename or "")
    return match.group(0).upper() if match else None


def normalize_filename(filename: str | None) -> str:
    return (filename or "").strip().lower()


def normalize_source_filename(filename: str | None) -> str:
    normalized = normalize_filename(filename)
    match = EXPORT_NAME_RE.match(normalized)
    return match.group(1) if match else normalized


def normalize_created_at(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return value[:10]


@dataclass(slots=True)
class MatchResult:
    uuid_to_asset_id: dict[str, str]
    matched_by: dict[str, str]
    duplicate_uuids: dict[str, int]
    missing_uuids: list[str]


def match_assets(apple_assets: dict[str, dict[str, Any]], immich_assets: list[dict[str, Any]]) -> MatchResult:
    uuid_candidates: dict[str, list[str]] = {}
    fallback_candidates: dict[tuple[str, str], list[str]] = {}

    for asset in immich_assets:
        asset_id = str(asset["id"])
        original_name = asset.get("originalFileName", "")
        created_at = (
            asset.get("fileCreatedAt")
            or asset.get("localDateTime")
            or asset.get("exifInfo", {}).get("dateTimeOriginal")
            or ""
        )

        uuid = extract_uuid(original_name)
        if uuid:
            uuid_candidates.setdefault(uuid, []).append(asset_id)

        fallback_key = (normalize_source_filename(original_name), normalize_created_at(created_at))
        if fallback_key[0]:
            fallback_candidates.setdefault(fallback_key, []).append(asset_id)

    resolved: dict[str, str] = {}
    matched_by: dict[str, str] = {}
    duplicate_counter: Counter[str] = Counter()

    for uuid, ids in uuid_candidates.items():
        if len(ids) == 1:
            resolved[uuid] = ids[0]
            matched_by[uuid] = "uuid"
        else:
            duplicate_counter[uuid] = len(ids)

    missing: list[str] = []

    for apple_uuid, payload in apple_assets.items():
        normalized_uuid = apple_uuid.upper()
        if normalized_uuid in resolved:
            continue

        fallback_key = (
            normalize_source_filename(str(payload.get("originalFilename", ""))),
            normalize_created_at(str(payload.get("date", ""))),
        )
        candidate_ids = fallback_candidates.get(fallback_key, [])
        if len(candidate_ids) == 1:
            resolved[normalized_uuid] = candidate_ids[0]
            matched_by[normalized_uuid] = "filename_date"
            continue

        missing.append(normalized_uuid)

    return MatchResult(
        uuid_to_asset_id=resolved,
        matched_by=matched_by,
        duplicate_uuids=dict(sorted(duplicate_counter.items())),
        missing_uuids=sorted(missing),
    )
