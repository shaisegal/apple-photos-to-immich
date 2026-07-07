# Codex Prompt: Apple Photos → Immich Migration Tool

You are working on a small open-source migration tool for moving an Apple Photos library to Immich.

## Goal

Build a robust CLI/project that migrates Apple Photos to Immich with the following goals:

- Export each Apple Photos asset only once.
- Preserve Live Photos, videos, RAW/JPEG pairs and metadata as well as possible.
- Preserve Apple Photos albums without duplicating files.
- Preserve multiple album memberships per asset.
- Create optional virtual Immich albums for Apple Photos properties such as:
  - Favorites
  - Videos
  - Live Photos
  - Screenshots
  - Selfies
  - Panoramas
  - Portrait
  - Slow Motion
  - Time Lapse
  - Hidden
- Use Immich API to create albums and add already-uploaded assets.
- Use `immich-go` for the actual asset upload.
- Use `osxphotos` for reading Apple Photos metadata.

## Known versions from the initial environment

- macOS: 26.5.1
- osxphotos: 0.76.1
- immich-go: 0.32.0
- Immich API: current as of July 2026

## Critical macOS requirement

The terminal app must have Full Disk Access:

System Settings → Privacy & Security → Full Disk Access → enable Terminal/iTerm.

Without this, `osxphotos info` may fail while copying `Photos.sqlite`.

## Current project files

- `config.example.toml`
- `01_export_once.sh`
- `02_import_assets.sh`
- `03_make_album_map.py`
- `04_apply_albums_to_immich.py`
- `05_verify.py`
- `README.md`

## Current strategy

1. `01_export_once.sh`
   - Runs `osxphotos export`.
   - Exports files by date.
   - Filename includes Apple Photos UUID:
     `{created.strftime,%Y%m%d-%H%M%S}_{uuid}_{original_name}`
   - Writes XMP sidecars.
   - Writes export report.

2. `02_import_assets.sh`
   - Runs `immich-go upload from-folder`.

3. `03_make_album_map.py`
   - Uses osxphotos Python API.
   - Produces `album-map.json`.
   - Maps Immich album title → Apple Photos UUIDs.

4. `04_apply_albums_to_immich.py`
   - Indexes Immich assets by UUID found in `originalFileName`.
   - Creates Immich albums.
   - Adds assets to albums.

5. `05_verify.py`
   - Compares UUIDs in `album-map.json` against UUIDs found in Immich asset filenames.

## Improvements requested

Turn this MVP into a more robust v1.0:

1. Convert shell/Python scripts into a single Python CLI, e.g.:
   - `apple-photos-to-immich check`
   - `apple-photos-to-immich export`
   - `apple-photos-to-immich import-assets`
   - `apple-photos-to-immich make-map`
   - `apple-photos-to-immich apply-albums`
   - `apple-photos-to-immich verify`
   - `apple-photos-to-immich all`

2. Add a TOML config file.

3. Add structured logging:
   - console progress
   - log file
   - JSON debug log optional

4. Add resume support:
   - if upload/import/apply-albums is interrupted, rerunning should continue safely.
   - album creation should be idempotent.
   - asset addition should not fail on already-added assets.

5. Add better Immich API compatibility:
   - centralize all API calls in one class.
   - handle pagination.
   - handle rate limiting and retries.
   - clear error messages for API changes.

6. Add a safer matching strategy:
   - primary: Apple UUID in filename.
   - fallback: original filename + creation date.
   - optional: checksum/hash if available.

7. Add verification:
   - Apple asset count vs Immich matched count.
   - albums created count.
   - assets per album.
   - missing asset report.
   - duplicate UUID report.

8. Add dry-run support for every write action.

9. Add tests:
   - unit tests for config loading.
   - unit tests for UUID extraction.
   - unit tests for album-map generation from mocked PhotoInfo objects.
   - unit tests for Immich API wrapper using mocked responses.

10. Improve README:
   - installation
   - macOS Full Disk Access warning
   - dry-run-first workflow
   - known limitations
   - troubleshooting
   - cleanup after successful migration

## Important constraints

- Do not mutate the original Apple Photos library.
- Do not require direct database schema hacking if osxphotos API can provide the needed metadata.
- Do not permanently duplicate files for album membership.
- Keep the tool understandable and easy to run on macOS.
- Prefer clear recoverability over cleverness.
