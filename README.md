# Apple Photos -> Immich Migration Tool

Python CLI for a robust migration from Apple Photos to Immich.

This project exports Apple Photos assets once, uploads them with `immich-go`, and then rebuilds Apple albums through the Immich API.

Important before you start:

- this tool is intended for a local Apple Photos library on your Mac
- if your library uses iCloud Photos, make sure the Mac has the full original files locally before you export
- in Photos on Mac, check the iCloud settings and prefer `Download Originals to this Mac` instead of `Optimize Mac Storage`
- otherwise the export may only see device-optimized or not-yet-downloaded items, which can lead to missing assets or reduced-quality files in the migration

Apple references:

- Photos User Guide for Mac: <https://support.apple.com/guide/photos/welcome/mac>
- Apple Support search for the Photos iCloud setting: <https://support.apple.com/search?query=Download%20Originals%20to%20this%20Mac>

## Why This Exists

The hardest part of an Apple Photos to Immich migration is usually not getting files into Immich. The real problem is preserving album structure without duplicating files or rebuilding everything by hand afterwards.

This tool exists to solve that gap:

- upload assets only once
- keep Apple Photos album membership recoverable
- avoid one exported copy per album
- keep the migration repeatable and resume-safe
- reduce the manual cleanup work after import

It is a migration workflow, not just an uploader.

## Installation

Recommended for end users:

```bash
brew install immich-go
uv tool install osxphotos
brew tap shaisegal/tools
brew trust shaisegal/tools
brew install apple-photos-to-immich
```

If Homebrew refuses to load the tap because it is untrusted, trust either the whole tap or just this Formula:

```bash
brew trust shaisegal/tools
brew trust --formula shaisegal/tools/apple-photos-to-immich
```

Homebrew stores trusted entries in `~/.homebrew/trust.json` by default, or in `${XDG_CONFIG_HOME}/homebrew/trust.json` if `XDG_CONFIG_HOME` is set.

Why Homebrew is the best default here:

- simple one-command installation and upgrades
- isolated Python environment managed by the Formula
- no need to manually create or activate a project venv

