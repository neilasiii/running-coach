# Agent Quick Reference: Planned Workouts System

## Overview

The Planned Workouts system stores the athlete's scheduled training plan workouts extracted from baseline plans. This provides agents with quick access to planned workouts, completion status, and adjustment history.

## Key Concepts

**Planned Workout**: A scheduled workout extracted from the baseline training plan
- Contains: date, domain (running/strength/mobility/nutrition), workout details, phase, week number
- Status: `planned`, `completed`, `skipped`, or `modified`
- Tracks: actual performance when completed, adjustments with reasoning

**Data Location**: `data/plans/planned_workouts.json`

## Common Agent Use Cases

### 1. Check Today's Workout

```bash
bash bin/planned_workouts.sh list --today -v
```

**When to use**: Beginning of coaching session, morning reports, daily guidance

**Returns**: All workouts scheduled for today with full details including:
- Workout type and duration
- Pace/HR targets
- Week number and training phase
- Current status

### 2. View Upcoming Schedule

```bash
# Next 7 days
bash bin/planned_workouts.sh list --upcoming 7 -v

# Next 14 days
bash bin/planned_workouts.sh list --upcoming 14 -v
```

**When to use**: Weekly planning, assessing training load, making adjustments

**Returns**: All workouts in the next N days

### 3. Check Week Summary

```bash
bash bin/planned_workouts.sh summary --week 3
```

**When to use**: Evaluating adherence, weekly check-ins, progress tracking

**Returns**:
- Total workouts planned vs completed
- Completion rate
- Breakdown by domain (running, strength, mobility)

### 4. Review Recent Completion Status

```bash
# List all completed workouts
bash bin/planned_workouts.sh list --status completed -v

# List skipped workouts
bash bin/planned_workouts.sh list --status skipped -v
```

**When to use**: Understanding training adherence, identifying patterns

### 5. Check Specific Training Phase

```bash
# View all workouts in current phase
bash bin/planned_workouts.sh list --phase recovery -v
bash bin/planned_workouts.sh list --phase base_building -v
bash bin/planned_workouts.sh list --phase early_quality -v
```

**When to use**: Phase-specific guidance, ensuring phase-appropriate adjustments

## Updating Workouts

### Mark Workout as Completed

When athlete reports completing a workout:

```bash
bash bin/planned_workouts.sh complete <workout_id> \
  --garmin-id 21089008771 \
  --duration 32 \
  --distance 3.2 \
  --pace "10:15/mile" \
  --hr 138 \
  --notes "Felt great, extended by 5 minutes"
```

**Required**: workout_id (get from `list` command)
**Optional**: All performance data

### Mark Workout as Skipped

When athlete misses a workout:

```bash
bash bin/planned_workouts.sh skip <workout_id> \
  --reason "Poor sleep, prioritized recovery"
```

### Add Adjustment to Workout

When modifying the planned workout:

```bash
bash bin/planned_workouts.sh adjust <workout_id> \
  --reason "Recovery metrics show elevated RHR" \
  --change "Reduced from 45 min to 30 min easy run" \
  --modified-by "vdot-running-coach"
```

**Important**: This marks workout as "modified" and preserves the adjustment history

## Integration with Other Systems

### Health Data Cache

After marking a workout complete, link it to the Garmin activity:

1. Check `data/health/health_data_cache.json` for the activity ID
2. Use `--garmin-id` flag when marking complete
3. This creates bidirectional link: workout → activity

### Baseline Plan

The planned workouts are extracted from:
`data/plans/gasparilla_half_marathon_baseline_plan.md`

To re-extract after plan updates:

```bash
python3 src/extract_baseline_plan.py
```

**Warning**: This clears all existing completion/adjustment data!

## Example Agent Workflow

### Morning Report

```bash
# 1. Check today's workout
bash bin/planned_workouts.sh list --today -v

# 2. Check week progress
bash bin/planned_workouts.sh summary --week 1

# 3. Check upcoming workouts
bash bin/planned_workouts.sh list --upcoming 3 -v

# 4. Provide guidance based on scheduled workout and recent completion rate
```

### Post-Workout Session

```bash
# 1. Get today's planned workout
bash bin/planned_workouts.sh list --today -v

# 2. Athlete reports completion
# Extract workout_id from output

# 3. Mark as completed with actual performance
bash bin/planned_workouts.sh complete <workout_id> \
  --duration 30 \
  --distance 3.1 \
  --pace "10:20/mile" \
  --hr 140 \
  --notes "Felt easy, good run"
```

### Weekly Check-In

```bash
# 1. Review last week's adherence
bash bin/planned_workouts.sh summary --week 1

# 2. Check upcoming week
bash bin/planned_workouts.sh list --week 2 -v

# 3. Identify any needed adjustments based on completion rate and athlete feedback
```

## Python API

For more complex operations, use the PlannedWorkoutManager directly:

```python
from planned_workout_manager import PlannedWorkoutManager

manager = PlannedWorkoutManager()

# Get today's workouts
today_workouts = manager.get_today_workouts()

# Get specific workout
workout = manager.get_workout(workout_id)

# Mark completed
manager.mark_completed(workout_id, {
    "garmin_activity_id": 21089008771,
    "date_completed": "2025-12-02",
    "duration_minutes": 30,
    "avg_hr": 140,
    "notes": "Great run"
})

# Add adjustment
manager.add_adjustment(
    workout_id,
    reason="Recovery needs",
    change="Reduced duration",
    modified_by="vdot-running-coach"
)
```

## Best Practices

1. **Check planned workouts at session start** - Understand what athlete expected to do
2. **Update status after athlete reports** - Keep system current
3. **Add adjustments with clear reasoning** - Document decision-making for future reference
4. **Link to Garmin activities** - Maintain connection between plan and actual data
5. **Review adherence weekly** - Use completion rates to assess plan viability
6. **Respect the baseline plan** - Major deviations should be discussed with athlete

## Data Schema

Each planned workout contains:

```json
{
  "id": "unique-id",
  "date": "2025-12-02",
  "week_number": 1,
  "phase": "recovery",
  "domain": "running",
  "workout": {
    "type": "easy_run",
    "duration_minutes": 25,
    "description": "25 min Easy (E pace, keep HR <140 bpm)",
    "pace_target": "E pace 10:20-10:40/mile",
    "hr_target": "HR <140 bpm",
    "intensity": "easy"
  },
  "status": "planned",
  "actual_performance": null,
  "adjustments": []
}
```

## Troubleshooting

**Q: Workout IDs are long UUIDs - how do I use them?**
A: Copy the ID from `list -v` output, or use date-based filtering to narrow down workouts

**Q: Can I modify the baseline plan markdown?**
A: Yes, but you must re-run `python3 src/extract_baseline_plan.py` to update planned workouts (this clears completion data!)

**Q: Should I update planned workouts or just make notes in conversation?**
A: Update planned workouts when making durable changes. Use conversation for ephemeral guidance.

**Q: What if athlete wants to swap workout days?**
A: Delete one workout, get the other's ID, and update its date field via adjust command or Python API
