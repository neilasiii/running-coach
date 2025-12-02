#!/bin/bash
#
# Simple Morning Report - Non-AI version for cron automation
#
# Uses Python scripts to generate health summary without requiring Claude Code
# Sends Termux notification with key metrics and clickable HTML report
#
# Designed to run as a cron job at 0900 daily
#

set -e  # Exit on error

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Log file for debugging
LOG_FILE="$PROJECT_ROOT/data/morning_report.log"
echo "=== Morning Report (Simple): $(date) ===" >> "$LOG_FILE"

# 1. Sync latest Garmin data (incremental - only fetches new data)
echo "Syncing latest Garmin data..." >> "$LOG_FILE"
cd "$PROJECT_ROOT"

# Use venv Python if available
if [ -f "$PROJECT_ROOT/venv/bin/python3" ]; then
    PYTHON="$PROJECT_ROOT/venv/bin/python3"
else
    PYTHON="python3"
fi

"$PYTHON" "$PROJECT_ROOT/src/garmin_sync.py" --quiet >> "$LOG_FILE" 2>&1 || {
    echo "Garmin sync failed" >> "$LOG_FILE"
    termux-notification --title "Morning Report Error" --content "Failed to sync Garmin data" --channel morning-report
    exit 1
}

# 2. Fetch current weather
echo "Fetching weather..." >> "$LOG_FILE"
WEATHER=$("$PYTHON" "$PROJECT_ROOT/src/get_weather.py" 2>> "$LOG_FILE") || {
    echo "Weather fetch failed, continuing without weather data..." >> "$LOG_FILE"
    WEATHER="Weather data unavailable"
}

# 3. Generate enhanced text report for notification
echo "Generating enhanced report..." >> "$LOG_FILE"
REPORT=$("$PYTHON" "$PROJECT_ROOT/src/generate_enhanced_report.py" "$WEATHER" 2>> "$LOG_FILE") || {
    echo "Enhanced report generation failed" >> "$LOG_FILE"
    termux-notification --title "Morning Report Error" --content "Failed to generate report" --channel morning-report
    exit 1
}

# Extract brief summary for notification (first 10 lines or so)
BRIEF_SUMMARY=$(echo "$REPORT" | head -15 | grep -E "^(Recovery:|Sleep:|Workout:|Weather:|⚡)" | head -5 || echo "Morning Report Ready")

# 4. Generate enhanced HTML report for click action
DETAILED_REPORT_HTML="$PROJECT_ROOT/data/morning_report_detailed.html"

echo "Generating enhanced HTML report..." >> "$LOG_FILE"
"$PYTHON" "$PROJECT_ROOT/src/generate_enhanced_html.py" "$WEATHER" > "$DETAILED_REPORT_HTML" 2>> "$LOG_FILE" || {
    echo "Enhanced HTML generation failed" >> "$LOG_FILE"
    # Continue anyway - we still have text report
}

# 5. Copy HTML to Downloads folder (accessible via file:// URIs)
DOWNLOADS_HTML="$HOME/storage/downloads/morning_report.html"
if [ -f "$DETAILED_REPORT_HTML" ]; then
    cp "$DETAILED_REPORT_HTML" "$DOWNLOADS_HTML" 2>> "$LOG_FILE"
fi

# 6. Send notification with clickable action
echo "Sending notification..." >> "$LOG_FILE"

termux-notification \
    --title "🏃 Morning Training Report" \
    --content "$BRIEF_SUMMARY" \
    --channel morning-report \
    --priority high \
    --sound \
    --button1 "View Details" \
    --button1-action "termux-share $DOWNLOADS_HTML"

echo "Report sent successfully" >> "$LOG_FILE"
echo "$BRIEF_SUMMARY" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
