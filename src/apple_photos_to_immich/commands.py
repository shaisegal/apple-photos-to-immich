from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .album_names import (
    build_album_title,
    build_system_album_title,
    legacy_system_album_title,
    legacy_user_album_title,
)
from .apple_photos import get_album_names, get_bool
from .config import Config
from .matching import match_assets
from .state import RunState, load_state, save_state

if TYPE_CHECKING:
    from .immich import ImmichClient


def check(config: Config, logger: logging.Logger) -> int:
    logger.info("Checking local dependencies and directories.")
    missing = []
    for binary in [config.osxphotos_binary, config.immich_go_binary]:
        if shutil.which(binary) is None:
            missing.append(binary)
    if missing:
        logger.error("Missing required binaries: %s", ", ".join(missing))
        return 1

    try:
        config.export_dir.mkdir(parents=True, exist_ok=True)
        config.meta_dir.mkdir(parents=True, exist_ok=True)
        config.log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.error("Could not prepare output directories: %s", exc)
        return 1

    library = Path(config.photos_library).expanduser()
    if not library.exists():
        logger.error("Apple Photos library not found: %s", library)
        return 1

    logger.info("Config OK.")
    logger.info("Photos library: %s", library)
    logger.info("Export dir: %s", config.export_dir)
    logger.info("Meta dir: %s", config.meta_dir)
    return 0


def export_assets(
    config: Config,
    logger: logging.Logger,
    *,
    test_mode: bool = False,
    dry_run: bool = False,
    update: bool = False,
) -> int:
    cmd = [
        config.osxphotos_binary,
        "export",
        str(config.export_dir),
        "--library",
        config.photos_library,
        "--export-by-date",
        "--filename",
        "{created.strftime,%Y%m%d-%H%M%S}_{uuid}_{original_name}",
        "--touch-file",
        "--sidecar",
        "xmp",
        "--favorite-rating",
        "--album-keyword",
        "--person-keyword",
        "--report",
        str(config.meta_dir / "osxphotos-export.csv"),
        "--retry",
        "3",
        "--verbose",
    ]
    if test_mode:
        cmd.extend(["--limit", str(config.test_export_limit)])
    if update:
        cmd.append("--update")

    if dry_run:
        logger.info("DRY RUN export command: %s", " ".join(cmd))
        return 0

    logger.info("Running osxphotos export%s.", " in test mode" if test_mode else "")
    return subprocess.run(cmd, check=False).returncode


def import_assets(config: Config, logger: logging.Logger, *, dry_run: bool = False) -> int:
    cmd = [
        config.immich_go_binary,
        "upload",
        "from-folder",
        "--server",
        config.immich_server,
        "--api-key",
        config.immich_api_key,
        f"--manage-heic-jpeg={config.import_manage_heic_jpeg}",
        f"--manage-raw-jpeg={config.import_manage_raw_jpeg}",
        "--session-tag",
        config.import_session_tag,
    ]
    if config.skip_verify_ssl:
        cmd.append("--skip-verify-ssl")
    cmd.append(str(config.export_dir))

    if dry_run:
        logger.info("DRY RUN import command: %s", " ".join(cmd))
        return 0

    logger.info("Importing assets into Immich via immich-go.")
    return_code = subprocess.run(cmd, check=False).returncode
    if return_code == 0:
        logger.warning(
            "immich-go finished, but Immich server-side jobs may still be running. "
            "Check pending jobs before apply-albums or verify."
        )
    return return_code


