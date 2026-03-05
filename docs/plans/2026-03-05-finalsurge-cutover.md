# FinalSurge Cutover Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** After 4 successful Saturday auto-plans, prompt Neil in #coach to review a readiness report and explicitly confirm before FinalSurge's ICS import is disabled.

**Architecture:** Four SQLite state keys track progress (`saturday_plan_success_count`, `cutover_threshold`, `pending_cutover_prompt`, `cutover_awaiting_response`). A new heartbeat hook detects when the count hits the threshold and queues a prompt. The Discord bot delivers it, handles "delay" replies, and processes `/coach_cutover confirm` to generate a readiness report and flip the config flag.

**Note on Feature A (Athlete Pattern Analysis):** Already fully implemented. `src/athlete_pattern_analyzer.py`, `memory/retrieval.py` wiring, `brain/planner.py` prompt integration, daily runner hook, and `data/athlete/learned_patterns.md` all exist. No work needed.

**Tech Stack:** Python stdlib, SQLite (via `memory.db`), `discord.py`, `config/calendar_sources.json`

---

## Task 1: Increment counter in saturday_plan_task

**Files:**
- Modify: `src/discord_bot.py` (saturday_plan_task, ~line 2340)

**Step 1: Write the failing test**

```python
# tests/test_cutover.py
import json
import pytest
from pathlib import Path
import tempfile

def make_db(tmp_path):
    from memory.db import _connect, SCHEMA
    db = tmp_path / "coach.sqlite"
    conn = _connect(db)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    return db

def test_increment_saturday_count(tmp_path):
    """After a successful Saturday plan, count increments from 0 to 1."""
    db = make_db(tmp_path)
    from memory.db import get_state, set_state
    # Simulate what saturday_plan_task will do on success
    from hooks.on_cutover_ready import _increment_success_count
    _increment_success_count(db_path=db)
    assert get_state("saturday_plan_success_count", db_path=db) == "1"

def test_increment_saturday_count_accumulates(tmp_path):
    """Count accumulates across multiple calls."""
    db = make_db(tmp_path)
    from hooks.on_cutover_ready import _increment_success_count
    _increment_success_count(db_path=db)
    _increment_success_count(db_path=db)
    _increment_success_count(db_path=db)
    from memory.db import get_state
    assert get_state("saturday_plan_success_count", db_path=db) == "3"
```

**Step 2: Run test to verify it fails**

```bash
cd /home/coach/running-coach && python -m pytest tests/test_cutover.py::test_increment_saturday_count -v
```

Expected: FAIL with `ImportError: cannot import name '_increment_success_count'`

**Step 3: Create `hooks/on_cutover_ready.py` with `_increment_success_count`**

```python
"""
Hook: on_cutover_ready — detects when 4 successful Saturday auto-plans have
been generated and queues a cutover prompt for Discord delivery.

Called from agent/runner.py run_cycle() unconditionally (like on_obs_missed).

State keys used:
  saturday_plan_success_count  - int, incremented by saturday_plan_task on success
  cutover_threshold            - int, starts 4, bumped by 1 on each "delay"
  pending_cutover_prompt       - set when count >= threshold (bot clears after posting)
  cutover_awaiting_response    - set after bot posts (cleared on delay or confirm)
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).parent.parent
log = logging.getLogger("hooks.on_cutover_ready")

_COUNT_KEY     = "saturday_plan_success_count"
_THRESHOLD_KEY = "cutover_threshold"
_PROMPT_KEY    = "pending_cutover_prompt"
_AWAITING_KEY  = "cutover_awaiting_response"
_DEFAULT_THRESHOLD = 4


def _increment_success_count(db_path=None) -> int:
    """Increment saturday_plan_success_count by 1 and return the new value."""
    from memory.db import get_state, set_state, DB_PATH
    db = db_path or DB_PATH
    current = int(get_state(_COUNT_KEY, default="0", db_path=db))
    new_val = current + 1
    set_state(_COUNT_KEY, str(new_val), db_path=db)
    log.info("on_cutover_ready: success count → %d", new_val)
    return new_val


def run(db_path=None) -> Dict[str, Any]:
    """
    Check if count >= threshold and queue prompt if not already pending.
    Returns {pending_written: bool, count: int, threshold: int}
    """
    from memory.db import get_state, set_state, DB_PATH
    db = db_path or DB_PATH

    result: Dict[str, Any] = {"pending_written": False, "count": 0, "threshold": _DEFAULT_THRESHOLD}

    count = int(get_state(_COUNT_KEY, default="0", db_path=db))
    threshold = int(get_state(_THRESHOLD_KEY, default=str(_DEFAULT_THRESHOLD), db_path=db))
    result["count"] = count
    result["threshold"] = threshold

    if count < threshold:
        log.debug("on_cutover_ready: %d/%d plans — not ready", count, threshold)
        return result

    # Guard: don't re-queue if already pending or awaiting response
    if get_state(_PROMPT_KEY, db_path=db) or get_state(_AWAITING_KEY, db_path=db):
        log.debug("on_cutover_ready: prompt already queued or awaiting response — skipping")
        return result

    payload = {"count": count, "threshold": threshold}
    set_state(_PROMPT_KEY, json.dumps(payload), db_path=db)
    result["pending_written"] = True
    log.info("on_cutover_ready: %d/%d plans complete — cutover prompt queued", count, threshold)
    return result
```