If you want to run the repository directly during development instead:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -e ".[dev]"
```

## Quick Start

```bash
apple-photos-to-immich check
apple-photos-to-immich export
apple-photos-to-immich import-assets
apple-photos-to-immich apply-albums
apple-photos-to-immich verify
```

`import-assets` waits for Immich processing by default. `apply-albums` generates or refreshes `album-map.json` automatically when needed.

## Main Advantage

The main advantage of this tool is that it separates asset upload from album reconstruction.

Without that separation, Apple Photos albums usually push users toward one of two bad options:

- duplicate files into album-specific export folders
- upload everything once, but lose album structure

This project avoids both. It exports assets once, imports them once, and then recreates album membership from Apple Photos metadata.

## Features

- Export and upload assets only once
- Restore album membership without duplicating files
- Preserve Live Photos, videos, RAW/JPEG pairs, and metadata as well as possible
- Support resume-safe, idempotent album synchronization
- Provide dry-run mode for write operations
- Verify results with match and missing reports

## Prerequisites

```bash
brew install immich-go
uv tool install osxphotos
```

If you want to try the repository locally without installing the Homebrew package first:

```bash
./apple-photos-to-immich --help
```

Important macOS note:

```text
System Settings
-> Privacy & Security
-> Full Disk Access
-> Enable Terminal and/or iTerm
```

If `osxphotos info` fails while copying `Photos.sqlite`, the usual reason is missing Full Disk Access or the Photos app still being open.

## Configuration

The tool uses `config.toml`.

```bash
cp config.example.toml config.toml
```

For safe repo-local testing without writes outside the project:

```bash
cp config.local.example.toml config.toml
```

Important fields:

- `[immich].server`
- `[immich].api_key`
- `[immich].skip_verify_ssl`
- `[photos].library`
- `[photos].album_prefix`
- `[photos].system_album_prefix`
- `[paths].export_dir`
- `[paths].meta_dir`
- `[runtime].osxphotos_python`

Notes:

- If `osxphotos` is only installed via `uv tool install osxphotos`, `make-map` can automatically use the Python interpreter from that tool environment.
- If auto-detection does not work, set `runtime.osxphotos_python`, for example `/Users/USERNAME/.local/share/uv/tools/osxphotos/bin/python`.
- Regular Apple albums are recreated with their plain album names.
- System albums are recreated as `<system_album_prefix>: <name>`, for example `Apple Photos: Videos`.
- `photos.album_prefix` is kept as a legacy compatibility setting so existing `Apple Photos/Albums/...` and `Apple Photos/System/...` names can be recognized and renamed automatically during `apply-albums`.

## CLI

Direct entry points:

```bash
apple-photos-to-immich --help
python3 -m apple_photos_to_immich --help
```

Alternative entry points:

```bash
./01_export_once.sh --test
./02_import_assets.sh
python3 03_make_album_map.py
python3 04_apply_albums_to_immich.py --dry-run
python3 05_verify.py
```

The primary interface is the `apple-photos-to-immich` CLI.

Available commands:

```text
check
export
import-assets
wait-for-immich
make-map
apply-albums
verify
all
```

`all` supports resume via `META_DIR/run-state.json`.
If a previous run stopped after `export` or `make-map`, a new `all` run resumes at the next unfinished step by default.

## Where Data Is Stored

If you use `config.local.example.toml`, the tool writes everything into the repo-local `.local` directory:

- exported media: `.local/export`
- metadata and reports: `.local/meta`
- logs: `.local/meta/logs`
- resume state: `.local/meta/run-state.json`

Example in this project:

```text
/Users/fabian/Pictures/apple-photos-to-immich-mvp/.local/export
/Users/fabian/Pictures/apple-photos-to-immich-mvp/.local/meta
```

## Recommended Flow

1. `apple-photos-to-immich check`
2. `apple-photos-to-immich export --test`
3. `apple-photos-to-immich export`
4. `apple-photos-to-immich import-assets`

Before continuing with the next steps, wait until Immich has finished processing the uploaded assets. The default `import-assets` command already waits for server-side jobs unless you explicitly pass `--no-wait`.

`apply-albums` generates `album-map.json` automatically if it does not exist yet, and refreshes it if it is older than the latest export data, so in the normal flow you usually do not need to call `make-map` manually.

5. `apple-photos-to-immich apply-albums --dry-run`
6. `apple-photos-to-immich apply-albums`
7. `apple-photos-to-immich verify`

Useful variants:

- `apple-photos-to-immich all --test`
- `apple-photos-to-immich all --dry-run`
- `apple-photos-to-immich all --no-resume`
- `apple-photos-to-immich all --reset-state`

The same calls also work through the repo-local launcher:

- `./apple-photos-to-immich check`
- `./apple-photos-to-immich export --test`
- `./apple-photos-to-immich import-assets --dry-run`
- `./apple-photos-to-immich import-assets`
- `./apple-photos-to-immich apply-albums --dry-run`

## Dry Runs

Dry runs show the real target paths and do not perform write operations.

Export:

```bash
apple-photos-to-immich export --dry-run
apple-photos-to-immich export --update
```

Import:

```bash
apple-photos-to-immich import-assets --dry-run
apple-photos-to-immich import-assets
apple-photos-to-immich import-assets --no-wait
apple-photos-to-immich wait-for-immich
```

Example output:

```text
INFO: DRY RUN import command: immich-go upload from-folder --server https://immich.home.arpa --api-key ... --manage-heic-jpeg=StackCoverHeic --manage-raw-jpeg=StackCoverRaw --session-tag apple-photos-to-immich --skip-verify-ssl /Users/fabian/Pictures/apple-photos-to-immich-mvp/.local/export
```

Album sync:

```bash
apple-photos-to-immich apply-albums --dry-run
```

Per album, the tool logs:

- how many assets were matched
- how many are already present in the album
- how many would be added
- how many Apple UUIDs are still missing

## Import Behavior

`import-assets` starts `immich-go` and then, by default, waits for Immich's server-side jobs.

Important:

- `Upload complete` in `immich-go` primarily means that the client has finished its upload queue
- Immich may still have active or waiting jobs afterwards
- `Pending` and `Errors` in the `immich-go` view are more important than the completion box alone
- even if the `immich-go` completion box appears and is confirmed, the wrapper continues running and polls `GET /api/jobs`
- `import-assets` waits by default until `active=0`, `waiting=0`, and `delayed=0`
- `import-assets --no-wait` exits immediately after `immich-go`
- `apply-albums` generates `album-map.json` automatically if it is missing
- `wait-for-immich` performs the same check separately if you only want to wait for server state

Practical consequences:

- after a larger import, `import-assets` is usually enough
- in the normal flow you usually do not need to call `make-map` separately anymore
- do not start `apply-albums --dry-run` while Immich is still active or waiting
- if only `paused` jobs remain, the tool reports Immich as idle but warns that no further progress will happen until those queues are resumed

## Design Benefits

- Central Python CLI instead of scattered one-off scripts
- TOML configuration instead of distributed shell-env configuration
- Consistent path resolution for `~` and relative paths
- Shared logging layer with console and file logging
- Central Immich API client with retry logic
- Idempotent album synchronization for resume scenarios
- Fallback matching via filename plus creation date
- Match and verify reports under `META_DIR`, including per-album drift details
- Resume state for `all`
- Repo-local launcher `./apple-photos-to-immich`
- Unit tests for config, matching, state, and Apple Photos helpers

## Important Reports

- `album-map.json`
- `match-report.json`
- `verify-report.json`
- `run-state.json`
- `missing-uuids.txt`
- `logs/migration.log`

`verify-report.json` now includes per album:

- whether the album exists in Immich
- expected vs. actual asset count
- missing asset IDs in Immich
- extra asset IDs in Immich
- a small sample of unmatched UUIDs

`match-report.json` also includes:

- total number of matched assets
- missing Apple UUIDs
- duplicate UUID candidates in Immich
- match type per asset, for example `uuid` or `filename_date`

## Homebrew

Homebrew installation for normal usage:

```bash
brew tap shaisegal/tools
brew trust shaisegal/tools
brew install apple-photos-to-immich
```

After that, the command is available globally:

```bash
apple-photos-to-immich --help
```

Use the repo-local launcher only if you are working from this repository checkout:

```bash
./apple-photos-to-immich --help
```

## Known Limitations

- Apple People/Faces are not transferred 1:1 into Immich.
- Smart Albums can only be recreated as static virtual albums.
- Classic Shared Albums are only partially recoverable. Album names can now be rebuilt more reliably, but assets from other people in a shared album may still be missing because Apple Photos often shows them without keeping exportable local originals in the library.
- Uploading still runs through `immich-go`; part of the resume semantics depends on its behavior.
- API-based steps still require `requests`.
