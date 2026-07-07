from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import osxphotos

from .apple_photos import as_list, get_bool


def build_album_map(library: str, album_prefix: str) -> dict[str, Any]:
    photosdb = osxphotos.PhotosDB(dbfile=library) if library else osxphotos.PhotosDB()
    photos = photosdb.photos()

    album_map: dict[str, dict[str, Any]] = {}
    asset_index: dict[str, dict[str, Any]] = {}

    def add(album_name: str, photo: Any) -> None:
        album_name = album_name.strip("/")
        if not album_name:
            return
        full_name = f"{album_prefix}/{album_name}" if album_prefix else album_name
        item = album_map.setdefault(full_name, {"title": full_name, "assetUuids": []})
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
                add(f"Albums/{album}", photo)

        if bool(getattr(photo, "favorite", False)):
            add("System/Favorites", photo)
        if get_bool(photo, "ismovie", "is_movie"):
            add("System/Videos", photo)
        if get_bool(photo, "live_photo", "is_live_photo", "live"):
            add("System/Live Photos", photo)
        if get_bool(photo, "screenshot", "is_screenshot"):
            add("System/Screenshots", photo)
        if get_bool(photo, "selfie", "is_selfie"):
            add("System/Selfies", photo)
        if get_bool(photo, "panorama", "is_panorama"):
            add("System/Panoramas", photo)
        if get_bool(photo, "portrait", "is_portrait"):
            add("System/Portrait", photo)
        if get_bool(photo, "slow_mo", "slowmo", "is_slow_mo"):
            add("System/Slow Motion", photo)
        if get_bool(photo, "time_lapse", "timelapse", "is_time_lapse"):
            add("System/Time Lapse", photo)
        if get_bool(photo, "hidden", "is_hidden"):
            add("System/Hidden", photo)

    album_map = {
        key: {"title": value["title"], "assetUuids": sorted(value["assetUuids"])}
        for key, value in sorted(album_map.items(), key=lambda item: item[0].lower())
        if value["assetUuids"]
    }

    return {
        "source": "Apple Photos via osxphotos",
        "albumPrefix": album_prefix,
        "assetCount": len(asset_index),
        "albumCount": len(album_map),
        "albums": album_map,
        "assets": asset_index,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", required=True)
    parser.add_argument("--album-prefix", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    result = build_album_map(args.library, args.album_prefix)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {output}")
    print(f"Assets: {result['assetCount']}")
    print(f"Albums: {result['albumCount']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