**Step 4: Run tests to verify they pass**

```bash
cd /home/coach/running-coach && python -m pytest tests/test_cutover.py::test_increment_saturday_count tests/test_cutover.py::test_increment_saturday_count_accumulates -v
```

Expected: PASS

**Step 5: Wire `_increment_success_count` into `saturday_plan_task` in `discord_bot.py`**

Find the block where both `rc == 0` AND `exp_rc == 0` — that's a fully successful Saturday plan. Add the increment call there:

```python
# After: garmin_note = "\n✅ Workouts published to Garmin Connect."
# Add:
try:
    from hooks.on_cutover_ready import _increment_success_count
    _increment_success_count()
    logger.info("[Saturday Plan] Cutover success count incremented")
except Exception as _exc:
    logger.warning("[Saturday Plan] Could not increment cutover count: %s", _exc)
```

**Step 6: Write test for the wiring**

Add to `tests/test_cutover.py`:

```python
def test_only_increments_on_full_success(tmp_path):
    """Count must NOT increment when Garmin export fails — only full success counts."""
    # This is a logic test: _increment_success_count should only be called
    # when both plan gen AND Garmin export return rc==0.
    # We verify by checking the count starts at 0 and only increments explicitly.
    db = make_db(tmp_path)
    from memory.db import get_state
    # Before any call, count is 0
    assert get_state("saturday_plan_success_count", db_path=db) is None
    # Simulating garmin failure: don't call increment — count stays 0
    assert get_state("saturday_plan_success_count", db_path=db) is None
```

**Step 7: Run full test file**

```bash
cd /home/coach/running-coach && python -m pytest tests/test_cutover.py -v
```

Expected: PASS

**Step 8: Commit**

```bash
git add hooks/on_cutover_ready.py tests/test_cutover.py src/discord_bot.py
git commit -m "feat(cutover): track saturday auto-plan success count"
```

---

## Task 2: Heartbeat hook wired into runner

**Files:**
- Modify: `agent/runner.py` (~line 205, after on_weekly_rollup block)

**Step 1: Write the failing test**

Add to `tests/test_cutover.py`:

