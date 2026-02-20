"""
Tests for B11-011 — activities table in SQLite schema.

Scope:
  - init_db() creates activities table (additive)
  - upsert_activity() inserts and updates rows idempotently
  - get_activities() returns rows in date range, optionally filtered by type
"""
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

import pytest


def _tmp_db() -> Path:
    tf = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tf.close()
    return Path(tf.name)


class TestActivitiesSchema:
    def setup_method(self):
        self.db = _tmp_db()
        from memory.db import init_db
        init_db(db_path=self.db)

    def test_table_exists_after_init(self):
        conn = sqlite3.connect(str(self.db))
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='activities'"
        ).fetchone()
        conn.close()
        assert row is not None, "activities table not created by init_db()"

    def test_existing_tables_not_dropped(self):
        conn = sqlite3.connect(str(self.db))
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        for expected in ("plans", "plan_days", "events", "sync_runs", "daily_metrics"):
            assert expected in tables, f"table {expected!r} was dropped by migration"

    def test_upsert_inserts_row(self):
        from memory.db import upsert_activity, get_activities

        d = date(2026, 2, 10)
        upsert_activity(
            "act-001", d, activity_type="running", name="Easy run",
            duration_s=3600, distance_m=8000, avg_hr=140.0, max_hr=158.0,
            avg_pace_s=450.0, calories=520.0, raw={"source": "garmin"},
            db_path=self.db,
        )
        rows = get_activities(d, d, db_path=self.db)
        assert len(rows) == 1
        assert rows[0]["activity_id"] == "act-001"
        assert rows[0]["activity_type"] == "running"
        assert rows[0]["name"] == "Easy run"
        assert rows[0]["distance_m"] == pytest.approx(8000)

    def test_upsert_updates_existing_row(self):
        from memory.db import upsert_activity, get_activities

        d = date(2026, 2, 11)
        upsert_activity("act-002", d, activity_type="running", distance_m=5000, db_path=self.db)
        upsert_activity("act-002", d, activity_type="running", distance_m=8500, db_path=self.db)

        rows = get_activities(d, d, db_path=self.db)
        assert len(rows) == 1
        assert rows[0]["distance_m"] == pytest.approx(8500)

    def test_null_columns_allowed(self):
        from memory.db import upsert_activity, get_activities

        d = date(2026, 2, 12)
        upsert_activity("act-003", d, db_path=self.db)

        rows = get_activities(d, d, db_path=self.db)
        assert len(rows) == 1
        assert rows[0]["duration_s"] is None
        assert rows[0]["avg_hr"] is None

    def test_get_activities_date_range(self):
        from memory.db import upsert_activity, get_activities

        for i in range(5):
            upsert_activity(
                f"act-{i}", date(2026, 2, i + 1), activity_type="running",
                db_path=self.db,
            )

        rows = get_activities(date(2026, 2, 2), date(2026, 2, 4), db_path=self.db)
        assert len(rows) == 3

    def test_get_activities_type_filter(self):
        from memory.db import upsert_activity, get_activities

        d = date(2026, 2, 15)
        upsert_activity("run-1", d, activity_type="running", db_path=self.db)
        upsert_activity("str-1", d, activity_type="strength_training", db_path=self.db)

        running = get_activities(d, d, activity_type="running", db_path=self.db)
        assert len(running) == 1
        assert running[0]["activity_type"] == "running"

    def test_get_activities_empty_range(self):
        from memory.db import get_activities
        rows = get_activities(date(2025, 1, 1), date(2025, 1, 7), db_path=self.db)
        assert rows == []
