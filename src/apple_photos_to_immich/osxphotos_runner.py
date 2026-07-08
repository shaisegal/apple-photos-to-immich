from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import osxphotos

from .album_names import build_album_title, build_system_album_title
from .apple_photos import as_list, get_bool


def build_album_map(library: str, album_prefix: str, system_album_prefix: str) -> dict[str, Any]:
    photosdb = osxphotos.PhotosDB(dbfile=library) if library else osxphotos.PhotosDB()
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

        folder_albums = as_list(getattr(photo, "folder_album", None))
        if not folder_albums:
            folder_albums = as_list(getattr(photo, "albums", None))

        for album in folder_albums:
            if album and album != "_":
                add(build_album_title(album), photo)

        if bool(getattr(photo, "favorite", False)):
            add(build_system_album_title("Favorites", system_album_prefix), photo)
        if get_bool(photo, "ismovie", "is_movie"):
            add(build_system_album_title("Videos", system_album_prefix), photo)
        if get_bool(photo, "live_photo", "is_live_photo", "live"):
            add(build_system_album_title("Live Photos", system_album_prefix), photo)
        if get_bool(photo, "screenshot", "is_screenshot"):
            add(build_system_album_title("Screenshots", system_album_prefix), photo)
        if get_bool(photo, "selfie", "is_selfie"):
            add(build_system_album_title("Selfies", system_album_prefix), photo)
        if get_bool(photo, "panorama", "is_panorama"):
            add(build_system_album_title("Panoramas", system_album_prefix), photo)
        if get_bool(photo, "portrait", "is_portrait"):
            add(build_system_album_title("Portrait", system_album_prefix), photo)
        if get_bool(photo, "slow_mo", "slowmo", "is_slow_mo"):
            add(build_system_album_title("Slow Motion", system_album_prefix), photo)
        if get_bool(photo, "time_lapse", "timelapse", "is_time_lapse"):
            add(build_system_album_title("Time Lapse", system_album_prefix), photo)
        if get_bool(photo, "hidden", "is_hidden"):
            add(build_system_album_title("Hidden", system_album_prefix), photo)

    album_map = {
        key: {"title": value["title"], "assetUuids": sorted(value["assetUuids"])}
        for key, value in sorted(album_map.items(), key=lambda item: item[0].lower())
        if value["assetUuids"]
    }

    return {
        "source": "Apple Photos via osxphotos",
        "albumPrefix": album_prefix,
        "systemAlbumPrefix": system_album_prefix,
        "assetCount": len(asset_index),
        "albumCount": len(album_map),
        "albums": album_map,
        "assets": asset_index,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", required=True)
    parser.add_argument("--album-prefix", required=True)
    parser.add_argument("--system-album-prefix", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    result = build_album_map(args.library, args.album_prefix, args.system_album_prefix)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {output}")
    print(f"Assets: {result['assetCount']}")
    print(f"Albums: {result['albumCount']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
