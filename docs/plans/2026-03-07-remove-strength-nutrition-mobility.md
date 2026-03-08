# Remove Strength, Nutrition, and Mobility Coaching Features

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Delete all strength, nutrition, and mobility coaching features while preserving passive activity-type tracking in garmin_sync.

**Architecture:** Pure deletion and trimming — no new logic. Remove 7 files entirely, make targeted edits to 8 files. All changes are removal only. Passive Garmin data (STRENGTH activity type stored in cache) is untouched.

**Tech Stack:** Python, Discord.py, Pydantic v2, SQLite

---

### Task 1: Delete agent files (3 files)

**Files:**
- Delete: `.claude/agents/runner-strength-coach.md`
- Delete: `.claude/agents/endurance-nutrition-coach.md`
- Delete: `.claude/agents/mobility-coach-runner.md`

**Step 1: Delete the three agent markdown files**

```bash
rm /home/coach/running-coach/.claude/agents/runner-strength-coach.md
rm /home/coach/running-coach/.claude/agents/endurance-nutrition-coach.md
rm /home/coach/running-coach/.claude/agents/mobility-coach-runner.md
```

**Step 2: Verify**

```bash
ls /home/coach/running-coach/.claude/agents/
```
Expected: only `onboarding-wizard.md` and `vdot-running-coach.md` remain.

**Step 3: Commit**

```bash
git add -A
git commit -m "remove: delete strength, nutrition, mobility agent files"
```

---

### Task 2: Delete generator source files (4 files)

**Files:**
- Delete: `src/ai_strength_generator.py`
- Delete: `src/streprogen_program_generator.py`
- Delete: `src/streprogen_completion_tracker.py`
- Delete: `src/supplemental_workout_generator.py`

**Step 1: Delete the four source files**

```bash
rm /home/coach/running-coach/src/ai_strength_generator.py
rm /home/coach/running-coach/src/streprogen_program_generator.py
rm /home/coach/running-coach/src/streprogen_completion_tracker.py
rm /home/coach/running-coach/src/supplemental_workout_generator.py
```

**Step 2: Verify test suite still imports cleanly**

```bash
cd /home/coach/running-coach && python3 -m pytest tests/ -q --tb=short 2>&1 | head -40
```
Expected: no ImportError for the deleted files. Note baseline pass count.

**Step 3: Commit**

```bash
git add -A
git commit -m "remove: delete strength/streprogen generator source files"
```

---

### Task 3: Edit `src/discord_bot.py` — remove 3 slash commands + 2 display blocks

**File:** `src/discord_bot.py`

**Step 1: Remove the `/strength`, `/mobility`, `/nutrition` slash command handlers**

Delete lines 917–941 (the three `@bot.tree.command` blocks for strength, mobility, nutrition). The section starts at:
```python
@bot.tree.command(name="strength", description="[Deprecated] Strength coaching moved to agent system")
```
and ends after the closing of `nutrition_coach_command`. The next line after is a blank line then `# ============== CLI-Routed Coach Commands ==============`.

**Step 2: Remove strength bullet from sync digest (lines ~366–378)**

In the sync digest block, remove these lines:
```python
strength = [a for a in new_activities if a.get('activity_type') == 'STRENGTH']
```
and:
```python
                        if strength:
                            new_data_details.append(f"💪 Strength: {len(strength)} sessions")
```

**Step 3: Remove the strength/mobility section from the `/workout` command display (lines ~655–660)**

Change this block:
```python
            if "ics_calendar" in source or domain == "running":
                emoji = "🏃"
                color = discord.Color.green()
            elif "strength" in domain or "strength" in w.get("name", "").lower():
                emoji = "💪"
                color = discord.Color.orange()
            elif "mobility" in domain or "mobility" in w.get("name", "").lower():
                emoji = "🧘"
                color = discord.Color.purple()
            else:
                emoji = "📋"
                color = discord.Color.blue()
```
To:
```python
            if "ics_calendar" in source or domain == "running":
                emoji = "🏃"
                color = discord.Color.green()
            else:
                emoji = "📋"
                color = discord.Color.blue()
```

**Step 4: Remove `supplemental_workout_details` block (lines ~476–478)**

Remove:
```python
        if supplemental_workout_details:
            content_lines.append("\n💪 Strength workouts scheduled:")
            content_lines.extend(supplemental_workout_details)
```