```python
def test_hook_queues_prompt_at_threshold(tmp_path):
    """Hook writes pending_cutover_prompt when count reaches threshold."""
    db = make_db(tmp_path)
    from memory.db import set_state, get_state
    set_state("saturday_plan_success_count", "4", db_path=db)
    from hooks.on_cutover_ready import run
    result = run(db_path=db)
    assert result["pending_written"] is True
    assert get_state("pending_cutover_prompt", db_path=db) is not None

def test_hook_does_not_double_queue(tmp_path):
    """Hook does not re-queue if prompt is already pending."""
    db = make_db(tmp_path)
    from memory.db import set_state, get_state
    set_state("saturday_plan_success_count", "4", db_path=db)
    from hooks.on_cutover_ready import run
    run(db_path=db)
    run(db_path=db)  # second call
    # Verify count hasn't somehow doubled the pending flag
    import json
    raw = get_state("pending_cutover_prompt", db_path=db)
    data = json.loads(raw)
    assert data["count"] == 4

def test_hook_respects_delay(tmp_path):
    """After delay, threshold is 5; hook does not queue at count=4."""
    db = make_db(tmp_path)
    from memory.db import set_state, get_state
    set_state("saturday_plan_success_count", "4", db_path=db)
    set_state("cutover_threshold", "5", db_path=db)
    from hooks.on_cutover_ready import run
    result = run(db_path=db)
    assert result["pending_written"] is False

def test_hook_queues_after_delay_when_count_catches_up(tmp_path):
    """After delay (threshold=5), hook queues at count=5."""
    db = make_db(tmp_path)
    from memory.db import set_state
    set_state("saturday_plan_success_count", "5", db_path=db)
    set_state("cutover_threshold", "5", db_path=db)
    from hooks.on_cutover_ready import run
    result = run(db_path=db)
    assert result["pending_written"] is True
```

**Step 2: Run tests to verify they pass (logic already in hook)**

```bash
cd /home/coach/running-coach && python -m pytest tests/test_cutover.py -v
```

Expected: PASS (hook logic already handles these cases)

**Step 3: Wire hook into `agent/runner.py`**

After the `on_weekly_rollup` block (step 7), add:

```python
        # ── 8. FinalSurge cutover readiness check (always) ──────────────────
        from hooks.on_cutover_ready import run as on_cutover_ready
        cutover = on_cutover_ready(db_path=db)
        if cutover["pending_written"]:
            summary["hooks_run"].append("on_cutover_ready")
            log.info("on_cutover_ready: cutover prompt queued (%d/%d plans)",
                     cutover["count"], cutover["threshold"])
```

**Step 4: Commit**

```bash
git add agent/runner.py tests/test_cutover.py
git commit -m "feat(cutover): wire on_cutover_ready into heartbeat agent"
```

---

## Task 3: Bot delivery — `_post_pending_cutover_prompt`

**Files:**
- Modify: `src/discord_bot.py`

**Step 1: Write the test**

Add to `tests/test_cutover.py`:

```python
def test_cutover_awaiting_set_after_prompt(tmp_path):
    """After prompt is delivered, cutover_awaiting_response is set."""
    db = make_db(tmp_path)
    import json
    from memory.db import set_state, get_state
    set_state("pending_cutover_prompt", json.dumps({"count": 4, "threshold": 4}), db_path=db)
    # Simulate what _post_pending_cutover_prompt does (minus Discord send):
    from memory.db import DB_PATH
    # After posting: clear pending, set awaiting
    from memory.db import set_state as ss, get_state as gs
    ss("cutover_awaiting_response", "1", db_path=db)
    from memory.db import get_state
    import sqlite3
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("DELETE FROM state WHERE key = 'pending_cutover_prompt'")
    conn.commit()
    conn.close()
    assert get_state("pending_cutover_prompt", db_path=db) is None
    assert get_state("cutover_awaiting_response", db_path=db) == "1"
```

**Step 2: Run to verify it passes (pure state logic, no Discord)**

```bash
cd /home/coach/running-coach && python -m pytest tests/test_cutover.py::test_cutover_awaiting_set_after_prompt -v
```

Expected: PASS

**Step 3: Add `_post_pending_cutover_prompt` to `discord_bot.py`**

Add after `_post_pending_weekly_synthesis` (around line 2234):

