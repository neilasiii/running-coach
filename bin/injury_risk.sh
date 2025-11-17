#!/bin/bash
#
# Injury Risk Assessment - Wrapper for injury_risk_ml.py
#
# Analyzes multiple risk factors:
# - ACWR violations
# - Sleep deprivation
# - Elevated resting heart rate
# - Suppressed HRV
# - Low training readiness
# - Training load spikes
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Run Python script
python3 "$PROJECT_ROOT/src/injury_risk_ml.py" "$@"