def wait_for_immich(
    config: Config,
    logger: logging.Logger,
    *,
    timeout_seconds: float = 1800.0,
    interval_seconds: float = 10.0,
) -> int:
    client = _make_client(config, logger)
    deadline = time.monotonic() + timeout_seconds
    last_summary: dict[str, Any] | None = None

    logger.info(
        "Waiting for Immich jobs to settle via /api/jobs (timeout=%.0fs, interval=%.1fs).",
        timeout_seconds,
        interval_seconds,
    )

    while True:
        jobs = client.get_jobs()
        summary = _summarize_jobs(jobs)

        if summary != last_summary:
            logger.info(
                "Immich jobs: active=%s waiting=%s delayed=%s paused=%s failed=%s queues=%s",
                summary["active"],
                summary["waiting"],
                summary["delayed"],
                summary["paused"],
                summary["failed"],
                summary["queues"],
            )
            last_summary = summary

        if summary["active"] == 0 and summary["waiting"] == 0 and summary["delayed"] == 0:
            if summary["paused"] > 0:
                logger.warning(
                    "Immich is idle, but %s paused jobs remain. No more progress happens until those queues are resumed.",
                    summary["paused"],
                )
            logger.info("Immich server-side jobs are idle.")
            return 0

        if time.monotonic() >= deadline:
            logger.error(
                "Timed out waiting for Immich jobs. Last state: active=%s waiting=%s delayed=%s paused=%s failed=%s",
                summary["active"],
                summary["waiting"],
                summary["delayed"],
                summary["paused"],
                summary["failed"],
            )
            return 1

        time.sleep(interval_seconds)


def make_album_map(config: Config, logger: logging.Logger) -> int:
    try:
        import osxphotos
    except ImportError:
        logger.info("osxphotos is not importable in the current Python; trying external osxphotos Python.")
        return _run_osxphotos_helper(config, logger)

    config.meta_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Reading Apple Photos metadata.")

    photosdb = osxphotos.PhotosDB(dbfile=config.photos_library) if config.photos_library else osxphotos.PhotosDB()
    photos = photosdb.photos()

    album_map: dict[str, dict[str, Any]] = {}
    asset_index: dict[str, dict[str, Any]] = {}

    def add(album_name: str, photo: Any) -> None:
        album_name = album_name.strip("/")
        if not album_name:
            return
        item = album_map.setdefault(album_name, {"title": album_name, "assetUuids": []})
        uuid = str(getattr(photo, "uuid", "")).upper()
        if uuid and uuid not in item["assetUuids"]:
            item["assetUuids"].append(uuid)

    for photo in photos:
        uuid = str(getattr(photo, "uuid", "")).upper()
        if not uuid:
            continue

        original_filename = (
            getattr(photo, "original_filename", None)
            or getattr(photo, "filename", None)
            or getattr(photo, "original_name", None)
            or ""
        )

        asset_index[uuid] = {
            "uuid": uuid,
            "originalFilename": str(original_filename),
            "date": str(getattr(photo, "date", "")),
            "favorite": bool(getattr(photo, "favorite", False)),
        }

        for album in get_album_names(photo):
            add(build_album_title(album), photo)

        if bool(getattr(photo, "favorite", False)):
            add(build_system_album_title("Favorites", config.system_album_prefix), photo)
        if get_bool(photo, "ismovie", "is_movie"):
            add(build_system_album_title("Videos", config.system_album_prefix), photo)
        if get_bool(photo, "live_photo", "is_live_photo", "live"):
            add(build_system_album_title("Live Photos", config.system_album_prefix), photo)
        if get_bool(photo, "screenshot", "is_screenshot"):
            add(build_system_album_title("Screenshots", config.system_album_prefix), photo)
        if get_bool(photo, "selfie", "is_selfie"):
            add(build_system_album_title("Selfies", config.system_album_prefix), photo)
        if get_bool(photo, "panorama", "is_panorama"):
            add(build_system_album_title("Panoramas", config.system_album_prefix), photo)
        if get_bool(photo, "portrait", "is_portrait"):
            add(build_system_album_title("Portrait", config.system_album_prefix), photo)
        if get_bool(photo, "slow_mo", "slowmo", "is_slow_mo"):
            add(build_system_album_title("Slow Motion", config.system_album_prefix), photo)
        if get_bool(photo, "time_lapse", "timelapse", "is_time_lapse"):
            add(build_system_album_title("Time Lapse", config.system_album_prefix), photo)
        if get_bool(photo, "hidden", "is_hidden"):
            add(build_system_album_title("Hidden", config.system_album_prefix), photo)

    album_map = {
        key: {"title": value["title"], "assetUuids": sorted(value["assetUuids"])}
        for key, value in sorted(album_map.items(), key=lambda item: item[0].lower())
        if value["assetUuids"]
    }

    out = {
        "source": "Apple Photos via osxphotos",
        "albumPrefix": config.album_prefix,
        "systemAlbumPrefix": config.system_album_prefix,
        "assetCount": len(asset_index),
        "albumCount": len(album_map),
        "albums": album_map,
        "assets": asset_index,
    }
    config.album_map_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote %s", config.album_map_path)
    logger.info("Assets: %s, Albums: %s", len(asset_index), len(album_map))
    return 0