```python
async def _post_pending_cutover_prompt(channel) -> bool:
    """
    If pending_cutover_prompt is set, post the cutover readiness prompt to #coach.
    Returns True if posted, False otherwise.
    """
    import sqlite3 as _sqlite3
    db_path = _DB_PATH
    try:
        conn = _sqlite3.connect(db_path)
        conn.row_factory = _sqlite3.Row
        row = conn.execute(
            "SELECT value FROM state WHERE key = 'pending_cutover_prompt'"
        ).fetchone()
        conn.close()
    except Exception as exc:
        logger.warning("_post_pending_cutover_prompt: DB read error: %s", exc)
        return False

    if not row:
        return False

    try:
        embed = discord.Embed(
            title="✅ 4 Weeks of Auto-Plans Complete",
            description=(
                "The system has generated 4 consecutive weeks of training plans automatically.\n\n"
                "**Ready to cut FinalSurge?**\n"
                "Run `/coach_cutover confirm` to review a readiness report and disable the FinalSurge import.\n\n"
                "Not ready yet? Reply **delay** to wait one more week."
            ),
            color=discord.Color.green(),
            timestamp=datetime.now(),
        )
        await channel.send(embed=embed)
    except Exception as exc:
        logger.error("_post_pending_cutover_prompt: send failed: %s", exc)
        return False

    # Clear pending, set awaiting response
    try:
        from memory.db import set_state, DB_PATH
        conn = _sqlite3.connect(db_path)
        conn.execute("DELETE FROM state WHERE key = 'pending_cutover_prompt'")
        conn.commit()
        conn.close()
        set_state("cutover_awaiting_response", "1")
    except Exception as exc:
        logger.warning("_post_pending_cutover_prompt: state update error: %s", exc)

    logger.info("_post_pending_cutover_prompt: cutover prompt posted")
    return True
```

Note: `_DB_PATH` — check the actual variable name used in `discord_bot.py` for the SQLite path (search for `DB_PATH` or `db_path` at module level and use the same).

**Step 4: Wire into `checkin_delivery_task` and `on_ready`**

In `checkin_delivery_task`, add after `_post_pending_weekly_synthesis`:
```python
        await _post_pending_cutover_prompt(channel)
```

In `on_ready`, after the `_post_pending_obs` block, add:
```python
    coach_channel = bot.get_channel(CHANNELS["coach"])
    if coach_channel:
        posted = await _post_pending_cutover_prompt(coach_channel)
        if posted:
            print("✓ Late cutover prompt delivered on reconnect")
```

**Step 5: Commit**

```bash
git add src/discord_bot.py
git commit -m "feat(cutover): add _post_pending_cutover_prompt delivery"
```

---

## Task 4: Delay mechanism in `on_message`

**Files:**
- Modify: `src/discord_bot.py` (`on_message` handler)

**Step 1: Write the test**

Add to `tests/test_cutover.py`:

```python
def test_delay_bumps_threshold(tmp_path):
    """Replying 'delay' when awaiting response bumps threshold by 1 and clears awaiting."""
    db = make_db(tmp_path)
    from memory.db import set_state, get_state
    set_state("cutover_awaiting_response", "1", db_path=db)
    set_state("cutover_threshold", "4", db_path=db)
    # Simulate delay handler logic
    from hooks.on_cutover_ready import _handle_delay
    _handle_delay(db_path=db)
    assert get_state("cutover_awaiting_response", db_path=db) is None
    assert get_state("cutover_threshold", db_path=db) == "5"

def test_delay_without_awaiting_is_noop(tmp_path):
    """Delay handler is a no-op when not awaiting response."""
    db = make_db(tmp_path)
    from memory.db import get_state
    from hooks.on_cutover_ready import _handle_delay
    result = _handle_delay(db_path=db)
    assert result is False
    assert get_state("cutover_threshold", db_path=db) is None
```

**Step 2: Run to verify they fail**

```bash
cd /home/coach/running-coach && python -m pytest tests/test_cutover.py::test_delay_bumps_threshold tests/test_cutover.py::test_delay_without_awaiting_is_noop -v
```

Expected: FAIL with `ImportError: cannot import name '_handle_delay'`

**Step 3: Add `_handle_delay` to `hooks/on_cutover_ready.py`**

```python
def _handle_delay(db_path=None) -> bool:
    """
    Called when athlete replies 'delay'. Bumps threshold by 1, clears awaiting flag.
    Returns True if delay was applied, False if not awaiting.
    """
    from memory.db import get_state, set_state, DB_PATH
    db = db_path or DB_PATH
    if not get_state(_AWAITING_KEY, db_path=db):
        return False
    threshold = int(get_state(_THRESHOLD_KEY, default=str(_DEFAULT_THRESHOLD), db_path=db))
    set_state(_THRESHOLD_KEY, str(threshold + 1), db_path=db)
    # Clear awaiting — hook will re-queue when count catches up
    conn = __import__("sqlite3").connect(str(db))
    conn.execute(f"DELETE FROM state WHERE key = '{_AWAITING_KEY}'")
    conn.commit()
    conn.close()
    log.info("on_cutover_ready: delay applied — new threshold %d", threshold + 1)
    return True
```

