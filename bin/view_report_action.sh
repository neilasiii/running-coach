#!/bin/bash
REPORT="$HOME/running-coach/data/morning_report.md"
if [ -f "$REPORT" ]; then
    # Copy to shared storage so Markor can access it
    # (Termux private dir /data/data/com.termux is not accessible to other apps)
    SHARED_DIR="/storage/emulated/0/Documents"
    mkdir -p "$SHARED_DIR"
    cp "$REPORT" "$SHARED_DIR/morning_report.md"
    termux-open "$SHARED_DIR/morning_report.md"
fi