**Step 5: Run tests**

```bash
cd /home/coach/running-coach && python3 -m pytest tests/ -q --tb=short 2>&1 | head -40
```
Expected: same pass count as Task 2.

**Step 6: Commit**

```bash
git add src/discord_bot.py
git commit -m "remove: strip strength/mobility/nutrition from discord_bot"
```

---

### Task 4: Edit `src/morning_report.py` — remove strength session tracking

**File:** `src/morning_report.py`

**Step 1: Simplify `get_recent_activities()`**

The function currently builds a `strength_sessions` list (lines ~448–488) and includes it in the return dict. Remove all strength-specific code. The simplified function body should:
- Keep `activities`, `cutoff`, `today`, `recent`, `running` locals
- Remove `strength = ...` and the entire `strength_sessions` list-building block
- Remove `'strength_sessions': strength_sessions` from the return dict
- Keep `'total_activities'`, `'running_count'`, `'running_miles'`, `'last_run'`

**Step 2: Remove strength context from `build_ai_prompt()`**

Find the block around lines 623–637 that adds recent strength sessions to the prompt:
```python
    # Include recent strength sessions if available
    if activities.get('strength_sessions'):
        for s in activities['strength_sessions'][:2]:  # Last 2 strength sessions
            activity_text += f"\nStrength ({s['date']}): {s['name']}"
            ...
```
Delete the entire block.

Also remove the comment at ~line 580:
```python
                    # For strength/mobility, extract key focus areas
```
and any associated strength/mobility handling in that section.

**Step 3: Run tests**

```bash
cd /home/coach/running-coach && python3 -m pytest tests/ -q --tb=short 2>&1 | head -40
```

**Step 4: Commit**

```bash
git add src/morning_report.py
git commit -m "remove: strip strength session tracking from morning_report"
```

---

### Task 5: Edit `brain/schemas.py` — remove "strength" from WorkoutTypeT

**File:** `brain/schemas.py:24`

**Step 1: Edit the type literal**

Change line 24 from:
```python
WorkoutTypeT = Literal["easy", "tempo", "interval", "long", "strength", "rest", "cross"]
```
To:
```python
WorkoutTypeT = Literal["easy", "tempo", "interval", "long", "rest", "cross"]
```

**Step 2: Run tests**

```bash
cd /home/coach/running-coach && python3 -m pytest tests/ -q --tb=short 2>&1 | head -40
```
Watch for any test that constructs a `PlanDay` with `workout_type="strength"` — those fixtures will need updating too.

**Step 3: Commit**

```bash
git add brain/schemas.py
git commit -m "remove: drop 'strength' from WorkoutTypeT literal"
```

---

### Task 6: Edit `brain/planner.py` — remove "strength" from prompt examples

**File:** `brain/planner.py`

**Step 1: Remove "strength" from workout_type examples in system prompts**

Find all occurrences of `"strength"` in the prompt template strings (around lines 186 and 211) where workout types are listed as examples:
```
"workout_type": "easy"|"tempo"|"interval"|"long"|"strength"|"rest"|"cross",
```
Change to:
```
"workout_type": "easy"|"tempo"|"interval"|"long"|"rest"|"cross",
```

**Step 2: Run tests**

```bash
cd /home/coach/running-coach && python3 -m pytest tests/ -q --tb=short 2>&1 | head -40
```

**Step 3: Commit**

```bash
git add brain/planner.py
git commit -m "remove: drop 'strength' from planner prompt examples"
```

---

### Task 7: Edit `skills/publish_to_garmin.py` — clean up strength/mobility references

**File:** `skills/publish_to_garmin.py`

**Step 1: Remove "strength" and "mobility" from `NON_RUNNING_TYPES`**

Change (lines 38–46):
```python
NON_RUNNING_TYPES = {
    "rest",
    "strength",
    "mobility",
    "cross",
    "cross_training",
    "off",
    "none",
}
```
To:
```python
NON_RUNNING_TYPES = {
    "rest",
    "cross",
    "cross_training",
    "off",
    "none",
}
```

**Step 2: Clean up `_load_generated_log()` default dicts**