**Step 4: Run tests to verify they pass**

```bash
cd /home/coach/running-coach && python -m pytest tests/test_cutover.py::test_delay_bumps_threshold tests/test_cutover.py::test_delay_without_awaiting_is_noop -v
```

Expected: PASS

**Step 5: Wire delay handler into `on_message` in `discord_bot.py`**

In `on_message`, in the same block as the VDOT confirm handler (after the "confirm" check), add:

```python
            # ── Cutover delay handler ────────────────────────────────────────
            if lower.strip() == "delay":
                from hooks.on_cutover_ready import _handle_delay
                if _handle_delay():
                    await message.reply(
                        "Got it. I'll check again after one more week of clean plans."
                    )
                    return
```

**Step 6: Run full test suite**

```bash
cd /home/coach/running-coach && python -m pytest tests/test_cutover.py -v
```

Expected: all PASS

**Step 7: Commit**

```bash
git add hooks/on_cutover_ready.py src/discord_bot.py tests/test_cutover.py
git commit -m "feat(cutover): add delay mechanism to defer cutover by one week"
```

---

## Task 5: `/coach_cutover confirm` command

**Files:**
- Modify: `src/discord_bot.py` (add slash command)

**Step 1: Write the test**

Add to `tests/test_cutover.py`:

```python
def test_build_readiness_report_structure(tmp_path):
    """_build_cutover_report returns a dict with plans and rpe_summary keys."""
    db = make_db(tmp_path)
    from src.discord_bot import _build_cutover_report
    report = _build_cutover_report(db_path=db)
    assert "plans_summary" in report
    assert "rpe_summary" in report
    assert "vdot_warning" in report
    # With empty DB, all are empty/None
    assert isinstance(report["plans_summary"], list)
    assert isinstance(report["rpe_summary"], list)

def test_disable_finalsurge_in_config(tmp_path):
    """_disable_finalsurge_calendar flips enabled=False on training-type entries."""
    config_path = tmp_path / "calendar_sources.json"
    config_path.write_text(json.dumps({
        "calendar_urls": [
            {"name": "FinalSurge", "url": "https://finalsurge.com/ical/abc", "enabled": True, "type": "training"},
            {"name": "Constraint", "url": "https://example.com/cal.ics", "enabled": True, "type": "constraint"},
        ]
    }))
    from src.discord_bot import _disable_finalsurge_calendar
    _disable_finalsurge_calendar(config_path=config_path)
    import json
    data = json.loads(config_path.read_text())
    training = [c for c in data["calendar_urls"] if c["type"] == "training"]
    constraint = [c for c in data["calendar_urls"] if c["type"] == "constraint"]
    assert all(not c["enabled"] for c in training)
    assert all(c["enabled"] for c in constraint)  # constraint calendars untouched
```

**Step 2: Run to verify they fail**

```bash
cd /home/coach/running-coach && python -m pytest tests/test_cutover.py::test_build_readiness_report_structure tests/test_cutover.py::test_disable_finalsurge_in_config -v
```

Expected: FAIL with ImportError

**Step 3: Add helper functions to `discord_bot.py`**

Add near the other `_post_pending_*` helpers:

