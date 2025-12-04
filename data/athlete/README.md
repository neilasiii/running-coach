# Athlete Context Files

This directory contains athlete-specific context files that all coaching agents must read before providing guidance.

## Active Context Files (Required Reading)

### Core Training Context
- **goals.md** - Performance goals, training objectives
- **current_training_status.md** - Current VDOT, training paces, phase status
- **training_preferences.md** - Schedule constraints, dietary requirements, training philosophy
- **training_history.md** - Injury history, past training patterns
- **upcoming_races.md** - Race schedule, time goals, taper timing
- **communication_preferences.md** - Detail level (BRIEF/STANDARD/DETAILED) and response format

### Health Data
- **../health/health_data_cache.json** - Objective metrics from Garmin Connect (use this, not health_profile.md)

## File Organization Principles

Each file has a specific purpose to avoid redundancy:

| File | Purpose | Single Source of Truth For |
|------|---------|----------------------------|
| `goals.md` | What the athlete wants to achieve | Performance targets, long-term objectives |
| `training_preferences.md` | How the athlete prefers to train | Schedule, dietary requirements, coaching style |
| `training_history.md` | What has happened in the past | Injuries, equipment, past training patterns |
| `current_training_status.md` | Current fitness state | VDOT, training paces, current plan |
| `upcoming_races.md` | Future races and past race results | Race calendar, priority, post-race reviews |
| `communication_preferences.md` | Response format preferences | Detail level, proactive suggestions |

## Cross-References

Files reference each other to avoid duplication:
- `current_training_status.md` → references `training_preferences.md` for schedule
- `current_training_status.md` → references `training_history.md` for injury details
- All files → use `health_data_cache.json` for current health metrics

## Deprecated Files

- **health_profile.md.deprecated** - Replaced by direct access to `health_data_cache.json`
  - Reason: Frequently outdated, redundant with cache
  - Agents should read cache directly instead

## Updating Context Files

When making updates:
1. Check if information already exists elsewhere
2. Update only the single source of truth
3. Use cross-references instead of duplicating
4. Keep files focused on their specific purpose
