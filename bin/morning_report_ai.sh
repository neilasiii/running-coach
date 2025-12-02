#!/bin/bash
#
# AI-Powered Morning Report - Daily health and training summary with Claude Code
#
# Uses Claude Code in headless mode to generate intelligent training recommendations
# based on recent health data, recovery metrics, and scheduled workouts.
#
# Designed to run as a cron job at 0715 daily
#

set -e  # Exit on error

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Log file for debugging
LOG_FILE="$PROJECT_ROOT/data/morning_report.log"
echo "=== Morning Report (AI): $(date) ===" >> "$LOG_FILE"

# 1. Sync Garmin data (quiet mode, last 7 days)
echo "Syncing Garmin data..." >> "$LOG_FILE"
cd "$PROJECT_ROOT"
bash bin/sync_garmin_data.sh --days 7 --quiet >> "$LOG_FILE" 2>&1 || {
    echo "Garmin sync failed" >> "$LOG_FILE"
    termux-notification --title "Morning Report Error" --content "Failed to sync Garmin data" --channel morning-report
    exit 1
}

# 2. Generate AI-powered report using Claude Code (headless mode)
echo "Generating AI report..." >> "$LOG_FILE"

# Create the prompt for Claude
PROMPT="Please analyze my current training readiness and provide today's workout recommendations.

**Context:**
- Read my latest health data from data/health/health_data_cache.json
- Read my athlete context files from data/athlete/ (especially goals.md, training_preferences.md, upcoming_races.md)
- Check for scheduled workouts in the health cache

**Analysis Required:**
1. Recovery status based on:
   - Last night's sleep (duration, quality score)
   - Resting heart rate (recent average vs baseline)
   - Training readiness score and recovery time
   - Recent training load (last 3-7 days)

2. Today's workout recommendations including:
   - If a run is scheduled: should it proceed as planned, be modified, or replaced?
   - Strength training opportunities (if appropriate given recovery)
   - Mobility work recommendations
   - Walking/easy movement if recovery is needed

**Output Format (concise for notification):**
Keep the response under 300 characters for a mobile notification. Use this structure:

Recovery: [1-2 word status]
Today: [Primary workout recommendation]
Alt: [Alternative if needed]
Note: [Key insight]

Example:
Recovery: Good (7.2h sleep, RHR 45)
Today: Easy 45min OR Tempo 5x3min as scheduled
Alt: Strength (upper body) if fatigued
Note: Marathon in 8 weeks - base phase

Be specific with workout types, durations, and intensities. Prioritize the scheduled workout if recovery allows."

# Run Claude Code in headless mode
REPORT=$(claude -p "$PROMPT" \
    --output-format text \
    --permission-mode acceptEdits \
    --max-turns 3 \
    2>> "$LOG_FILE") || {
    echo "Claude Code failed" >> "$LOG_FILE"
    termux-notification --title "Morning Report Error" --content "Failed to generate AI report" --channel morning-report
    exit 1
}

# 3. Send notification
echo "Sending notification..." >> "$LOG_FILE"
termux-notification \
    --title "🏃 Morning Training Report" \
    --content "$REPORT" \
    --channel morning-report \
    --priority high \
    --sound

echo "Report sent successfully" >> "$LOG_FILE"
echo "$REPORT" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
