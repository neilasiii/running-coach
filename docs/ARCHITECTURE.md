# Running Coach System Architecture

## Overview

The Running Coach System is a CLI-first application designed for use with [Claude Code](https://docs.claude.com/en/docs/claude-code). It provides personalized training guidance across four coaching domains through specialized AI agents that access athlete context and health data directly from Garmin Connect.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Claude Code (User Interface)             │
│              Interactive conversational coaching             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Coaching Agent Layer                      │
│                    (.claude/agents/*.md)                     │
│  ┌──────────────┬──────────────┬──────────────────────────┐ │
│  │  Running     │  Strength    │  Mobility   │ Nutrition  │ │
│  │  Coach       │  Coach       │  Coach      │ Coach      │ │
│  │  (VDOT)      │  (Runners)   │  (Runners)  │ (Endurance)│ │
│  └──────────────┴──────────────┴──────────────────────────┘ │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Context & Data Layer                       │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Athlete Context (data/athlete/*.md)                │    │
│  │  - Goals, preferences, training history             │    │
│  │  - Current status, upcoming races                   │    │
│  │  - Communication preferences                        │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Health Data (data/health/health_data_cache.json)   │    │
│  │  - Activities, sleep, HR, VO2 max                   │    │
│  │  - Recovery metrics, training load                  │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Workout Library (data/library/*.json)              │    │
│  │  - Pre-built workout templates                      │    │
│  │  - Searchable by domain, type, difficulty           │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Planned Workouts (data/plans/*.json)               │    │
│  │  - Scheduled training plan workouts                 │    │
│  │  - Completion tracking, adjustments                 │    │
│  └─────────────────────────────────────────────────────┘    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  External Data Sources                       │
│  ┌──────────────┬───────────────┬───────────────────────┐   │
│  │  Garmin      │  ICS Calendar │  Weather API          │   │
│  │  Connect API │  (FinalSurge, │  (Open-Meteo)         │   │
│  │              │   TrainingPeaks)│                      │   │
│  └──────────────┴───────────────┴───────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Coaching Agent System

**Location:** `.claude/agents/`

Four specialized coaching agents with domain expertise:

- **`vdot-running-coach.md`** - Jack Daniels VDOT methodology, periodization, pacing
- **`runner-strength-coach.md`** - Runner-specific strength training coordinated with running schedule
- **`mobility-coach-runner.md`** - Mobility and recovery protocols for distance running
- **`endurance-nutrition-coach.md`** - Nutrition and fueling strategies for endurance training

**How They Work:**
- Each agent has a system prompt defining its coaching expertise and guidelines
- Agents automatically read athlete context files before providing guidance
- All agents share access to the same health data and context
- Claude Code loads agents dynamically based on user interaction

### 2. Health Data System

**Primary Script:** `src/garmin_sync.py`

**Data Flow:**
```
Garmin Connect API
    ↓
garminconnect library (OAuth authentication)
    ↓
src/garmin_sync.py (fetch, normalize, de-duplicate)
    ↓
data/health/health_data_cache.json (persistent cache)
    ↓
Coaching Agents (read for decisions)
```

**Key Features:**
- Direct API access via `garminconnect` library (no manual exports)
- OAuth authentication with token caching (`~/.garminconnect/`)
- Incremental sync - tracks last sync date to avoid refetching
- Atomic cache updates - write to temp file, then rename
- De-duplication by timestamp - safe to re-sync date ranges
- Activity type normalization (trail running → running, etc.)

**Supported Data Types:**
- Activities (all types: running, cycling, swimming, strength, walking, yoga, etc.)
- Sleep sessions (duration, stages, quality score)
- VO2 max estimates
- Lactate threshold (HR & pace)
- Resting heart rate (daily)
- Heart rate variability (HRV)
- Training readiness score (0-100)
- Body composition (weight, body fat %, muscle mass)
- Body Battery (energy tracking)
- Stress levels
- Gear stats (equipment mileage tracking)
- Daily steps
- Training load metrics (ATL/CTL/TSB)

**Cache Structure:**
```json
{
  "last_updated": "2025-12-02T10:30:00",
  "last_sync_date": "2025-12-02",
  "activities": [...],
  "sleep_sessions": [...],
  "vo2_max_readings": [...],
  "resting_hr_readings": [...],
  "hrv_readings": [...],
  "training_readiness": [...],
  "weight_readings": [...],
  "scheduled_workouts": [...]
}
```

### 3. Athlete Context Management

**Location:** `data/athlete/`

Context files that personalize coaching:

| File | Purpose |
|------|---------|
| `goals.md` | Performance goals, training objectives |
| `training_preferences.md` | Schedule constraints, workout preferences, dietary requirements |
| `training_history.md` | Injury history, past training patterns |
| `upcoming_races.md` | Race schedule, goal times, taper timing |
| `current_training_status.md` | Current VDOT, training paces, phase |
| `communication_preferences.md` | Detail level (BRIEF/STANDARD/DETAILED) |
| `health_profile.md` | Human-readable health summary |

All coaching agents read these files to provide personalized, context-aware guidance.

### 4. Workout Library System

**Location:** `data/library/workout_library.json`

**Components:**
- `src/workout_library.py` - CRUD operations, search, filtering
- `src/workout_library_cli.py` - Command-line interface
- `bin/workout_library.sh` - Shell wrapper for CLI

**Features:**
- 19+ pre-built workout templates across all coaching domains
- Searchable metadata: domain, type, difficulty, duration, VDOT range, equipment, tags
- JSON-based storage for easy integration
- Template system for workout customization

**Workflow:**
```
Coach searches library
    ↓
Filter by criteria (domain, type, difficulty, etc.)
    ↓
Select workout template
    ↓
Customize for athlete (pace, duration, etc.)
    ↓
Present to user
```

### 5. Planned Workouts System

**Location:** `data/plans/planned_workouts.json`

**Components:**
- `src/planned_workout_manager.py` - Workout plan manager (CRUD)
- `src/planned_workout_cli.py` - CLI interface
- `bin/planned_workouts.sh` - Shell wrapper

**Features:**
- Scheduled workout tracking from baseline training plan
- Completion status (pending, completed, skipped)
- Actual performance data (duration, distance, pace, HR)
- Adjustment history with reasoning
- Week and plan summaries

**Workflow:**
```
Baseline plan created
    ↓
Workouts extracted to JSON
    ↓
Agents check scheduled workouts
    ↓
Mark completed with actual data
    ↓
Track adjustments and deviations
```

**Priority System:**
1. **FinalSurge scheduled workouts** (Priority 1 - from ICS calendar import)
2. **Baseline plan workouts** (Priority 2 - fallback only)

### 6. Calendar Integration

**Import (from external sources):**
- `src/ics_parser.py` - Parse ICS calendar files
- `config/calendar_sources.json` - Calendar URL configuration
- Merges scheduled dates with Garmin workout templates
- Supports FinalSurge, TrainingPeaks, any ICS feed

**Export (to external calendars):**
- `src/ics_exporter.py` - Generate ICS files from scheduled workouts
- `bin/export_calendar.sh` - Shell wrapper for export
- Compatible with Google Calendar, Outlook, Apple Calendar

**Workflow:**
```
External calendar (FinalSurge, TrainingPeaks)
    ↓
ICS feed/file
    ↓
src/ics_parser.py (parse events)
    ↓
Match with Garmin workout templates
    ↓
data/health/health_data_cache.json (scheduled_workouts)
    ↓
src/ics_exporter.py (generate ICS)
    ↓
Import to calendar apps
```

### 7. VDOT Calculator

**Location:** `src/vdot_calculator.py`

**Features:**
- Official Jack Daniels formulas (Percent Max, Oxygen Cost)
- Race distance support: 5K, 10K, half marathon, marathon
- Training pace calculations for all zones: E, M, T, I, R
- Verified accuracy (e.g., half marathon 1:55:04 → VDOT 38.3)

**Usage:**
```python
from src.vdot_calculator import calculate_vdot_from_race

# Half marathon 1:55:04
vdot, paces = calculate_vdot_from_race('half', 1, 55, 4)
# Returns: VDOT 38.3 + all training paces
```

### 8. Weather Integration

**Location:** `src/get_weather.py`

**Features:**
- Current conditions (temp, feels-like, humidity, wind, UV index)
- 6-hour forecast
- Uses Open-Meteo API (free, no API key required)
- Requires `termux-api` for location access (Termux only)

**Coaching Applications:**
- Pace adjustments for heat/humidity
- Hydration and electrolyte strategies
- Clothing recommendations
- UV protection considerations

### 9. Morning Reports (Termux)

**Three Report Formats:**

1. **AI-Powered Brief Report** (`bin/morning_report.sh`)
   - Uses Claude Code in headless mode
   - Incremental sync + AI analysis
   - Concise notification (~300 chars)
   - Clickable "View Details" button
   - Logs to `data/morning_report.log`

2. **Enhanced Text Report** (`bin/show_detailed_report.sh`)
   - Terminal-based dashboard
   - Visual indicators (✓ ⚡ ⚠️)
   - Recovery status, training load, weekly summary
   - Gear alerts, weather-adjusted pacing
   - Today's workout with timing

3. **Enhanced HTML Report** (`bin/view_morning_report.sh`)
   - Mobile-friendly HTML dashboard
   - Recovery gauge (0-100 with colors)
   - Interactive activity chart (Chart.js)
   - Training stress balance visualization
   - Metric cards, weather conditions
   - Opens via `termux-share`

### 10. Automation System (Termux)

**Location:** `bin/setup_cron.sh`

**Features:**
- Automated Garmin sync (every 6 hours)
- Daily morning reports (9:00 AM)
- Sync with notifications (`bin/sync_with_notification.sh`)
- Logs to `data/sync_log.txt` and `data/morning_report.log`

**Cron Setup:**
```bash
# Option A: Every 6 hours + morning report (recommended)
5 */6 * * * cd $HOME/running-coach && bash bin/sync_with_notification.sh
0 9 * * * cd $HOME/running-coach && bash bin/morning_report.sh
```

## Data Persistence

### Local Storage

All data is stored locally in the `data/` directory:

```
data/
├── athlete/           # Athlete context files (version controlled)
├── health/            # Health data cache (gitignored)
├── library/           # Workout library (version controlled)
├── plans/             # Training plans and workouts (version controlled)
├── calendar/          # Calendar import/export files (gitignored)
└── frameworks/        # Training framework templates (version controlled)
```

### Git Integration

**Version Controlled:**
- Athlete context files (`data/athlete/*.md`)
- Training plans (`data/plans/*.md`, `data/plans/planned_workouts.json`)
- Workout library (`data/library/workout_library.json`)
- System configuration (`config/*.example`)

**Gitignored:**
- Health data cache (`data/health/health_data_cache.json`)
- Calendar sources with URLs (`config/calendar_sources.json`)
- Sync logs (`data/*.log`, `data/*.txt`)

### Cache Management

**Health Data Cache:**
- Atomic updates (write to temp, then rename)
- Safe for concurrent access
- De-duplication by timestamp
- Sorted newest-first
- Tracks `last_updated` and `last_sync_date`

**Token Cache:**
- Location: `~/.garminconnect/`
- Contains OAuth tokens (valid ~1 year)
- Not in repository (user-specific)

## Security & Authentication

### Garmin Connect Authentication

**Option 1: Password Authentication**
```bash
export GARMIN_EMAIL=your@email.com
export GARMIN_PASSWORD=yourpassword
```

**Option 2: Token-Based Authentication (Recommended for Bots)**
- Generate tokens on machine with browser: `python3 bin/generate_garmin_tokens.py`
- Transfer tokens to `~/.garminconnect/` on target device
- More reliable in automated/headless environments
- See [GARMIN_TOKEN_AUTH.md](GARMIN_TOKEN_AUTH.md) for details

### Best Practices

1. **Environment Variables** - Never hardcode credentials
2. **Token Security** - Restrict permissions on `~/.garminconnect/`
3. **Gitignore** - Keep sensitive data out of version control
4. **Local-Only** - No external API endpoints, no cloud storage

## Performance Considerations

### Sync Optimization

**Incremental Sync:**
- Default behavior: only fetch data since `last_sync_date`
- Full sync with `--days N` for initial setup or gaps
- De-duplication ensures no duplicate entries

**Sync Frequency:**
- Manual: Run `bash bin/sync_garmin_data.sh` as needed
- Automated (Termux): Every 6 hours via cron
- Morning reports: 9:00 AM daily

### Cache Size

Typical cache sizes:
- 30 days: ~500KB
- 90 days: ~1.5MB
- 365 days: ~6MB

No performance degradation with large caches (JSON reading is fast).

### Response Times

**Health Data Sync:**
- Authentication: 1-2 seconds (cached tokens)
- Data fetch: 2-5 seconds (30 days)
- Cache write: <1 second

**VDOT Calculator:**
- Instant (<0.1 seconds)

**Weather Data:**
- API call: 0.5-1 second
- Location access (Termux): 1-2 seconds

## Extensibility

### Adding New Coaching Agent

1. Create `.claude/agents/new-agent.md`:
```markdown
# New Agent System Prompt

Agent instructions here...
```

2. Update `CLAUDE.md` with agent description
3. Update README.md documentation section
4. Test agent in Claude Code

### Adding New Data Source

1. Create sync script in `src/`:
```python
# src/new_data_source.py
def fetch_data():
    # Fetch from external API
    return data

def update_cache(data):
    # Merge with health_data_cache.json
    pass
```

2. Add to `bin/sync_garmin_data.sh` or create new wrapper
3. Update `HEALTH_DATA_SYSTEM.md` documentation
4. Update agent guides with new data usage

### Adding New Workout Template

1. Use workout library CLI:
```bash
bash bin/workout_library.sh import my_workout.json
```

2. Or directly edit `data/library/workout_library.json`
3. Follow schema in `data/library/workout_library_schema.md`

## Troubleshooting

See [QUICKSTART.md](QUICKSTART.md#troubleshooting) for comprehensive troubleshooting guide.

**Common Issues:**
- Authentication failures → Clear token cache, re-authenticate
- No data syncing → Check Garmin API status, verify credentials
- Duplicate entries → System auto-deduplicates, safe to ignore
- Missing calendar imports → Verify ICS URL, check config file

## Future Enhancements

### Planned Features

1. **Automated Plan Generation** - Multi-week training plans from race goals
2. **Contextual Recovery Recommendations** - Auto-adjust workouts based on recovery metrics
3. **Workout Adaptation Engine** - Real-time workout modifications
4. **Race Strategy Planning** - Race-day pacing and fueling strategies

### Integration Roadmap

1. **Strava Sync** - Two-way activity sync
2. **TrainingPeaks Integration** - Structured workout import/export
3. **Zwift Integration** - Indoor training workouts
4. **Additional Wearables** - Polar, Wahoo, Coros support

### Platform Expansion

1. **Native Mobile Apps** - iOS and Android applications
2. **Offline Mode** - Cached plans and offline logging
3. **Watch App Integration** - Garmin Connect IQ, Apple Watch
4. **Push Notifications** - Workout reminders, recovery alerts

## Development Guidelines

See [CLAUDE.md](../CLAUDE.md) for detailed development guidance including:
- Adding new features
- Documentation standards
- Git commit guidelines
- Agent update procedures

## Related Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Setup and installation guide
- **[HEALTH_DATA_SYSTEM.md](HEALTH_DATA_SYSTEM.md)** - Health data technical reference
- **[AGENT_HEALTH_DATA_GUIDE.md](AGENT_HEALTH_DATA_GUIDE.md)** - Agent health data usage
- **[AGENT_WORKOUT_LIBRARY_GUIDE.md](AGENT_WORKOUT_LIBRARY_GUIDE.md)** - Workout library integration
- **[AGENT_PLANNED_WORKOUTS_GUIDE.md](AGENT_PLANNED_WORKOUTS_GUIDE.md)** - Planned workouts management
- **[COMMUNICATION_PREFERENCES_GUIDE.md](COMMUNICATION_PREFERENCES_GUIDE.md)** - Response detail levels
- **[GARMIN_TOKEN_AUTH.md](GARMIN_TOKEN_AUTH.md)** - Advanced authentication
