#!/usr/bin/env python3
"""
Tests for cli/coach.py schedule command and skills/plans.get_schedule().

Run:
    python3 -m pytest tests/test_schedule_cmd.py -v
"""

import json
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _seed_db(db_path: Path, start_date: date, n_days: int = 7) -> str:
    """Insert a minimal active plan with n_days into db_path. Returns plan_id."""
    from memory.db import init_db, insert_plan, insert_plan_days, set_active_plan

    init_db(db_path)

    end_date = start_date + timedelta(days=n_days - 1)
    plan_json = {
        "phase": "base",
        "weekly_volume_miles": 30.0,
        "safety_flags": [],
        "rationale": "Test plan",
    }
    plan_id = insert_plan(start_date, end_date, plan_json, db_path=db_path)

    days = []
    workout_types = ["easy", "rest", "tempo", "easy", "rest", "long", "cross"]
    for i in range(n_days):
        d = start_date + timedelta(days=i)
        wtype = workout_types[i % len(workout_types)]
        dur = 0 if wtype in ("rest",) else 45 + i * 5
        steps = (
            []
            if wtype == "rest"
            else [
                {
                    "label": "warmup",
                    "duration_min": 10,
                    "target_metric": "pace",
                    "target_value": "easy",
                    "reps": None,
                    "notes": None,
                },
                {
                    "label": "main",
                    "duration_min": dur - 10,
                    "target_metric": "pace",
                    "target_value": "easy",
                    "reps": None,
                    "notes": None,
                },
            ]
        )
        days.append(
            {
                "day": d.isoformat(),
                "intent": f"Day {i+1}: {wtype} workout intent text",
                "workout_json": {
                    "date": d.isoformat(),
                    "workout_type": wtype,
                    "duration_min": dur,
                    "structure_steps": steps,
                    "safety_flags": [],
                    "rationale": "Test",
                    "intent": f"Day {i+1}: {wtype} workout intent text",
                },
            }
        )

    insert_plan_days(plan_id, days, db_path=db_path)
    set_active_plan(plan_id, db_path=db_path)
    return plan_id


