"""
Skills wrapper: Garmin sync.

Calls sync_garmin_data.sh after a native Python cache-age check.
Does NOT modify health_data_cache.json format — that remains owned by
src/garmin_sync.py (sacred invariant).
"""

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent
CACHE_FILE = PROJECT_ROOT / "data" / "health" / "health_data_cache.json"
log = logging.getLogger("skills.garmin_sync")


def _cache_age_minutes() -> Optional[float]:
    """
    Return the age of health_data_cache.json in minutes, or None if
    the file is absent or the timestamp cannot be parsed.
    """
    try:
        with open(CACHE_FILE) as f:
            data = json.load(f)
        ts_str = data.get("last_updated", "")
        if not ts_str:
            return None
        last_updated = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - last_updated).total_seconds() / 60
    except Exception:
        return None


def run(
    force: bool = False,
    source: str = "agent",
    days: int = None,
    check_only: bool = False,
    max_age_minutes: int = 30,
) -> dict:
    """
    Run Garmin sync and record a sync event in SQLite.

    Cache-age check is performed natively in Python:
    - If cache is younger than max_age_minutes and force=False, skip sync.
    - If cache is stale, absent, or force=True, run sync_garmin_data.sh.

    Args:
        force:           Skip cache-age check and always sync.
        source:          Who triggered this sync ('agent', 'cli', 'discord', …).
        days:            Number of days to pass to sync_garmin_data.sh.
        check_only:      Pass --check-only to sync_garmin_data.sh (preview).
        max_age_minutes: Maximum acceptable cache age in minutes (default 30).

    Returns:
        dict with keys: success, returncode, stdout, stderr, event_id, summary,
                        skipped (True when cache-hit short-circuit fired).
    """
    from memory.db import (
        init_db, insert_event, log_task_start, log_task_finish,
        record_sync_start, record_sync_finish,
    )

    init_db()

    # ── Cache-age check (Python-native, replaces smart_sync.sh logic) ──────────
    if not force and not check_only:
        age = _cache_age_minutes()
        if age is not None and age < max_age_minutes:
            log.info(
                "Cache is %.1f min old (max %d min) — skipping sync",
                age, max_age_minutes,
            )
            return {
                "success": True,
                "returncode": 0,
                "stdout": f"Cache is {age:.0f}m old (max {max_age_minutes}m). Skipping sync.",
                "stderr": "",
                "event_id": "skipped",
                "summary": f"Cache fresh ({age:.0f}m); skipped.",
                "skipped": True,
            }

    # ── Build sync command ──────────────────────────────────────────────────────
    cmd = ["bash", str(PROJECT_ROOT / "bin" / "sync_garmin_data.sh")]
    if days is not None:
        cmd += ["--days", str(days)]
    if check_only:
        cmd.append("--check-only")

    run_id = log_task_start("garmin_sync")
    sync_run_id = record_sync_start(source=source, days_requested=days)

    log.info("Running Garmin sync: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=180,
        )
    except subprocess.TimeoutExpired as exc:
        log_task_finish(
            run_id, "failed",
            details={"error": "timeout", "timeout_sec": 180},
        )
        record_sync_finish(sync_run_id, "failed", error_summary="timeout after 180s")
        raise RuntimeError("garmin_sync timed out after 180s") from exc

    success = result.returncode == 0
    summary = (result.stdout if success else result.stderr).strip()[:500]

    if success:
        log_task_finish(run_id, "success", details={"summary": summary[:200]})
        record_sync_finish(sync_run_id, "success")
    else:
        log.warning("Garmin sync failed rc=%d stderr: %s", result.returncode, result.stderr[:300])
        log_task_finish(
            run_id, "failed",
            details={"returncode": result.returncode, "stderr": result.stderr[:500]},
        )
        record_sync_finish(
            sync_run_id, "failed",
            error_summary=result.stderr[:200] if result.stderr else f"rc={result.returncode}",
        )

    event_id = insert_event(
        event_type="garmin_sync",
        payload={
            "returncode": result.returncode,
            "force": force,
            "success": success,
            "summary": summary[:200],
        },
        source="skills.garmin_sync",
    )

    log.info("Garmin sync rc=%d event_id=%s task_run_id=%d", result.returncode, event_id[:8], run_id)

    return {
        "success": success,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "event_id": event_id,
        "summary": summary,
        "skipped": False,
    }