def build_match_report(config: Config, client: ImmichClient, logger: logging.Logger) -> dict[str, Any]:
    data = json.loads(config.album_map_path.read_text(encoding="utf-8"))
    apple_assets: dict[str, dict[str, Any]] = data.get("assets", {})

    logger.info("Indexing Immich assets.")
    immich_assets = client.iter_all_assets()
    result = match_assets(apple_assets, immich_assets)
    report = {
        "appleAssetCount": len(apple_assets),
        "immichAssetCount": len(immich_assets),
        "matchedCount": len(result.uuid_to_asset_id),
        "missingCount": len(result.missing_uuids),
        "duplicateUuidCount": len(result.duplicate_uuids),
        "matchedBy": result.matched_by,
        "duplicateUuids": result.duplicate_uuids,
        "missingUuids": result.missing_uuids,
        "uuidToAssetId": result.uuid_to_asset_id,
    }
    config.match_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if result.missing_uuids:
        config.missing_uuids_path.write_text("\n".join(result.missing_uuids) + "\n", encoding="utf-8")
    logger.info(
        "Match report written. Matched: %s, Missing: %s, Duplicate UUIDs: %s",
        report["matchedCount"],
        report["missingCount"],
        report["duplicateUuidCount"],
    )
    return report


def apply_albums(config: Config, logger: logging.Logger, *, dry_run: bool = False, sleep_seconds: float = 0.1) -> int:
    exit_code = ensure_album_map(config, logger)
    if exit_code != 0:
        return exit_code

    client = _make_client(config, logger)
    album_map = json.loads(config.album_map_path.read_text(encoding="utf-8"))
    albums: dict[str, dict[str, Any]] = album_map["albums"]
    report = build_match_report(config, client, logger)
    uuid_to_asset_id = report["uuidToAssetId"]

    existing_albums = {album["albumName"]: album["id"] for album in client.get_albums()}
    created = 0
    renamed = 0
    merged = 0
    touched = 0
    missing_assets_total = 0

    for title, album in albums.items():
        apple_uuids = [uuid.upper() for uuid in album["assetUuids"]]
        asset_ids = [uuid_to_asset_id[uuid] for uuid in apple_uuids if uuid in uuid_to_asset_id]
        missing_assets_total += len(apple_uuids) - len(asset_ids)

        if not asset_ids:
            logger.warning("Skipping unmatched album %s", title)
            continue

        legacy_album_id: str | None = None
        legacy_album_title: str | None = None
        if title in existing_albums:
            album_id = existing_albums[title]
            legacy_titles = _legacy_album_titles(title, config)
            legacy_matches = [legacy for legacy in legacy_titles if legacy in existing_albums and legacy != title]
            if len(legacy_matches) == 1:
                legacy_album_title = legacy_matches[0]
                legacy_album_id = existing_albums[legacy_album_title]
                if dry_run:
                    logger.info(
                        "DRY RUN would merge legacy album %s into %s and delete the legacy album",
                        legacy_album_title,
                        title,
                    )
                merged += 1
            elif len(legacy_matches) > 1:
                logger.warning("Multiple legacy album names match %s: %s", title, ", ".join(legacy_matches))
                continue
        else:
            legacy_titles = _legacy_album_titles(title, config)
            legacy_matches = [legacy for legacy in legacy_titles if legacy in existing_albums and legacy != title]
            if len(legacy_matches) == 1:
                legacy_title = legacy_matches[0]
                album_id = existing_albums[legacy_title]
                if dry_run:
                    logger.info("DRY RUN would rename album %s -> %s", legacy_title, title)
                else:
                    client.update_album(album_id, title)
                existing_albums.pop(legacy_title, None)
                existing_albums[title] = album_id
                renamed += 1
            elif len(legacy_matches) > 1:
                logger.warning("Multiple legacy album names match %s: %s", title, ", ".join(legacy_matches))
                continue
            else:
                if dry_run:
                    logger.info("DRY RUN would create album %s with %s assets", title, len(asset_ids))
                    touched += 1
                    continue
                new_album = client.create_album(title)
                album_id = new_album["id"]
                existing_albums[title] = album_id
                created += 1

        existing_asset_ids = set()
        legacy_asset_ids = set()
        if not dry_run:
            album_payload = client.get_album_assets(album_id)
            existing_asset_ids = {asset["id"] for asset in album_payload.get("assets", [])}
            if legacy_album_id is not None:
                legacy_payload = client.get_album_assets(legacy_album_id)
                legacy_asset_ids = {asset["id"] for asset in legacy_payload.get("assets", [])}

        pending = [asset_id for asset_id in asset_ids if asset_id not in existing_asset_ids]
        for legacy_asset_id in sorted(legacy_asset_ids):
            if legacy_asset_id not in existing_asset_ids and legacy_asset_id not in pending:
                pending.append(legacy_asset_id)
        if dry_run:
            logger.info(
                "DRY RUN album %s: total=%s add=%s already_present=%s missing=%s",
                title,
                len(asset_ids),
                len(pending),
                len(asset_ids) - len(pending),
                len(apple_uuids) - len(asset_ids),
            )
            touched += 1
            continue

        for index in range(0, len(pending), config.album_chunk_size):
            chunk = pending[index : index + config.album_chunk_size]
            if chunk:
                client.add_assets_to_album(album_id, chunk)
                time.sleep(sleep_seconds)
        if legacy_album_id is not None:
            client.delete_album(legacy_album_id)
            if legacy_album_title is not None:
                existing_albums.pop(legacy_album_title, None)

        logger.info(
            "Album %s synced: total=%s added=%s already_present=%s missing=%s",
            title,
            len(asset_ids),
            len(pending),
            len(asset_ids) - len(pending),
            len(apple_uuids) - len(asset_ids),
        )
        touched += 1

    logger.info(
        "Album apply finished. Created=%s, renamed=%s, merged=%s, touched=%s, missing asset references=%s",
        created,
        renamed,
        merged,
        touched,
        missing_assets_total,
    )
    return 0


