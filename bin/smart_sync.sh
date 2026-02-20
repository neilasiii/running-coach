#!/usr/bin/env bash
#
# smart_sync.sh — thin shim; cache-age check is now native Python.
#
# Usage:
#   bash bin/smart_sync.sh [--force]
#
# All logic (cache freshness, SQLite recording) lives in skills/garmin_sync.py.
# This shim exists so scripts and systemd units that call smart_sync.sh
# continue to work without modification.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

exec python3 "$PROJECT_ROOT/cli/coach.py" sync "$@"
