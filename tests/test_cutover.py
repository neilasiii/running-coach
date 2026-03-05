#!/usr/bin/env python3
"""Tests for FinalSurge cutover counter and readiness hook."""

import json


def make_db(tmp_path):
    from memory.db import SCHEMA, _connect

    db = tmp_path / "coach.sqlite"
    conn = _connect(db)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    return db


def test_increment_saturday_count(tmp_path):
    db = make_db(tmp_path)
    from hooks.on_cutover_ready import _increment_success_count
    from memory.db import get_state

    _increment_success_count(db_path=db)
    assert get_state("saturday_plan_success_count", db_path=db) == "1"


def test_increment_saturday_count_accumulates(tmp_path):
    db = make_db(tmp_path)
    from hooks.on_cutover_ready import _increment_success_count
    from memory.db import get_state

    _increment_success_count(db_path=db)
    _increment_success_count(db_path=db)
    _increment_success_count(db_path=db)
    assert get_state("saturday_plan_success_count", db_path=db) == "3"


def test_only_increments_on_full_success(tmp_path):
    db = make_db(tmp_path)
    from memory.db import get_state

    assert get_state("saturday_plan_success_count", db_path=db) is None
    assert get_state("saturday_plan_success_count", db_path=db) is None


def test_hook_queues_prompt_at_threshold(tmp_path):
    db = make_db(tmp_path)
    from hooks.on_cutover_ready import run
    from memory.db import get_state, set_state

    set_state("saturday_plan_success_count", "4", db_path=db)
    result = run(db_path=db)

    assert result["pending_written"] is True
    assert get_state("pending_cutover_prompt", db_path=db) is not None


def test_hook_does_not_double_queue(tmp_path):
    db = make_db(tmp_path)
    from hooks.on_cutover_ready import run
    from memory.db import get_state, set_state

    set_state("saturday_plan_success_count", "4", db_path=db)
    first = run(db_path=db)
    second = run(db_path=db)

    assert first["pending_written"] is True
    assert second["pending_written"] is False
    raw = get_state("pending_cutover_prompt", db_path=db)
    payload = json.loads(raw)
    assert payload["count"] == 4


def test_hook_respects_delay(tmp_path):
    db = make_db(tmp_path)
    from hooks.on_cutover_ready import run
    from memory.db import set_state

    set_state("saturday_plan_success_count", "4", db_path=db)
    set_state("cutover_threshold", "5", db_path=db)
    result = run(db_path=db)
    assert result["pending_written"] is False


def test_hook_queues_after_delay_when_count_catches_up(tmp_path):
    db = make_db(tmp_path)
    from hooks.on_cutover_ready import run
    from memory.db import set_state

    set_state("saturday_plan_success_count", "5", db_path=db)
    set_state("cutover_threshold", "5", db_path=db)
    result = run(db_path=db)
    assert result["pending_written"] is True