def verify(config: Config, logger: logging.Logger) -> int:
    exit_code = ensure_album_map(config, logger)
    if exit_code != 0:
        return exit_code

    data = json.loads(config.album_map_path.read_text(encoding="utf-8"))
    client = _make_client(config, logger)
    report = build_match_report(config, client, logger)
    existing_albums = {album["albumName"]: album["id"] for album in client.get_albums()}

    album_stats = []
    for title, album in data.get("albums", {}).items():
        expected_uuids = [uuid.upper() for uuid in album["assetUuids"]]
        expected_asset_ids = {
            report["uuidToAssetId"][uuid]
            for uuid in expected_uuids
            if uuid in report["uuidToAssetId"]
        }
        unmatched_uuids = [uuid for uuid in expected_uuids if uuid not in report["uuidToAssetId"]]
        album_id = existing_albums.get(title)
        if not album_id:
            for legacy_title in _legacy_album_titles(title, config):
                album_id = existing_albums.get(legacy_title)
                if album_id:
                    break
        actual_asset_ids: set[str] = set()
        extra_asset_ids: list[str] = []
        missing_asset_ids: list[str] = []
        actual_asset_count = 0

        if album_id:
            album_payload = client.get_album_assets(album_id)
            actual_asset_ids = {asset["id"] for asset in album_payload.get("assets", [])}
            actual_asset_count = len(actual_asset_ids)
            missing_asset_ids = sorted(expected_asset_ids - actual_asset_ids)
            extra_asset_ids = sorted(actual_asset_ids - expected_asset_ids)

        album_stats.append(
            {
                "title": title,
                "expectedAssetCount": len(expected_uuids),
                "matchedAssetCount": len(expected_asset_ids),
                "unmatchedUuidCount": len(unmatched_uuids),
                "unmatchedUuidsSample": unmatched_uuids[:10],
                "existsInImmich": album_id is not None,
                "actualAssetCount": actual_asset_count,
                "missingAssetIdCount": len(missing_asset_ids),
                "missingAssetIdsSample": missing_asset_ids[:10],
                "extraAssetIdCount": len(extra_asset_ids),
                "extraAssetIdsSample": extra_asset_ids[:10],
            }
        )

    albums_with_missing_assets = sum(1 for stat in album_stats if stat["missingAssetIdCount"] > 0)
    albums_with_extra_assets = sum(1 for stat in album_stats if stat["extraAssetIdCount"] > 0)
    albums_missing_in_immich = sum(1 for stat in album_stats if not stat["existsInImmich"])
    verify_report = {
        "appleAssetCount": data.get("assetCount", len(data.get("assets", {}))),
        "albumCount": data.get("albumCount", len(data.get("albums", {}))),
        "matchedAssetCount": report["matchedCount"],
        "missingAssetCount": report["missingCount"],
        "duplicateUuidCount": report["duplicateUuidCount"],
        "albumsPresentInImmich": sum(1 for stat in album_stats if stat["existsInImmich"]),
        "albumsMissingInImmich": albums_missing_in_immich,
        "albumsWithMissingAssets": albums_with_missing_assets,
        "albumsWithExtraAssets": albums_with_extra_assets,
        "albumStats": album_stats,
    }
    config.verify_report_path.write_text(json.dumps(verify_report, indent=2), encoding="utf-8")

    logger.info("Verification summary")
    logger.info("Apple assets in map: %s", verify_report["appleAssetCount"])
    logger.info("Matched assets in Immich: %s", verify_report["matchedAssetCount"])
    logger.info("Missing Apple UUIDs: %s", verify_report["missingAssetCount"])
    logger.info("Duplicate UUIDs in Immich matches: %s", verify_report["duplicateUuidCount"])
    logger.info("Albums in map: %s", verify_report["albumCount"])
    logger.info("Albums present in Immich: %s", verify_report["albumsPresentInImmich"])
    logger.info("Albums missing in Immich: %s", verify_report["albumsMissingInImmich"])
    logger.info("Albums with missing assets: %s", verify_report["albumsWithMissingAssets"])
    logger.info("Albums with extra assets: %s", verify_report["albumsWithExtraAssets"])
    logger.info("Verify report: %s", config.verify_report_path)
    has_drift = (
        report["missingCount"] > 0
        or verify_report["duplicateUuidCount"] > 0
        or verify_report["albumsMissingInImmich"] > 0
        or verify_report["albumsWithMissingAssets"] > 0
    )
    return 2 if has_drift else 0


