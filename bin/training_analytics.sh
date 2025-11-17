#!/bin/bash
#
# Training Load Analytics - Wrapper for training_analytics.py
#
# Provides easy access to training load metrics:
# - TSS (Training Stress Score)
# - CTL (Chronic Training Load / Fitness)
# - ATL (Acute Training Load / Fatigue)
# - TSB (Training Stress Balance / Form)
# - ACWR (Acute:Chronic Workload Ratio)
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Run Python script
python3 "$PROJECT_ROOT/src/training_analytics.py" "$@"
