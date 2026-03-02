# Streprogen Integration Design

## Overview

Integrate streprogen library for structured, periodized strength programming while maintaining compatibility with the existing FinalSurge-based running schedule and AI-powered workout generation.

## Architecture

### Current System
- **Supplemental Workout Generator** (`src/supplemental_workout_generator.py`)
  - Generates individual strength workouts on-demand (one workout at a time)
  - Uses AI to select days and focus areas
  - Uses templates (Session A/B/C) for workout structure
  - Uploads workouts to Garmin immediately

### New System with Streprogen

#### 1. Multi-Week Program Generation
- **Program Generator** (`src/streprogen_program_generator.py`)
  - Creates 4-8 week periodized programs using streprogen
  - Includes 3 session types: A (Squat), B (Hinge), C (Unilateral)
  - Stores program data in `data/strength_programs/`

#### 2. Program Storage Format
```json
{
  "program_id": "2025-12-27_foundation",
  "phase": "Foundation",
  "start_date": "2025-12-30",
  "end_date": "2026-01-26",
  "current_week": 1,
  "parameters": {
    "duration_weeks": 4,
    "intensity": 75,
    "units": "kg"
  },
  "sessions": {
    "A": {
      "name": "Squat + Push",
      "exercises": [...]
    },
    "B": {
      "name": "Hinge + Pull",
      "exercises": [...]
    },
    "C": {
      "name": "Unilateral + Velocity",
      "exercises": [...]
    }
  },
  "weekly_workouts": [
    {
      "week": 1,
      "session": "A",
      "date": "2025-12-30",
      "workout_detail": "..."
    },
    ...
  ]
}
```

#### 3. Daily Workout Extraction
- **Workout Extractor** (in `supplemental_workout_generator.py`)
  - Reads current program from storage
  - Finds workout for specific date
  - Converts streprogen output to Garmin format
  - Uploads to Garmin Connect

#### 4. AI Integration Points

**AI determines:**
- Which session (A/B/C) to schedule on which days
- Weekly intent (BUILD/HOLD/RECOVER)
- Intensity adjustments based on running schedule
- When to regenerate the program

**Streprogen determines:**
- Progressive overload (week-to-week weight increases)
- Set/rep schemes (optimized across weeks)
- Exercise sequencing within sessions

## Handling Incomplete/Missed Workouts

### Smart Adjustment Approach

The system tracks completion status and adjusts future workouts based on adherence:

#### Completion Tracking
```json
{
  "program_id": "2025-12-27_foundation",
  "completion_history": [
    {
      "date": "2025-12-30",
      "session": "A",
      "week": 1,
      "completed": true,
      "notes": "Felt strong"
    },
    {
      "date": "2026-01-02",
      "session": "B",
      "week": 1,
      "completed": false,
      "reason": "running_fatigue"
    }
  ]
}
```

#### Adjustment Logic

1. **Miss 1 workout**: Continue as planned (no adjustment)
   - Example: Skip week 2 session A, proceed to week 3 session A as scheduled

2. **Miss 2+ workouts in same week**: Reduce intensity for next week
   - Use previous week's weights/sets/reps for that session type
   - Example: Miss both week 2 workouts → week 3 uses week 1's prescription

3. **Miss entire week**: Repeat that week's prescription
   - Example: Miss all week 2 workouts → next scheduled workouts use week 2's prescription

4. **Miss >30% of workouts over 2 weeks**: Trigger program regeneration
   - Archive current program
   - Generate new program starting at current fitness level
   - Notify athlete of reset

#### Completion Detection

- **Automatic**: Check Garmin for strength activities on scheduled dates
- **Manual override**: Allow marking complete/incomplete via commands
- **Activity matching**: Match activity type (strength training) and approximate duration

#### AI Integration

Morning report recommendations:
- "You missed Session A this week. Consider doing Session A today instead of Session B."
- "Completed 1/2 strength workouts this week. Add one session on rest day?"

Weekly summary:
- "Completed 6/8 strength sessions this month (75%). Good adherence!"
- "Missed 3 consecutive workouts. Consider reducing running volume or regenerating strength program."

### Implementation Requirements

1. **Completion Tracker** (`src/streprogen_completion_tracker.py`)
   - Track completion status for each scheduled workout
   - Query Garmin activities to auto-detect completion
   - Provide commands to manually mark complete/incomplete
   - Calculate adherence metrics (weekly, monthly)

2. **Smart Workout Selector** (in `supplemental_workout_generator.py`)
   - Check completion history before selecting next workout
   - Apply adjustment logic based on missed workouts
   - Return appropriate week's prescription for session type

3. **Program Metadata** (in `data/strength_programs/current_program.json`)
   - Add `completion_history` array
   - Add `adherence_metrics` object
   - Track last completed week per session type

## Implementation Plan

