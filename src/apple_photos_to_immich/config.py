from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomllib


DEFAULT_CONFIG_FILE = "config.toml"
DEFAULT_LOG_DIRNAME = "logs"
DEFAULT_MATCH_REPORT = "match-report.json"
DEFAULT_ALBUM_MAP = "album-map.json"
DEFAULT_MISSING_UUIDS = "missing-uuids.txt"
DEFAULT_VERIFY_REPORT = "verify-report.json"
DEFAULT_STATE_FILE = "run-state.json"


@dataclass(slots=True)
class Config:
    immich_server: str
    immich_api_key: str
    photos_library: str
    export_dir: Path
    meta_dir: Path
    album_prefix: str = ""
    system_album_prefix: str = ""
    skip_verify_ssl: bool = False
    log_dir: Path | None = None
    page_size: int = 250
    retry_attempts: int = 5
    retry_backoff_seconds: float = 1.0
    album_chunk_size: int = 500
    import_session_tag: str = "apple-photos-to-immich"
    import_manage_heic_jpeg: str = "StackCoverHeic"
    import_manage_raw_jpeg: str = "StackCoverRaw"
    test_export_limit: int = 30
    osxphotos_binary: str = "osxphotos"
    osxphotos_python: str = ""
    immich_go_binary: str = "immich-go"

    def __post_init__(self) -> None:
        self.album_prefix = self.album_prefix.strip("/")
        self.system_album_prefix = self.system_album_prefix.strip("/")
        self.log_dir = self.log_dir or (self.meta_dir / DEFAULT_LOG_DIRNAME)

    @property
    def album_map_path(self) -> Path:
        return self.meta_dir / DEFAULT_ALBUM_MAP

    @property
    def match_report_path(self) -> Path:
        return self.meta_dir / DEFAULT_MATCH_REPORT

    @property
    def missing_uuids_path(self) -> Path:
        return self.meta_dir / DEFAULT_MISSING_UUIDS

    @property
    def verify_report_path(self) -> Path:
        return self.meta_dir / DEFAULT_VERIFY_REPORT

    @property
    def state_path(self) -> Path:
        return self.meta_dir / DEFAULT_STATE_FILE

    @property
    def verify_ssl(self) -> bool:
        return not self.skip_verify_ssl


def find_config_file(explicit_path: str | None = None, start_dir: Path | None = None) -> Path:
    if explicit_path:
        path = Path(explicit_path).expanduser()
        if path.exists():
            return path
        raise FileNotFoundError(f"Config file not found: {path}")

    current = (start_dir or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        toml_candidate = directory / DEFAULT_CONFIG_FILE
        if toml_candidate.exists():
            return toml_candidate

    raise FileNotFoundError(
        "No config.toml found. Create one or pass --config /path/to/config.toml."
    )


def load_config(path: Path) -> Config:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))

    immich = _require_table(raw, "immich")
    photos = _require_table(raw, "photos")
    paths = _require_table(raw, "paths")
    logging = raw.get("logging", {})
    runtime = raw.get("runtime", {})

    config = Config(
        immich_server=_require_str(immich, "server"),
        immich_api_key=_require_str(immich, "api_key"),
        photos_library=str(_resolve_path(path, _require_str(photos, "library"))),
        export_dir=_resolve_path(path, _require_str(paths, "export_dir")),
        meta_dir=_resolve_path(path, _require_str(paths, "meta_dir")),
        album_prefix=_optional_str(photos.get("album_prefix", "")),
        system_album_prefix=_optional_str(photos.get("system_album_prefix", photos.get("album_prefix", ""))),
        skip_verify_ssl=_coerce_bool(immich.get("skip_verify_ssl", False)),
        log_dir=_resolve_optional_path(path, logging.get("dir")),
        page_size=int(runtime.get("page_size", 250)),
        retry_attempts=int(runtime.get("retry_attempts", 5)),
        retry_backoff_seconds=float(runtime.get("retry_backoff_seconds", 1.0)),
        album_chunk_size=int(runtime.get("album_chunk_size", 500)),
        import_session_tag=str(runtime.get("import_session_tag", "apple-photos-to-immich")),
        import_manage_heic_jpeg=str(runtime.get("import_manage_heic_jpeg", "StackCoverHeic")),
        import_manage_raw_jpeg=str(runtime.get("import_manage_raw_jpeg", "StackCoverRaw")),
        test_export_limit=int(runtime.get("test_export_limit", 30)),
        osxphotos_binary=str(runtime.get("osxphotos_binary", "osxphotos")),
        osxphotos_python=str(runtime.get("osxphotos_python", "")),
        immich_go_binary=str(runtime.get("immich_go_binary", "immich-go")),
    )
    return config


def _require_table(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Missing required [{key}] section in config.")
    return value


def _require_str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing required config value: {key}")
    return value.strip()


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _optional_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _resolve_path(config_path: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (config_path.parent / path).resolve()
    return path


def _resolve_optional_path(config_path: Path, value: Any) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    return _resolve_path(config_path, value)