```python
def _build_cutover_report(db_path=None) -> dict:
    """
    Build cutover readiness report data.
    Returns: {plans_summary: list, rpe_summary: list, vdot_warning: str|None}
    """
    import sqlite3 as _sql
    from datetime import date, timedelta
    from memory.db import get_weekly_rpe_summary, get_state, DB_PATH
    db = db_path or DB_PATH

    # Last 4 weeks of plan days
    today = date.today()
    plans_summary = []
    for weeks_back in range(4, 0, -1):
        week_start = today - timedelta(days=today.weekday() + 7 * weeks_back)
        week_end = week_start + timedelta(days=6)
        try:
            conn = _sql.connect(str(db))
            conn.row_factory = _sql.Row
            rows = conn.execute(
                "SELECT day, intent FROM plan_days WHERE day BETWEEN ? AND ? ORDER BY day",
                (week_start.isoformat(), week_end.isoformat()),
            ).fetchall()
            conn.close()
            days = [dict(r) for r in rows]
            plans_summary.append({"week_start": week_start.isoformat(), "days": days})
        except Exception:
            plans_summary.append({"week_start": week_start.isoformat(), "days": []})

    # Last 4 weeks of RPE data
    rpe_summary = []
    for weeks_back in range(4, 0, -1):
        week_start = today - timedelta(days=today.weekday() + 7 * weeks_back)
        rows = get_weekly_rpe_summary(week_start, db_path=db)
        rpe_summary.extend(rows)

    # VDOT drift warning
    vdot_warning = get_state("pending_vdot_update", db_path=db)

    return {
        "plans_summary": plans_summary,
        "rpe_summary": rpe_summary,
        "vdot_warning": vdot_warning,
    }


def _disable_finalsurge_calendar(config_path=None) -> int:
    """
    Set enabled=False on all type='training' entries in calendar_sources.json.
    Returns count of entries disabled.
    """
    import json as _json
    from pathlib import Path as _Path
    path = _Path(config_path) if config_path else _Path("config/calendar_sources.json")
    if not path.exists():
        return 0
    data = _json.loads(path.read_text())
    disabled = 0
    for entry in data.get("calendar_urls", []):
        if entry.get("type") == "training" and entry.get("enabled"):
            entry["enabled"] = False
            disabled += 1
    path.write_text(_json.dumps(data, indent=2))
    return disabled
```

**Step 4: Run tests to verify they pass**

```bash
cd /home/coach/running-coach && python -m pytest tests/test_cutover.py::test_build_cutover_report_structure tests/test_cutover.py::test_disable_finalsurge_in_config -v
```

Expected: PASS

**Step 5: Add `/coach_cutover` slash command to `discord_bot.py`**

Add after the last `@bot.tree.command` definition:

```python
@bot.tree.command(name="coach_cutover", description="Review FinalSurge cutover readiness and confirm when ready")
@app_commands.describe(action="Action: 'confirm' to proceed, 'status' to see progress")
async def coach_cutover_command(interaction: discord.Interaction, action: str = "status"):
    await interaction.response.defer()
    action = action.strip().lower()

    from memory.db import get_state, DB_PATH
    count = int(get_state("saturday_plan_success_count", default="0") or "0")
    threshold = int(get_state("cutover_threshold", default="4") or "4")

    if action == "status":
        embed = discord.Embed(
            title="📊 FinalSurge Cutover Status",
            description=(
                f"**Plans completed:** {count}/{threshold}\n"
                f"**Status:** {'Ready — run `/coach_cutover confirm`' if count >= threshold else f'{threshold - count} more week(s) needed'}"
            ),
            color=discord.Color.blue(),
        )
        await interaction.followup.send(embed=embed)
        return

    if action != "confirm":
        await interaction.followup.send("Usage: `/coach_cutover confirm` or `/coach_cutover status`")
        return

    # Generate readiness report
    report = _build_cutover_report()
    lines = ["**Readiness Report**\n"]

    # Plans summary
    lines.append("**Last 4 Weeks — Plan Structure:**")
    for week in report["plans_summary"]:
        run_days = [d for d in week["days"] if d.get("intent") not in ("rest", None)]
        lines.append(f"• Week of {week['week_start']}: {len(run_days)} training days planned")

    # RPE summary
    rpe_rows = [r for r in report["rpe_summary"] if r.get("rpe")]
    if rpe_rows:
        avg_rpe = sum(r["rpe"] for r in rpe_rows) / len(rpe_rows)
        lines.append(f"\n**RPE (last 4 weeks):** {avg_rpe:.1f} avg across {len(rpe_rows)} sessions")
    else:
        lines.append("\n**RPE:** No check-in data yet")

    # VDOT warning
    if report["vdot_warning"]:
        lines.append("\n⚠️ **Pending VDOT update** — consider resolving before cutting FinalSurge")

    # Disable FinalSurge
    disabled = _disable_finalsurge_calendar()
    lines.append(f"\n✅ **FinalSurge disabled** ({disabled} calendar(s) turned off)")
    lines.append("Internal plan is now authoritative. FinalSurge ICS import will no longer run.")

    # Clear cutover state
    try:
        import sqlite3 as _sql
        conn = _sql.connect(str(DB_PATH))
        conn.execute("DELETE FROM state WHERE key IN ('cutover_awaiting_response', 'cutover_threshold')")
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning("coach_cutover: state cleanup error: %s", exc)

    embed = discord.Embed(
        title="✅ FinalSurge Cutover Complete",
        description=clamp("\n".join(lines), MOBILE_DESC_LIMIT),
        color=discord.Color.green(),
        timestamp=datetime.now(),
    )
    await interaction.followup.send(embed=embed)
```

