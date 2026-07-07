#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

exec ./apple-photos-to-immich export "$@"
