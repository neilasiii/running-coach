#!/bin/bash
#
# VDOT Calculator - Wrapper for vdot_calculator.py
#
# Calculate VDOT from races, generate training paces,
# analyze workout performance, and track fitness progression.
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Run Python script
python3 "$PROJECT_ROOT/src/vdot_calculator.py" "$@"
