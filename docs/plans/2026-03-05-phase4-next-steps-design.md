# Phase 4 Next Steps Design

**Date:** 2026-03-05
**Status:** Approved
**Context:** System is in a 4-week validation window while Saturday auto-plans prove themselves before cutting FinalSurge. These two features run in parallel during that window.

---

## Feature A: Athlete Pattern Analysis

**Goal:** Mine 15 months of Garmin data to discover personal training patterns and feed them into the Brain's context packet so plan generation starts from observed reality, not generic VDOT tables.

**Existing design doc:** `docs/plans/2026-03-01-athlete-pattern-analysis.md` — implement as written, no changes.

### Architecture

- `src/athlete_pattern_analyzer.py` — mines health cache, computes 5 patterns, writes `data/athlete/learned_patterns.md`
- `memory/retrieval.py` — new `_load_athlete_patterns()` reads that file into the context packet under key `athlete_patterns`
- `brain/planner.py` — updated prompt uses personal patterns instead of generic VDOT defaults; gracefully degrades to generic if file missing
- `agent/runner.py` — runs analysis daily at 4 AM (reads cache only, no network I/O)
- `cli/coach.py` — `analyze-patterns` command for on-demand refresh

### The 5 Patterns

1. **HRV Calibration** — athlete's personal median/IQR/range and Garmin BALANCED floor; replaces generic HRV thresholds
2. **Aerobic Efficiency** — pace-at-HR in 5 bpm buckets; fitness trend (early vs late thirds of easy run history)
3. **Quality Session Predictors** — HRV/sleep/body battery medians on good vs poor quality days; combined predictor %
4. **Recovery Signature** — median days for HRV to return to 97% of baseline after quality sessions
5. **Volume Tolerance** — sustainable weekly mileage threshold where readiness begins to decline

### Known Caveat

Quality predictor shows HRV lower on good days (65ms) vs poor days (70.5ms) — reversed from expected. Two possible explanations: classification artifact (pace ≤ median ≠ "good session") or real behavior (athlete pushes hard regardless of HRV). Brain prompt notes this signal as low-confidence until validated by future check-in data. Other 4 patterns used at full weight.

### Sequencing

Implement immediately (this week). Patterns accumulate during the 4-week FinalSurge validation window. Brain will have refined personal data before FinalSurge is cut.

---

## Feature B: FinalSurge Cutover

**Goal:** System prompts Neil after 4 successful Saturday auto-plans. Neil reviews a readiness report, can delay if needed, and explicitly confirms before FinalSurge is disabled. No automatic cutover.

### What "cutting FinalSurge" means

Flip `enabled: false` on all `"type": "training"` entries in `config/calendar_sources.json`. No account changes, no data deletion. Internal plan becomes authoritative.

### Components

**1. SQLite counter**
- New state key: `saturday_plan_success_count`
- Incremented by `saturday_plan_task` (in `discord_bot.py`) after each successful plan gen + Garmin export
- Existing task; adds one line

**2. Heartbeat hook — `hooks/on_cutover_ready.py`**
- Checks `saturday_plan_success_count >= threshold` (starts at 4)
- Guards against re-triggering: skips if `pending_cutover_prompt` already set
- Writes prompt payload to SQLite state on detection
- Wired into `agent/runner.py` `run_cycle()` like existing hooks

**3. Bot delivery — `_post_pending_cutover_prompt()`**
- Added to `discord_bot.py`, called from `on_ready` + `sync_digest_task` (same pattern as existing pending_ handlers)
- Posts to #coach:
  > "4 weeks of auto-generated plans complete. Ready to review before cutting FinalSurge? Reply **delay** to wait another week, or run `/coach_cutover confirm` when ready."

**4. Delay mechanism**
- Bot watches #coach for "delay" reply to the prompt message
- On "delay": increments `cutover_delay_weeks` in SQLite, raises threshold by 1 (counter must reach 5, then 6, etc.)
- No expiry — system waits indefinitely for Neil's go-ahead

**5. `/coach_cutover confirm` command**
- Generates readiness report inline in #coach:
  - Last 4 Saturday plans: days scheduled, quality session type, target weekly mileage
  - RPE summary: average by workout type, any elevated-effort flags from check-ins
  - Any pending VDOT drift warnings
- After report: flips `enabled: false` on FinalSurge entries in `config/calendar_sources.json`
- Confirms in Discord: "FinalSurge disabled. Internal plan is now authoritative."

### Data Flow

```
saturday_plan_task (success)
  → increment saturday_plan_success_count in SQLite

heartbeat agent (every 15 min)
  → on_cutover_ready.py checks count >= threshold
  → writes pending_cutover_prompt to SQLite

discord bot (on_ready / sync_digest_task)
  → _post_pending_cutover_prompt() posts to #coach

Neil replies "delay"
  → bot raises threshold by 1, clears prompt

Neil runs /coach_cutover confirm
  → readiness report generated
  → config/calendar_sources.json updated
  → done
```

---

## Implementation Order

1. Athlete Pattern Analysis (implement now, runs during validation window)
2. FinalSurge Cutover plumbing (can build now, first trigger ~4 Saturdays out)