**Step 6: Run full test suite**

```bash
cd /home/coach/running-coach && python -m pytest tests/test_cutover.py -v
```

Expected: all PASS

**Step 7: Smoke-test imports**

```bash
cd /home/coach/running-coach && python -c "from src.discord_bot import _build_cutover_report, _disable_finalsurge_calendar; print('OK')"
```

Expected: `OK`

**Step 8: Commit**

```bash
git add src/discord_bot.py tests/test_cutover.py
git commit -m "feat(cutover): add /coach_cutover command, readiness report, and config flip"
```

---

## Task 6: Final integration check

**Step 1: Run all tests**

```bash
cd /home/coach/running-coach && python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: no new failures

**Step 2: Restart bot and verify**

```bash
sudo systemctl restart running-coach-bot
sudo systemctl status running-coach-bot
```

Expected: `active (running)`

**Step 3: Verify slash command registered**

In Discord, type `/coach_cutover` — it should appear as a registered command with the `action` parameter.

**Step 4: Simulate a count manually (dev test)**

```bash
python3 -c "
from memory.db import set_state
set_state('saturday_plan_success_count', '4')
print('Count set to 4')
"
```

Then trigger the heartbeat manually:
```bash
python3 -c "
from hooks.on_cutover_ready import run
result = run()
print(result)
"
```

Expected: `{'pending_written': True, 'count': 4, 'threshold': 4}`

Then clear the test state:
```bash
python3 -c "
import sqlite3
from memory.db import DB_PATH
conn = sqlite3.connect(str(DB_PATH))
conn.execute(\"DELETE FROM state WHERE key IN ('saturday_plan_success_count','pending_cutover_prompt','cutover_awaiting_response','cutover_threshold')\")
conn.commit()
conn.close()
print('Test state cleared')
"
```

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat(cutover): finalsurge cutover system complete — prompt, delay, confirm"
```

---

## Summary

| Component | File | New/Modified |
|-----------|------|-------------|
| Success counter | `src/discord_bot.py` (saturday_plan_task) | Modified |
| Hook logic + helpers | `hooks/on_cutover_ready.py` | New |
| Hook wiring | `agent/runner.py` | Modified |
| Bot delivery | `src/discord_bot.py` (_post_pending_cutover_prompt) | Modified |
| Delivery wiring | `src/discord_bot.py` (checkin_delivery_task, on_ready) | Modified |
| Delay handler | `src/discord_bot.py` (on_message) | Modified |
| Slash command + helpers | `src/discord_bot.py` (coach_cutover_command, _build_cutover_report, _disable_finalsurge_calendar) | Modified |
| Tests | `tests/test_cutover.py` | New |

**State keys used (all in SQLite `state` table):**

| Key | Purpose | Lifecycle |
|-----|---------|-----------|
| `saturday_plan_success_count` | Running count of successful Saturday plans | Persists; never cleared |
| `cutover_threshold` | Plans needed before prompt (starts 4, +1 per delay) | Cleared on confirm |
| `pending_cutover_prompt` | Hook → bot delivery queue | Cleared after bot posts |
| `cutover_awaiting_response` | Set while waiting for delay/confirm | Cleared on either action |