### Phase 1: Program Generator (Foundational)
1. Create `src/streprogen_program_generator.py`
   - Define runner-specific exercises for sessions A/B/C
   - Generate 4-week programs with proper periodization
   - Export to JSON format for storage
   - Lower intensity default (75 instead of 83) for runners

2. Create program storage system
   - Directory: `data/strength_programs/`
   - Current program: `data/strength_programs/current_program.json`
   - Archive: `data/strength_programs/archive/`

### Phase 2: Integration with Current System
1. Modify `supplemental_workout_generator.py`
   - Check for active streprogen program
   - If exists: extract workout for date
   - If not: fallback to current template system
   - Convert streprogen output to Garmin format

2. Add program management commands
   - Generate new program: `python3 src/streprogen_program_generator.py --generate`
   - View current program: `python3 src/streprogen_program_generator.py --view`
   - Archive old program: automatic on regeneration

### Phase 3: Intelligent Scheduling
1. AI-powered session scheduling
   - Read FinalSurge running schedule
   - Determine optimal days for sessions A/B/C
   - Map streprogen program workouts to calendar dates

2. Program regeneration logic
   - Every 4 weeks (program completion)
   - On significant running schedule changes
   - On athlete request (injury, plateau, etc.)

## Key Design Principles

1. **Backward Compatibility**: System must work with or without streprogen
   - If no program exists, fall back to templates
   - Gradual migration path

2. **Running-First Philosophy**: Strength supports running, never compromises it
   - Lower default intensity (75 vs 83)
   - Scheduled 48+ hours before quality running
   - Automatic intensity reduction during high running load

3. **Minimal Soreness**: Exercises chosen for runner needs
   - Foundation phase exercises (goblet squat, RDL, lunges)
   - No exercises that interfere with running (heavy back squats, deadlifts)
   - Emphasis on time-under-tension, not max strength

4. **Progressive Overload**: Let streprogen handle progression
   - Automatic weekly weight increases (1.5-2%)
   - Rep scheme optimization across sets
   - Multi-week planning ensures proper periodization

## Example Workflow

### Initial Program Generation
```bash
# Generate 4-week foundation program
python3 src/streprogen_program_generator.py --generate --duration 4 --phase foundation

# View program summary
python3 src/streprogen_program_generator.py --view
```

### Daily Sync (Automated)
```bash
# Sync runs automatically via Discord bot or cron
bash bin/sync_garmin_data.sh

# Supplemental generator checks:
# 1. Active streprogen program exists?
# 2. Workout scheduled for today/future dates?
# 3. Extract workout from program
# 4. Upload to Garmin
```

### Program Completion
```bash
# After 4 weeks, automatically:
# 1. Archive current program
# 2. Generate new program (next phase or repeat)
# 3. Notify athlete of progression
```

## File Structure

```
running-coach/
├── src/
│   ├── streprogen_program_generator.py  # NEW: Multi-week program generator
│   ├── streprogen_workout_extractor.py  # NEW: Extract daily workouts from program
│   └── supplemental_workout_generator.py  # MODIFIED: Integrate streprogen
│
├── data/
│   └── strength_programs/
│       ├── current_program.json         # Active program
│       ├── program_metadata.json        # Program history, progression tracking
│       └── archive/                     # Completed programs
│           ├── 2025-12-01_foundation.json
│           └── 2025-11-01_foundation.json
│
└── docs/
    └── STREPROGEN_INTEGRATION_DESIGN.md  # This file
```

## Benefits

1. **Structured Periodization**: Proper 4-8 week training cycles instead of random workouts
2. **Progressive Overload**: Automatic weight progression based on proven principles
3. **Better Planning**: Athlete can see 4 weeks ahead, plan around travel/races
4. **Reduced Decision Fatigue**: No need to decide sets/reps each workout
5. **Proven Framework**: Streprogen based on established strength training science
6. **Flexibility**: Still allows AI to adjust based on running schedule and recovery

## Migration Path

1. **Week 1**: Generate first streprogen program (Foundation phase)
2. **Week 1-4**: Run both systems in parallel (streprogen + templates), verify output
3. **Week 5**: Switch to streprogen-only if working well
4. **Week 8**: First program regeneration, evaluate progression

## Open Questions

1. **Intensity Level**: Start at 75 or lower for runners? (vs default 83)
2. **Program Duration**: 4 weeks or 8 weeks for first cycle?
3. **Session Frequency**: Keep 2 sessions/week or increase to 3 in easy weeks?
4. **Exercise Selection**: Fixed exercises or allow AI to vary exercises within sessions?

## Next Steps

1. Implement `streprogen_program_generator.py`
2. Create program storage system
3. Test program generation with runner-specific exercises
4. Implement `streprogen_completion_tracker.py` for tracking missed/completed workouts
5. Add smart workout selection logic to `supplemental_workout_generator.py`
6. Integrate completion tracking with Garmin activity detection
7. Test end-to-end workflow (generate → extract → track → adjust → upload)
