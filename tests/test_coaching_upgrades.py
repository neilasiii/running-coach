from datetime import date, timedelta

from brain.macro_plan import validate_macro_plan
from brain.planner import _enforce_structure_constraints, _normalize_weekly_structure, replan_remaining_week
from brain.schemas import MacroPaces, MacroPlan, MacroWeek, PlanDay, PlanDecision
from memory.db import get_active_plan, init_db, insert_plan, insert_plan_days, set_active_plan


def _macro_week(i: int, ws: str, target: float, ceil: float | None = None):
    return MacroWeek(
        week_number=i,
        week_start=ws,
        phase="base",
        volume_floor_miles=max(0, target - 2),
        volume_target_miles=target,
        volume_ceiling_miles=ceil if ceil is not None else target + 2,
        long_run_max_min=60,
        intensity_budget="low",
        quality_sessions_allowed=0,
        key_workout_type="easy",
        recommended_session_types=["easy", "long"],
        paces=MacroPaces(easy="10:00/mi", tempo=None, interval=None, long_run="10:30/mi"),
        planner_notes="",
        phase_rationale="",
    )


def test_macro_band_validation_order_and_ceiling_jump():
    start = date(2026, 1, 4)
    ok = MacroPlan(
        mode="base_block",
        race_date=None,
        race_name=None,
        race_distance=None,
        vdot=45,
        start_week=start.isoformat(),
        total_weeks=2,
        peak_weekly_miles=22,
        rationale="ok",
        weeks=[
            _macro_week(1, start.isoformat(), 20),
            _macro_week(2, (start + timedelta(days=7)).isoformat(), 21),
        ],
    )
    assert validate_macro_plan(ok).ok

    bad_order = ok.model_copy(deep=True)
    bad_order.weeks[0].volume_floor_miles = 22
    bad_order.weeks[0].volume_target_miles = 20
    assert not validate_macro_plan(bad_order).ok

    bad_jump = ok.model_copy(deep=True)
    bad_jump.weeks[1].volume_ceiling_miles = 30
    errs = validate_macro_plan(bad_jump)
    assert not errs.ok
    assert any("ceiling ramp" in e for e in errs.errors)


def test_flexible_weekly_run_counts_and_blocked_days():
    start = date(2026, 1, 4)
    d = PlanDecision.model_validate(
        {
            "week_start": start.isoformat(),
            "week_end": (start + timedelta(days=6)).isoformat(),
            "phase": "base",
            "weekly_volume_miles": 20,
            "safety_flags": [],
            "rationale": "",
            "context_hash": "x",
            "days": [
                {
                    "date": (start + timedelta(days=i)).isoformat(),
                    "intent": "",
                    "workout_type": "easy" if i < 6 else "rest",
                    "priority": "optional" if i in (0, 1) else "nice_to_have",
                    "duration_min": 30,
                    "structure_steps": [{"label": "main", "duration_min": 30, "target_metric": "rpe", "target_value": "RPE 4"}],
                    "safety_flags": [],
                    "rationale": "",
                }
                for i in range(7)
            ],
        }
    )
    structure = _normalize_weekly_structure({"athlete": {"weekly_structure": {"runs_per_week": 4, "max_runs_per_week": 4, "non_negotiable_blocked_days": ["sunday"]}}})
    _enforce_structure_constraints(d, structure)
    runs = [x for x in d.days if x.workout_type in {"easy", "tempo", "interval", "long"}]
    assert len(runs) <= 4
    assert d.days[0].workout_type in {"rest", "cross"}


def test_replan_remaining_week_persists_revision_metadata(tmp_path):
    db = tmp_path / "coach.sqlite"
    init_db(db)
    start = date.today() - timedelta(days=date.today().weekday() + 1)
    end = start + timedelta(days=6)
    plan = {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "phase": "quality",
        "weekly_volume_miles": 25,
        "safety_flags": [],
        "rationale": "",
        "context_hash": "x",
        "days": [
            {
                "date": (start + timedelta(days=i)).isoformat(),
                "intent": "",
                "workout_type": "tempo" if i == 2 else ("long" if i == 4 else "easy"),
                "priority": "must_do" if i in (2, 4) else "nice_to_have",
                "duration_min": 60,
                "structure_steps": [{"label": "main", "duration_min": 60, "target_metric": "rpe", "target_value": "RPE 5"}],
                "safety_flags": [],
                "rationale": "",
            }
            for i in range(7)
        ],
    }
    pid = insert_plan(start, end, plan, context_hash="x", db_path=db)
    insert_plan_days(pid, [{"day": x["date"], "intent": x["intent"], "workout_json": x} for x in plan["days"]], db_path=db)
    set_active_plan(pid, db_path=db)

    decision = replan_remaining_week({"today": date.today().isoformat()}, [date.today().isoformat()], db_path=db)
    assert isinstance(decision, PlanDecision)
    active = get_active_plan(db_path=db)
    assert active["supersedes_plan_id"] == pid
    assert active["replan_reason"] == "missed_workout"
    assert active["plan_revision_number"] == 2
