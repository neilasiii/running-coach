#!/bin/bash
# Convenience wrapper for planned workout CLI

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT" || exit 1

python3 src/planned_workout_cli.py "$@"
