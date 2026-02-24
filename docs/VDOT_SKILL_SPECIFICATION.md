# VDOT Running Coach Skill Specification

## Overview

An OpenClaw skill implementing Jack Daniels' VDOT methodology for calculating training paces and race predictions. This fills a gap in the ClawHub ecosystem - no existing skill provides VDOT-based pace prescription.

## Core Functionality

### 1. VDOT Calculation
```
Input: Race distance + time
Output: VDOT value + all training paces (E, M, T, I, R)

Example:
Q: "What's my VDOT from a 1:55:04 half marathon?"
A: "VDOT 38.3
   Easy: 9:43-10:23/mi
   Marathon: 9:10/mi
   Threshold: 8:28/mi
   Interval: 7:55/mi
   Repetition: 7:31/mi"
```

### 2. Race Time Predictions
```
Input: Current VDOT
Output: Predicted times for all standard distances

Example:
Q: "What races can I run at VDOT 38.3?"
A: "5K: 25:44
    10K: 53:36
    Half Marathon: 1:55:04
    Marathon: 4:00:00"
```

### 3. Training Pace Lookup
```
Input: VDOT + workout type
Output: Specific pace guidance

Example:
Q: "What pace for 5x1000m intervals at VDOT 38.3?"
A: "Interval pace: 7:55/mi (4:55/km)
   Target: 4:55 per 1000m
   Recovery: Easy jog 400m between reps"
```

### 4. Performance Comparison
```
Input: Two race results
Output: Which is better + VDOT equivalent

Example:
Q: "Is a 25:30 5K or 1:54 half better?"
A: "25:30 5K = VDOT 39.1
    1:54:00 half = VDOT 38.8
    The 5K performance is slightly better."
```

## Technical Implementation

### Core Functions (from existing code)

```python
# Leverage your verified calculations:
src/vdot_calculator.py
├── calculate_vdot_from_race(distance, hours, minutes, seconds)
├── get_training_paces(vdot)
├── predict_race_times(vdot)
└── compare_race_results(race1, race2)
```

### Skill Structure

```
vdot-running-coach/
├── SKILL.md                    # Skill documentation
├── package.json                # Dependencies
├── index.js                    # Skill entry point
├── lib/
│   ├── vdot_calculator.py      # Your existing code
│   ├── pace_formatter.js       # Format output
│   └── conversions.js          # Unit conversions (mi/km)
└── tests/
    └── vdot_tests.js           # Validation tests
```

### API Design

```javascript
// Natural language interface
const skill = {
  name: "vdot-running-coach",

  patterns: [
    "calculate VDOT from {distance} in {time}",
    "what's my VDOT from {race_result}",
    "training paces for VDOT {number}",
    "predict race times at VDOT {number}",
    "compare {race1} vs {race2}"
  ],

  actions: {
    calculateVdot: async (distance, time) => {
      // Call Python calculator
      const result = await execPython('vdot_calculator.py', [distance, time]);
      return formatVdotResponse(result);
    },

    getTrainingPaces: async (vdot) => {
      const paces = await execPython('vdot_calculator.py', ['--paces', vdot]);
      return formatPaceTable(paces);
    }
  }
};
```

## User Experience

### Conversational Interface

```
User: "I just ran a half marathon in 1:55:04. What should my easy pace be?"

Agent uses skill:
1. Calls calculateVdot('half', '1:55:04')
2. Returns VDOT 38.3
3. Calls getTrainingPaces(38.3)
4. Returns Easy: 9:43-10:23/mi

Response: "Congrats on your 1:55:04! That's a VDOT of 38.3.
Your easy runs should be 9:43-10:23 per mile."
```

### Integration with Other Skills

```javascript
// Combine with garmin-health-analysis
const recentRace = await garminHealth.getRecentActivity({type: 'race'});
const vdot = await vdotCoach.calculateVdot(recentRace.distance, recentRace.time);
const paces = await vdotCoach.getTrainingPaces(vdot);

// Combine with caldav-calendar
const upcomingWorkout = await calendar.getNextWorkout();
const prescribedPace = await vdotCoach.getPaceForWorkout(upcomingWorkout, vdot);
```

## Advantages Over Existing Solutions

### vs. clawd-coach (HR-based)
- ✅ More precise for track workouts (HR lags, pace immediate)
- ✅ Better for interval training (HR doesn't stabilize in short reps)
- ✅ Standardized methodology (Jack Daniels = gold standard)
- ✅ Race predictions based on proven formulas

### vs. Generic Pace Calculators
- ✅ Integrated with OpenClaw agents
- ✅ Natural language interface
- ✅ Combines with health data skills
- ✅ Can be automated in morning reports

## Validation

Your calculator is **already verified**:
```python
# Example from CLAUDE.md:
calculate_vdot_from_race('half', 1, 55, 4)
# Returns: VDOT 38.3 ✓ (matches official Jack Daniels tables)
```

## Publication to ClawHub

### Skill Metadata

```json
{
  "name": "vdot-running-coach",
  "version": "1.0.0",
  "author": "your-username",
  "description": "Jack Daniels VDOT calculator and training pace prescriptions",
  "category": "Health & Fitness",
  "tags": ["running", "vdot", "jack-daniels", "training-paces", "coaching"],
  "license": "MIT",
  "verified": true,
  "dependencies": {
    "python": "^3.8",
    "numpy": "^1.21.0"
  }
}
```

### Installation

```bash
npx clawhub@latest install vdot-running-coach
```

### Usage Documentation

```markdown
# VDOT Running Coach Skill

Calculate training paces using Jack Daniels' proven VDOT methodology.

## Quick Start

"What's my VDOT from a 25:30 5K?"
"Show training paces for VDOT 45"
"Predict my marathon time at VDOT 50"

## Commands

- Calculate VDOT from race result
- Get training paces (Easy, Marathon, Threshold, Interval, Repetition)
- Predict race times across all distances
- Compare two race performances
```

## Potential Revenue

If the skill gains traction:
- **Freemium Model**: Basic VDOT calc free, advanced features paid
- **Pro Version**: Altitude adjustments, heat/humidity corrections
- **Premium**: Integration with TrainingPeaks, custom periodization

Jack Daniels calculators are popular (V.O2, RunSmartProject, etc.) - ClawHub currently has **zero** VDOT skills!

## Next Steps

1. **Extract skill** from your `src/vdot_calculator.py`
2. **Create skill wrapper** (JavaScript + Python backend)
3. **Test locally** with OpenClaw
4. **Publish to ClawHub** (be first!)
5. **Integrate** with your running coach system
6. **Iterate** based on community feedback

## Resources

- Jack Daniels formulas: Already implemented in `src/vdot_calculator.py`
- OpenClaw skill docs: https://docs.openclaw.ai/skills
- ClawHub publishing: https://docs.openclaw.ai/tools/clawhub
- Skill examples: https://github.com/openclaw/skills