The function returns dicts with `"strength"` and `"mobility"` keys as leftover sections. Change all four occurrences of:
```python
return {"running": {}, "strength": {}, "mobility": {}, "week_snapshots": {}}
```
To:
```python
return {"running": {}, "week_snapshots": {}}
```

Also remove the `data.setdefault("strength", {})` and `data.setdefault("mobility", {})` lines (~65–66).

**Step 3: Run tests**

```bash
cd /home/coach/running-coach && python3 -m pytest tests/ -q --tb=short 2>&1 | head -40
```

**Step 4: Commit**

```bash
git add skills/publish_to_garmin.py
git commit -m "remove: drop strength/mobility from publish_to_garmin"
```

---

### Task 8: Edit `hooks/on_activity_completed.py` — running-only checkins

**File:** `hooks/on_activity_completed.py`

**Step 1: Remove `_STRENGTH_TYPES` and update `_CHECKIN_TYPES`**

Change lines 32–34:
```python
_RUNNING_TYPES  = {"running", "trail_running", "treadmill_running"}
_STRENGTH_TYPES = {"strength_training", "cardio"}
_CHECKIN_TYPES  = _RUNNING_TYPES | _STRENGTH_TYPES
```
To:
```python
_RUNNING_TYPES = {"running", "trail_running", "treadmill_running"}
_CHECKIN_TYPES = _RUNNING_TYPES
```

Also update the module docstring lines 2–8 to remove mentions of "strength":
- Line 2: `Hook: on_activity_completed — detects new running activities and queues`
- Line 8: `1. Query activities table for running activities from last 48 hours.`

**Step 2: Run tests**

```bash
cd /home/coach/running-coach && python3 -m pytest tests/ -q --tb=short 2>&1 | head -40
```

**Step 3: Commit**

```bash
git add hooks/on_activity_completed.py
git commit -m "remove: restrict activity checkins to running only"
```

---

### Task 9: Edit `cli/coach.py` — remove "strength" from type map

**File:** `cli/coach.py`

**Step 1: Remove `"strength"` entry from the workout type label/color dict**

Find the dict around line 392:
```python
    "strength": ("🟠", "Quality"),
```
Delete that line.

**Step 2: Run tests**

```bash
cd /home/coach/running-coach && python3 -m pytest tests/ -q --tb=short 2>&1 | head -40
```

**Step 3: Commit**

```bash
git add cli/coach.py
git commit -m "remove: drop 'strength' from cli workout type map"
```

---

### Task 10: Edit `src/garmin_sync.py` — remove strength fetch function and dead comments

**File:** `src/garmin_sync.py`

**Step 1: Delete `_fetch_strength_workout_details()` (lines ~377–420)**

Delete the entire function from its docstring to the last `return` statement.

**Step 2: Remove the call site (lines ~488–491)**

Delete:
```python
            # For strength activities, try to get workout details
            workout_description = None
            if activity_type == 'STRENGTH':
                workout_description = _fetch_strength_workout_details(client, str(activity_id), quiet)
```
Replace with just:
```python
            workout_description = None
```

**Step 3: Remove the large commented-out strength regeneration block (~lines 2056–2101)**

Delete the entire commented block starting with:
```python
            # DISABLED: Automatic strength workout regeneration after reschedules
```
through to the end of the commented section.

**Step 4: Run tests**

```bash
cd /home/coach/running-coach && python3 -m pytest tests/ -q --tb=short 2>&1 | head -40
```

**Step 5: Commit**

```bash
git add src/garmin_sync.py
git commit -m "remove: delete strength fetch fn and dead comments from garmin_sync"
```

---

### Task 11: Final verification

**Step 1: Run full test suite**

```bash
cd /home/coach/running-coach && python3 -m pytest tests/ -q --tb=short
```
Expected: same pass count as before Task 1 (no regressions).

**Step 2: Check for any remaining stray references**

```bash
cd /home/coach/running-coach && grep -r "strength\|nutrition\|mobility" \
  src/ brain/ hooks/ skills/ cli/ .claude/agents/ \
  --include="*.py" --include="*.md" -l
```
Expected: no Python files. Any remaining `.md` files should only be documentation (CLAUDE.md, docs/) — not agent or generator files.

**Step 3: Restart bot to pick up changes**

```bash
sudo systemctl restart running-coach-bot
sudo systemctl status running-coach-bot
```
Expected: `active (running)`.