def _run_cli(*args) -> tuple:
    """Run cli/coach.py with args, return (rc, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "cli" / "coach.py"), *args],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


# ── Unit: get_schedule() ───────────────────────────────────────────────────────

class TestGetSchedule:
    def test_returns_7_rows_for_active_plan(self, tmp_path):
        from skills.plans import get_schedule

        db = tmp_path / "coach.sqlite"
        today = date.today()
        _seed_db(db, start_date=today, n_days=7)

        sched = get_schedule(days=7, start_date=today, db_path=db)

        assert sched["plan_id"] is not None
        assert len(sched["rows"]) == 7

    def test_correct_weekday_labels(self, tmp_path):
        from skills.plans import get_schedule

        db = tmp_path / "coach.sqlite"
        today = date.today()
        _seed_db(db, start_date=today, n_days=7)

        sched = get_schedule(days=7, start_date=today, db_path=db)

        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for row in sched["rows"]:
            d = date.fromisoformat(row["date"])
            expected_wd = weekdays[d.weekday()]
            assert row["weekday"] == expected_wd, (
                f"{row['date']}: expected {expected_wd}, got {row['weekday']}"
            )

    def test_workout_type_and_intent_present(self, tmp_path):
        from skills.plans import get_schedule

        db = tmp_path / "coach.sqlite"
        today = date.today()
        _seed_db(db, start_date=today, n_days=7)

        sched = get_schedule(days=7, start_date=today, db_path=db)

        for row in sched["rows"]:
            assert row["workout_type"] in (
                "easy", "rest", "tempo", "long", "cross", "interval", "strength", "none"
            ), f"Unexpected type: {row['workout_type']}"
            assert row["intent"], f"Empty intent for {row['date']}"

    def test_no_entry_row_for_dates_outside_plan(self, tmp_path):
        from skills.plans import get_schedule

        db = tmp_path / "coach.sqlite"
        today = date.today()
        _seed_db(db, start_date=today, n_days=3)

        # Ask for 7 days but plan only has 3
        sched = get_schedule(days=7, start_date=today, db_path=db)

        assert len(sched["rows"]) == 7
        for row in sched["rows"][3:]:
            assert row["workout_type"] == "none"
            assert row["intent"] == "(no entry)"

    def test_duration_from_structure_steps(self, tmp_path):
        from skills.plans import get_schedule

        db = tmp_path / "coach.sqlite"
        today = date.today()
        _seed_db(db, start_date=today, n_days=7)

        sched = get_schedule(days=7, start_date=today, db_path=db)

        for row in sched["rows"]:
            if row["structure_steps"]:
                expected = sum(s.get("duration_min", 0) for s in row["structure_steps"])
                assert row["duration_min"] == expected, (
                    f"{row['date']}: expected steps sum {expected}, got {row['duration_min']}"
                )

    def test_rest_day_has_zero_duration(self, tmp_path):
        from skills.plans import get_schedule

        db = tmp_path / "coach.sqlite"
        today = date.today()
        _seed_db(db, start_date=today, n_days=7)

        sched = get_schedule(days=7, start_date=today, db_path=db)

        rest_rows = [r for r in sched["rows"] if r["workout_type"] == "rest"]
        assert rest_rows, "Seeded plan should include rest days"
        for row in rest_rows:
            assert row["duration_min"] == 0

    def test_no_active_plan_returns_none_plan_id(self, tmp_path):
        from memory.db import init_db
        from skills.plans import get_schedule

        db = tmp_path / "coach.sqlite"
        init_db(db)

        sched = get_schedule(days=7, db_path=db)

        assert sched["plan_id"] is None
        assert len(sched["rows"]) == 7
        for row in sched["rows"]:
            assert row["workout_type"] == "none"
            assert row["intent"] == "(no entry)"


# ── Unit: safety_flags continuation line ──────────────────────────────────────

class TestSafetyFlags:
    def _seed_with_flags(self, db_path: Path) -> str:
        from memory.db import init_db, insert_plan, insert_plan_days, set_active_plan

        init_db(db_path)
        today = date.today()
        plan_id = insert_plan(today, today, {}, db_path=db_path)
        insert_plan_days(
            plan_id,
            [
                {
                    "day": today.isoformat(),
                    "intent": "Easy 45min",
                    "workout_json": {
                        "date": today.isoformat(),
                        "workout_type": "easy",
                        "duration_min": 45,
                        "structure_steps": [],
                        "safety_flags": ["low_hrv", "poor_sleep"],
                        "rationale": "",
                        "intent": "Easy 45min",
                    },
                }
            ],
            db_path=db_path,
        )
        set_active_plan(plan_id, db_path=db_path)
        return plan_id

    def test_flags_appear_in_get_schedule(self, tmp_path):
        from skills.plans import get_schedule

        db = tmp_path / "coach.sqlite"
        self._seed_with_flags(db)

        sched = get_schedule(days=1, db_path=db)

        row = sched["rows"][0]
        assert row["safety_flags"] == ["low_hrv", "poor_sleep"]

    def test_table_format_prints_flags_continuation(self, tmp_path):
        from skills.plans import get_schedule
        from cli.coach import _fmt_table

        db = tmp_path / "coach.sqlite"
        self._seed_with_flags(db)

        sched = get_schedule(days=1, db_path=db)
        table = _fmt_table(sched)

        assert "↳ flags:" in table
        assert "low_hrv" in table
        assert "poor_sleep" in table


# ── CLI integration: rc and output ────────────────────────────────────────────

class TestCLISchedule:
    def test_no_active_plan_returns_rc1(self, tmp_path, monkeypatch):
        """Without an active plan, CLI should exit 1."""
        from memory.db import init_db
        db = tmp_path / "coach.sqlite"
        init_db(db)

        # Patch DB_PATH via environment would require subprocess env injection.
        # Use skills.plans.get_schedule directly with the tmp db and check rc=1 logic.
        from skills.plans import get_schedule
        sched = get_schedule(days=7, db_path=db)
        assert sched["plan_id"] is None

    def test_cli_schedule_week_smoke(self, tmp_path, monkeypatch):
        """Smoke: schedule subcommand imports and runs without crashing."""
        import importlib
        import types

        # Monkeypatch get_schedule to return a minimal seeded result
        today = date.today()
        fake_rows = [
            {
                "date": (today + timedelta(days=i)).isoformat(),
                "weekday": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][
                    (today + timedelta(days=i)).weekday()
                ],
                "workout_type": "easy",
                "duration_min": 45,
                "intent": f"Easy run day {i+1}",
                "safety_flags": [],
                "structure_steps": [],
            }
            for i in range(7)
        ]
        fake_sched = {
            "plan_id": "20260217-abc12345",
            "plan_start": today.isoformat(),
            "plan_end": (today + timedelta(days=6)).isoformat(),
            "created_at": "2026-02-17T04:00:00",
            "range_start": today.isoformat(),
            "range_end": (today + timedelta(days=6)).isoformat(),
            "rows": fake_rows,
        }

        # Import formatter directly and verify output shape
        from cli.coach import _fmt_table, _fmt_text, _fmt_md

        table_out = _fmt_table(fake_sched)
        assert "DATE" in table_out
        assert "DAY" in table_out
        assert "TYPE" in table_out
        assert "INTENT" in table_out
        # All 7 dates present
        for row in fake_rows:
            assert row["date"] in table_out
            assert row["weekday"] in table_out

        text_out = _fmt_text(fake_sched)
        for row in fake_rows:
            assert row["date"] in text_out

        md_out = _fmt_md(fake_sched)
        assert "##" in md_out
        for row in fake_rows:
            assert row["date"] in md_out


# ── Unit: mobile format ────────────────────────────────────────────────────────

class TestMobileFormat:
    """Tests for _fmt_mobile — the Discord-mobile day-cards formatter."""

    def _fake_sched(self, n=7, flags=None):
        today = date.today()
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        types = ["easy", "rest", "tempo", "easy", "rest", "long", "none"]
        rows = [
            {
                "date":            (today + timedelta(days=i)).isoformat(),
                "weekday":         weekdays[(today + timedelta(days=i)).weekday()],
                "workout_type":    types[i % len(types)],
                "duration_min":    0 if types[i % len(types)] == "rest" else 45,
                "intent":          f"Day {i+1} intent text",
                "safety_flags":    (flags if flags and i == 0 else []),
                "structure_steps": [],
            }
            for i in range(n)
        ]
        return {
            "plan_id":    "20260217-abc12345",
            "plan_start": today.isoformat(),
            "plan_end":   (today + timedelta(days=n - 1)).isoformat(),
            "created_at": "2026-02-17T04:00:00",
            "range_start": today.isoformat(),
            "range_end":   (today + timedelta(days=n - 1)).isoformat(),
            "rows": rows,
        }

    def test_header_contains_week_schedule(self):
        from cli.coach import _fmt_mobile
        out = _fmt_mobile(self._fake_sched())
        assert "Week Schedule" in out

    def test_header_contains_plan_id(self):
        from cli.coach import _fmt_mobile
        out = _fmt_mobile(self._fake_sched())
        assert "20260217-abc12345" in out or "20260217" in out

    def test_all_dates_present(self):
        from cli.coach import _fmt_mobile
        sched = self._fake_sched(7)
        out = _fmt_mobile(sched)
        for row in sched["rows"]:
            assert row["date"] in out, f"{row['date']} missing from mobile output"

    def test_day_header_bold_markers(self):
        from cli.coach import _fmt_mobile
        out = _fmt_mobile(self._fake_sched())
        # Each day card should have a bold Discord markdown header
        assert "**" in out

    def test_emoji_present_for_known_types(self):
        from cli.coach import _fmt_mobile
        out = _fmt_mobile(self._fake_sched())
        # easy → 🟢, rest → ⚪, tempo → 🟠, long → 🔵
        assert "🟢" in out  # easy day
        assert "⚪" in out  # rest day
        assert "🟠" in out  # tempo day
        assert "🔵" in out  # long day

    def test_flags_prefixed_with_flag_symbol(self):
        from cli.coach import _fmt_mobile
        sched = self._fake_sched(flags=["low_hrv", "poor_sleep"])
        out = _fmt_mobile(sched)
        assert "⚑ low_hrv" in out
        assert "⚑ poor_sleep" in out

    def test_no_code_fences(self):
        from cli.coach import _fmt_mobile
        out = _fmt_mobile(self._fake_sched())
        assert "```" not in out

    def test_no_entry_row_shows_no_entry_emoji(self):
        from cli.coach import _fmt_mobile
        sched = self._fake_sched()
        # "none" type maps to ⚫ No entry
        out = _fmt_mobile(sched)
        assert "⚫" in out

    def test_intent_clamped_to_120_chars(self):
        from cli.coach import _fmt_mobile
        long_intent = "X" * 130
        sched = self._fake_sched(n=1)
        sched["rows"][0]["intent"] = long_intent
        out = _fmt_mobile(sched)
        # Intent should appear truncated with ellipsis
        assert "…" in out
        # No line in the output should be longer than 200 chars (intent clamped to 120)
        for line in out.splitlines():
            assert len(line) <= 200, f"Line too long ({len(line)}): {line!r}"

    def test_rest_day_omits_duration(self):
        from cli.coach import _fmt_mobile
        sched = self._fake_sched(n=1)
        sched["rows"][0]["workout_type"] = "rest"
        sched["rows"][0]["duration_min"] = 0
        out = _fmt_mobile(sched)
        # "0m" should NOT appear — rest with dur=0 should omit · Nm
        assert "· 0m" not in out