def ensure_album_map(config: Config, logger: logging.Logger) -> int:
    if not config.album_map_path.exists():
        logger.info("Missing %s. Generating album map now.", config.album_map_path)
        return make_album_map(config, logger)

    stale_reason = _get_album_map_stale_reason(config)
    if stale_reason:
        logger.info(
            "Album map is stale (%s). Regenerating %s.",
            stale_reason,
            config.album_map_path,
        )
        return make_album_map(config, logger)

    return 0


def run_all(
    config: Config,
    logger: logging.Logger,
    *,
    dry_run: bool = False,
    test_mode: bool = False,
    resume: bool = True,
    reset_state: bool = False,
) -> int:
    steps = [
        ("check", lambda: check(config, logger)),
        ("export", lambda: export_assets(config, logger, test_mode=test_mode, dry_run=dry_run, update=True)),
        ("import-assets", lambda: import_assets(config, logger, dry_run=dry_run)),
        ("make-map", lambda: make_album_map(config, logger)),
        ("apply-albums", lambda: apply_albums(config, logger, dry_run=dry_run)),
        ("verify", lambda: verify(config, logger)),
    ]

    state = RunState()
    persist_state = not dry_run
    if persist_state:
        if reset_state and config.state_path.exists():
            config.state_path.unlink()
        if resume:
            state = load_state(config.state_path)

    for name, fn in steps:
        if persist_state and resume and state.is_completed(name):
            logger.info("Skipping completed step from state file: %s", name)
            continue
        logger.info("Running step: %s", name)
        exit_code = fn()
        if exit_code != 0 and not (name == "verify" and exit_code == 2):
            logger.error("Step failed: %s", name)
            return exit_code
        if persist_state:
            state.mark_completed(
                name,
                {
                    "dryRun": dry_run,
                    "testMode": test_mode,
                    "exitCode": exit_code,
                },
            )
            save_state(config.state_path, state)
    return 0


