#!/bin/bash
#
# Performance Predictor - Wrapper for performance_predictor.py
#
# Predict race times with confidence adjustments based on:
# - Current VDOT and VO2 max
# - Training load (fitness/fatigue)
# - Recovery status
# - Race readiness assessment
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Run Python script
python3 "$PROJECT_ROOT/src/performance_predictor.py" "$@"
