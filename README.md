# Apple Photos -> Immich Migration Tool

Python CLI for a robust migration from Apple Photos to Immich.

This project exports Apple Photos assets once, uploads them with `immich-go`, and then rebuilds Apple albums through the Immich API. The new CLI replaces the original MVP of loose shell and Python scripts, while keeping the previous entry points as wrappers.

## Why This Exists

The hardest part of an Apple Photos to Immich migration is usually not getting files into Immich. The real problem is preserving album structure without duplicating files or rebuilding everything by hand afterwards.

This tool exists to solve that gap:

- upload assets only once
- keep Apple Photos album membership recoverable
- avoid one exported copy per album
- keep the migration repeatable and resume-safe
- reduce the manual cleanup work after import

It is a migration workflow, not just an uploader.

## Quick Start

```bash
./apple-photos-to-immich check
./apple-photos-to-immich export
./apple-photos-to-immich import-assets
./apple-photos-to-immich apply-albums
./apple-photos-to-immich verify
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
uv tool install osxphotos
brew install immich-go
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -e ".[dev]"
```

If you want to try the tool locally without installing it first:

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

## Publish Checklist

Before publishing:

- replace placeholder GitHub URLs in `pyproject.toml` and `packaging/homebrew/apple-photos-to-immich.rb`
- create a real `LICENSE` file, for example MIT
- review the version in `pyproject.toml`
- create a clean release tag such as `v0.1.0`
- update the Homebrew Formula with the real tarball URL and `sha256`

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
- `[paths].export_dir`
- `[paths].meta_dir`
- `[runtime].osxphotos_python`

Notes:

- If `osxphotos` is only installed via `uv tool install osxphotos`, `make-map` can automatically use the Python interpreter from that tool environment.
- If auto-detection does not work, set `runtime.osxphotos_python`, for example `/Users/USERNAME/.local/share/uv/tools/osxphotos/bin/python`.

## CLI

Direct entry points:

```bash
./apple-photos-to-immich --help
python3 -m apple_photos_to_immich --help
```

Or through the existing wrappers:

```bash
./01_export_once.sh --test
./02_import_assets.sh
python3 03_make_album_map.py
python3 04_apply_albums_to_immich.py --dry-run
python3 05_verify.py
```

The wrapper scripts are kept for compatibility. The primary interface is the `apple-photos-to-immich` CLI.

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

1. `python3 -m apple_photos_to_immich check`
2. `python3 -m apple_photos_to_immich export --test`
3. `python3 -m apple_photos_to_immich export`
4. `python3 -m apple_photos_to_immich import-assets`

Before continuing with the next steps, wait until Immich has finished processing the uploaded assets. The default `import-assets` command already waits for server-side jobs unless you explicitly pass `--no-wait`.

`apply-albums` generates `album-map.json` automatically if it does not exist yet, and refreshes it if it is older than the latest export data, so in the normal flow you usually do not need to call `make-map` manually.

5. `python3 -m apple_photos_to_immich apply-albums --dry-run`
6. `python3 -m apple_photos_to_immich apply-albums`
7. `python3 -m apple_photos_to_immich verify`

Useful variants:

- `python3 -m apple_photos_to_immich all --test`
- `python3 -m apple_photos_to_immich all --dry-run`
- `python3 -m apple_photos_to_immich all --no-resume`
- `python3 -m apple_photos_to_immich all --reset-state`

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
./apple-photos-to-immich export --dry-run
./apple-photos-to-immich export --update
```

Import:

```bash
./apple-photos-to-immich import-assets --dry-run
./apple-photos-to-immich import-assets
./apple-photos-to-immich import-assets --no-wait
./apple-photos-to-immich wait-for-immich
```

Example output:

```text
INFO: DRY RUN import command: immich-go upload from-folder --server https://immich.home.arpa --api-key ... --manage-heic-jpeg=StackCoverHeic --manage-raw-jpeg=StackCoverRaw --session-tag apple-photos-to-immich --skip-verify-ssl /Users/fabian/Pictures/apple-photos-to-immich-mvp/.local/export
```

Album sync:

```bash
./apple-photos-to-immich apply-albums --dry-run
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

## Improvements Over the MVP

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

If you want the tool to work "everywhere" directly, there are two sensible approaches:

1. Repo-local launcher  
   `./apple-photos-to-immich ...`
2. Installation into its own Python environment  
   `.venv/bin/apple-photos-to-immich ...`

I would not ship a real Homebrew package as `brew install` on top of the system Python. Instead, use a Formula with its own Python virtualenv via `Language::Python::Virtualenv`.

Practical flow for your own tap:

1. Version the repository and create a release tag, for example `v0.1.0`
2. Determine the release tarball and its `sha256`
3. Create your own tap repository, for example `yourname/homebrew-tools`
4. Add a Formula `apple-photos-to-immich.rb`
5. Install it via:

```bash
brew tap yourname/tools
brew install apple-photos-to-immich
```

Formula skeleton:

```ruby
class ApplePhotosToImmich < Formula
  include Language::Python::Virtualenv

  desc "Migrate Apple Photos libraries to Immich"
  homepage "https://github.com/yourname/apple-photos-to-immich"
  url "https://github.com/yourname/apple-photos-to-immich/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "REPLACE_WITH_REAL_SHA256"
  license "MIT"

  depends_on "python@3.12"

  resource "requests" do
    url "https://files.pythonhosted.org/packages/source/r/requests/requests-2.34.2.tar.gz"
    sha256 "REPLACE_WITH_REAL_SHA256"
  end

  resource "certifi" do
    url "https://files.pythonhosted.org/packages/source/c/certifi/certifi-2026.6.17.tar.gz"
    sha256 "REPLACE_WITH_REAL_SHA256"
  end

  resource "charset-normalizer" do
    url "https://files.pythonhosted.org/packages/source/c/charset-normalizer/charset_normalizer-3.4.8.tar.gz"
    sha256 "REPLACE_WITH_REAL_SHA256"
  end

  resource "idna" do
    url "https://files.pythonhosted.org/packages/source/i/idna/idna-3.18.tar.gz"
    sha256 "REPLACE_WITH_REAL_SHA256"
  end

  resource "urllib3" do
    url "https://files.pythonhosted.org/packages/source/u/urllib3/urllib3-2.7.0.tar.gz"
    sha256 "REPLACE_WITH_REAL_SHA256"
  end

  def install
    virtualenv_install_with_resources
    bin.install_symlink libexec/"bin/apple-photos-to-immich"
  end

  test do
    assert_match "apple-photos-to-immich", shell_output("#{bin}/apple-photos-to-immich --help")
  end
end
```

A repo-local starter version of that Formula is included at:

`packaging/homebrew/apple-photos-to-immich.rb`

Recommended publication layout:

1. Main source repository: `apple-photos-to-immich`
2. Homebrew tap repository: `homebrew-tools`
3. Formula path inside the tap: `Formula/apple-photos-to-immich.rb`

For this project, that approach makes sense if:

- `config.toml` remains the only config format
- releases are tagged cleanly
- Python dependencies remain stable
- you actually want to distribute the tool outside this repository

## Known Limitations

- Apple People/Faces are not transferred 1:1 into Immich.
- Smart Albums can only be recreated as static virtual albums.
- Uploading still runs through `immich-go`; part of the resume semantics depends on its behavior.
- API-based steps still require `requests`.