def _make_client(config: Config, logger: logging.Logger) -> ImmichClient:
    from .immich import ImmichClient

    return ImmichClient(
        config.immich_server,
        config.immich_api_key,
        verify_ssl=config.verify_ssl,
        page_size=config.page_size,
        retry_attempts=config.retry_attempts,
        retry_backoff_seconds=config.retry_backoff_seconds,
        logger=logger,
    )


def _summarize_jobs(jobs: dict[str, Any]) -> dict[str, int]:
    totals = {
        "active": 0,
        "waiting": 0,
        "delayed": 0,
        "paused": 0,
        "failed": 0,
        "completed": 0,
        "queues": 0,
    }

    for queue in jobs.values():
        if not isinstance(queue, dict):
            continue
        totals["queues"] += 1
        status = queue.get("queueStatus", {})
        counts = queue.get("jobCounts", {})
        totals["active"] += int(status.get("active", 0) or 0)
        totals["waiting"] += int(status.get("waiting", 0) or 0)
        totals["delayed"] += int(status.get("delayed", 0) or 0)
        totals["paused"] += int(status.get("paused", 0) or 0)
        totals["failed"] += int(counts.get("failed", 0) or 0)
        totals["completed"] += int(counts.get("completed", 0) or 0)

    return totals


def _get_album_map_stale_reason(config: Config) -> str | None:
    album_map_path = config.album_map_path
    if not album_map_path.exists():
        return "missing"

    album_map_mtime = album_map_path.stat().st_mtime
    freshness_sources = [
        config.meta_dir / "osxphotos-export.csv",
        config.export_dir,
    ]

    for source in freshness_sources:
        source_mtime = _get_latest_mtime(source)
        if source_mtime is not None and source_mtime > album_map_mtime:
            return f"{source} is newer"

    return None


def _get_latest_mtime(path: Path) -> float | None:
    if not path.exists():
        return None
    if path.is_file():
        return path.stat().st_mtime

    latest = path.stat().st_mtime
    for child in path.rglob("*"):
        try:
            child_mtime = child.stat().st_mtime
        except OSError:
            continue
        if child_mtime > latest:
            latest = child_mtime
    return latest


def _run_osxphotos_helper(config: Config, logger: logging.Logger) -> int:
    python_cmd = _detect_osxphotos_python(config)
    if not python_cmd:
        logger.error(
            "Missing osxphotos Python package in the active environment and no external osxphotos Python was found."
        )
        logger.error(
            "Either install osxphotos into the same venv, or set runtime.osxphotos_python in config.toml."
        )
        return 1

    src_root = Path(__file__).resolve().parents[1]
    env = dict(**__import__("os").environ)
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_root}{':' + existing_pythonpath if existing_pythonpath else ''}"
    cmd = [
        python_cmd,
        "-m",
        "apple_photos_to_immich.osxphotos_runner",
        "--library",
        config.photos_library,
        "--album-prefix",
        config.album_prefix,
        "--system-album-prefix",
        config.system_album_prefix,
        "--output",
        str(config.album_map_path),
    ]
    logger.info("Running album-map generation via external osxphotos Python: %s", python_cmd)
    return subprocess.run(cmd, check=False, env=env).returncode


def _detect_osxphotos_python(config: Config) -> str | None:
    if config.osxphotos_python:
        return config.osxphotos_python

    osxphotos_path = shutil.which(config.osxphotos_binary)
    if not osxphotos_path:
        return None

    candidate = Path(osxphotos_path).resolve().parent / "python"
    if candidate.exists():
        return str(candidate)
    return None


def _legacy_album_titles(title: str, config: Config) -> list[str]:
    legacy_titles = [title]
    system_prefix = f"{config.system_album_prefix}: " if config.system_album_prefix else ""
    if system_prefix and title.startswith(system_prefix):
        system_name = title[len(system_prefix) :].strip()
        legacy_titles.append(legacy_system_album_title(system_name, config.album_prefix))
        legacy_titles.append(legacy_system_album_title(system_name, ""))
    else:
        legacy_titles.append(legacy_user_album_title(title, config.album_prefix))
        legacy_titles.append(legacy_user_album_title(title, ""))
    return list(dict.fromkeys(legacy_titles))
