# Onboarding Wizard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an interactive onboarding wizard that detects fresh clones, interviews new athletes conversationally, sets up Garmin auth, writes all athlete context files, and optionally configures the Discord bot.

**Architecture:** A Claude agent (`.claude/agents/onboarding-wizard.md`) handles conversation and sequencing; a standalone Python script (`bin/check_setup.py`) handles all system checks and outputs JSON the agent can read. CLAUDE.md gets a small first-run detection block that prompts the user if the system looks unconfigured.

**Tech Stack:** Python 3.8+, pytest, existing `src/garmin_sync.py` auth path, existing `data/athlete/` file structure, existing systemd service pattern.

---

### Task 1: Create `bin/check_setup.py` — core checks (no Garmin auth yet)

**Files:**
- Create: `bin/check_setup.py`
- Create: `tests/test_check_setup.py`

**Step 1: Write the failing tests**

```python
# tests/test_check_setup.py
import json
import sys
import os
import subprocess
from pathlib import Path
import pytest

SCRIPT = Path(__file__).parent.parent / "bin" / "check_setup.py"

def run_check(args=(), env_overrides=None, tmp_path=None):
    """Run check_setup.py with --json, return parsed output."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    cmd = [sys.executable, str(SCRIPT), "--json"]
    if tmp_path:
        cmd += ["--root", str(tmp_path)]
    cmd += list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return json.loads(result.stdout)


def test_python_check_passes(tmp_path):
    data = run_check(tmp_path=tmp_path)
    assert data["checks"]["python"]["ok"] is True
    assert "version" in data["checks"]["python"]


def test_athlete_files_missing_when_no_goals(tmp_path):
    data = run_check(tmp_path=tmp_path)
    assert data["checks"]["athlete_files"]["ok"] is False
    assert "goals.md" in data["checks"]["athlete_files"]["missing"]


def test_athlete_files_ok_when_present(tmp_path):
    athlete_dir = tmp_path / "data" / "athlete"
    athlete_dir.mkdir(parents=True)
    required = ["goals.md", "training_preferences.md", "upcoming_races.md"]
    for f in required:
        (athlete_dir / f).write_text("# content")
    data = run_check(tmp_path=tmp_path)
    assert data["checks"]["athlete_files"]["ok"] is True


def test_health_cache_missing(tmp_path):
    data = run_check(tmp_path=tmp_path)
    assert data["checks"]["health_cache"]["ok"] is False


def test_health_cache_present(tmp_path):
    cache_dir = tmp_path / "data" / "health"
    cache_dir.mkdir(parents=True)
    (cache_dir / "health_data_cache.json").write_text('{"activities": [1]}')
    data = run_check(tmp_path=tmp_path)
    assert data["checks"]["health_cache"]["ok"] is True


def test_onboarding_needed_when_athlete_files_missing(tmp_path):
    data = run_check(tmp_path=tmp_path)
    assert data["onboarding_needed"] is True


def test_onboarding_not_needed_when_complete(tmp_path):
    athlete_dir = tmp_path / "data" / "athlete"
    athlete_dir.mkdir(parents=True)
    for f in ["goals.md", "training_preferences.md", "upcoming_races.md"]:
        (athlete_dir / f).write_text("# content")
    cache_dir = tmp_path / "data" / "health"
    cache_dir.mkdir(parents=True)
    (cache_dir / "health_data_cache.json").write_text('{"activities": [1]}')
    data = run_check(tmp_path=tmp_path)
    assert data["onboarding_needed"] is False


def test_garmin_credentials_missing_when_no_env(tmp_path):
    env = {k: v for k, v in os.environ.items()
           if k not in ("GARMIN_EMAIL", "GARMIN_PASSWORD")}
    data = run_check(tmp_path=tmp_path, env_overrides={"GARMIN_EMAIL": "", "GARMIN_PASSWORD": ""})
    assert data["checks"]["garmin_creds"]["ok"] is False


def test_garmin_credentials_present(tmp_path):
    data = run_check(
        tmp_path=tmp_path,
        env_overrides={"GARMIN_EMAIL": "test@example.com", "GARMIN_PASSWORD": "secret"}
    )
    assert data["checks"]["garmin_creds"]["ok"] is True


def test_discord_config_missing(tmp_path):
    data = run_check(tmp_path=tmp_path)
    assert data["checks"]["discord"]["ok"] is False


def test_discord_config_present(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "discord.env").write_text("DISCORD_BOT_TOKEN=abc123")
    data = run_check(tmp_path=tmp_path)
    assert data["checks"]["discord"]["ok"] is True


def test_json_output_has_all_keys(tmp_path):
    data = run_check(tmp_path=tmp_path)
    assert "onboarding_needed" in data
    assert "checks" in data
    expected_keys = {"python", "deps", "athlete_files", "health_cache",
                     "garmin_creds", "discord", "systemd"}
    assert expected_keys.issubset(data["checks"].keys())
```

**Step 2: Run tests to verify they fail**

```bash
cd /home/coach/running-coach
python -m pytest tests/test_check_setup.py -v 2>&1 | head -30
```

Expected: errors like `FileNotFoundError` or `JSONDecodeError` because `bin/check_setup.py` doesn't exist yet.

**Step 3: Write `bin/check_setup.py`**

```python
#!/usr/bin/env python3
"""
check_setup.py — System check script for running-coach onboarding.

Usage:
    python3 bin/check_setup.py           # Human-readable output
    python3 bin/check_setup.py --json    # JSON output for agent consumption
    python3 bin/check_setup.py --fix     # Auto-fix where possible
    python3 bin/check_setup.py --json --root /some/path  # Use alternate root
"""

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


def _project_root(override=None):
    if override:
        return Path(override)
    return Path(__file__).parent.parent


def check_python():
    v = sys.version_info
    ok = v >= (3, 8)
    return {"ok": ok, "version": f"{v.major}.{v.minor}.{v.micro}"}


def check_deps(root):
    req = root / "requirements.txt"
    if not req.exists():
        return {"ok": False, "reason": "requirements.txt not found"}
    result = subprocess.run(
        [sys.executable, "-m", "pip", "check"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return {"ok": True}
    # Try to find missing packages vs conflicts
    missing = []
    for line in result.stdout.splitlines():
        if "not installed" in line.lower():
            pkg = line.split()[0]
            missing.append(pkg)
    return {"ok": False, "missing": missing or ["see pip check output"]}


def check_athlete_files(root):
    athlete_dir = root / "data" / "athlete"
    required = ["goals.md", "training_preferences.md", "upcoming_races.md"]
    missing = [f for f in required if not (athlete_dir / f).exists()]
    return {"ok": len(missing) == 0, "missing": missing}


def check_health_cache(root):
    cache = root / "data" / "health" / "health_data_cache.json"
    if not cache.exists():
        return {"ok": False, "reason": "file not found"}
    try:
        data = json.loads(cache.read_text())
        if not data:
            return {"ok": False, "reason": "empty"}
        return {"ok": True}
    except json.JSONDecodeError:
        return {"ok": False, "reason": "invalid JSON"}


def check_garmin_creds():
    email = os.environ.get("GARMIN_EMAIL", "").strip()
    password = os.environ.get("GARMIN_PASSWORD", "").strip()
    # Also accept token-based auth
    token_dir = Path.home() / ".garminconnect"
    has_tokens = token_dir.exists() and any(token_dir.iterdir())
    if (email and password) or has_tokens:
        return {"ok": True, "method": "tokens" if has_tokens else "password"}
    return {"ok": False, "reason": "no credentials or tokens found"}


def check_discord(root):
    cfg = root / "config" / "discord.env"
    if not cfg.exists():
        return {"ok": False, "reason": "config/discord.env not found"}
    content = cfg.read_text()
    if "DISCORD_BOT_TOKEN" not in content:
        return {"ok": False, "reason": "DISCORD_BOT_TOKEN not set in config/discord.env"}
    return {"ok": True}


def check_systemd():
    result = subprocess.run(
        ["systemctl", "is-enabled", "running-coach-bot"],
        capture_output=True, text=True
    )
    ok = result.returncode == 0 and result.stdout.strip() == "enabled"
    return {"ok": ok}


def auto_fix(root):
    fixes = []
    # Create data directories
    for d in ["data/athlete", "data/health", "data/plans", "data/calendar", "config"]:
        path = root / d
        if not path.exists():
            path.mkdir(parents=True)
            fixes.append(f"Created {d}/")
    # Install deps
    req = root / "requirements.txt"
    if req.exists():
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req), "-q"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            fixes.append("Installed Python dependencies")
    return fixes


def run_checks(root):
    return {
        "python": check_python(),
        "deps": check_deps(root),
        "athlete_files": check_athlete_files(root),
        "health_cache": check_health_cache(root),
        "garmin_creds": check_garmin_creds(),
        "discord": check_discord(root),
        "systemd": check_systemd(),
    }


def onboarding_needed(checks):
    return (
        not checks["athlete_files"]["ok"] or
        not checks["health_cache"]["ok"]
    )


def print_human(checks, needed):
    icons = {True: "✅", False: "❌"}
    print("\nRunning Coach — Setup Status\n" + "=" * 32)
    labels = {
        "python": "Python >= 3.8",
        "deps": "Python dependencies",
        "athlete_files": "Athlete profile files",
        "health_cache": "Garmin health data",
        "garmin_creds": "Garmin credentials",
        "discord": "Discord bot config",
        "systemd": "Discord bot service",
    }
    for key, label in labels.items():
        c = checks[key]
        icon = icons[c["ok"]]
        detail = ""
        if not c["ok"]:
            detail = f" — {c.get('reason') or ', '.join(c.get('missing', []))}"
        print(f"  {icon} {label}{detail}")
    print()
    if needed:
        print("Onboarding needed: run @onboarding-wizard in Claude Code")
    else:
        print("All clear — system ready")
    print()


def main():
    parser = argparse.ArgumentParser(description="Check running-coach setup")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--fix", action="store_true", help="Auto-fix where possible")
    parser.add_argument("--root", help="Project root override (for testing)")
    args = parser.parse_args()

    root = _project_root(args.root)

    if args.fix:
        fixes = auto_fix(root)
        if fixes:
            print("Fixed:\n" + "\n".join(f"  - {f}" for f in fixes))

    checks = run_checks(root)
    needed = onboarding_needed(checks)

    if args.json:
        print(json.dumps({"onboarding_needed": needed, "checks": checks}))
    else:
        print_human(checks, needed)


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_check_setup.py -v
```

Expected: all tests PASS.

**Step 5: Make executable and commit**

```bash
chmod +x bin/check_setup.py
git add bin/check_setup.py tests/test_check_setup.py
git commit -m "feat(onboarding): add check_setup.py system diagnostic script"
```

---

### Task 2: Add first-run detection to CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (after the Overview section)

**Step 1: Read current CLAUDE.md top section**

Read the file and find the line number where the "AI Hallucination Prevention" section starts (currently after "## Overview"). The new block goes between Overview and AI Hallucination Prevention.

**Step 2: Insert the first-run detection block**

Add this section after `## Overview` (before `## CRITICAL: Date/Day-of-Week Verification`):

```markdown
## First Run Detection

At the start of every Claude Code session, silently run:
```bash
python3 bin/check_setup.py --json 2>/dev/null
```
If the output contains `"onboarding_needed": true`, say:

> "I notice this looks like a fresh setup. Want me to walk you through getting everything configured? It takes about 10–15 minutes and covers Garmin sync, your athlete profile, and optionally the Discord bot. Just say **yes** to start."

If the user says yes, invoke the `@onboarding-wizard` agent. If they say no, proceed normally. Do not repeat this prompt once `data/athlete/goals.md` exists.
```

Also add to the Key Commands section (after the Health Data Management header):

```markdown
**Re-run onboarding (update profile, add a race, reconfigure):**
```bash
# In Claude Code, type:
@onboarding-wizard
```
The wizard skips any steps that are already complete.
```

**Step 3: Verify the file looks right**

Read back the relevant sections of CLAUDE.md and confirm the additions are in place.

**Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "feat(onboarding): add first-run detection and re-onboarding note to CLAUDE.md"
```

---

### Task 3: Write the onboarding wizard agent

**Files:**
- Create: `.claude/agents/onboarding-wizard.md`

**Step 1: Write the agent file**

```markdown
---
name: onboarding-wizard
description: Interactive setup wizard for new users. Guides through Garmin auth, athlete profile creation, Discord bot setup. Invoke when user says yes to the first-run prompt, or anytime via @onboarding-wizard.
---

# Onboarding Wizard

You are setting up the running coach system for a new user. Work through the six phases below in order. At the start of each phase, run `python3 bin/check_setup.py --json` to see current state — skip any phase whose checks already pass.

Always speak in plain, friendly language. This is not a technical document — it's a conversation.

---

## Phase 1: System Checks

Run:
```bash
python3 bin/check_setup.py --json
```

Display results as a checklist. For any fixable issues, run:
```bash
python3 bin/check_setup.py --fix
```

If Python deps are missing, run:
```bash
pip install -r requirements.txt
```

If Python itself is too old (< 3.8), tell the user they need to upgrade Python and stop — you can't proceed.

Once all fixable issues are resolved, move to Phase 2.

---

## Phase 2: Garmin Setup

Check `garmin_creds` from the JSON output.

**If credentials are missing:**

Say: "I need your Garmin Connect credentials to pull your training data. These are the same email and password you use at connect.garmin.com."

Ask for email, then password. Write them to `~/.bashrc`:
```bash
echo 'export GARMIN_EMAIL=<email>' >> ~/.bashrc
echo 'export GARMIN_PASSWORD=<password>' >> ~/.bashrc
source ~/.bashrc
```

**Test authentication:**
```bash
python3 src/garmin_token_auth.py --test
```

If it fails with a 403 error, explain: "Garmin blocks automated logins on some accounts. We can use a one-time browser login to generate a token instead." Then run:
```bash
python3 bin/generate_garmin_tokens.py
```

Walk the user through the browser step. Once complete, test again.

**Run initial sync** (once auth is confirmed working):
```bash
bash bin/sync_garmin_data.sh --days 90
```

Report what was found: number of activities, most recent activity date. If no activities found, ask the user to confirm their Garmin device is synced to the Garmin Connect app.

---

## Phase 3: Athlete Interview

Say: "Now I need to learn a bit about you to set up your coaching profile. I'll ask a few questions — just answer naturally."

Ask these questions one at a time. Wait for each answer before asking the next.

1. "What's your name?" (first name is fine)

2. "Do you have a recent race result I can use to calibrate your training paces? If yes, what was the race distance and your finish time?"
   - If yes: run `python3 src/vdot_calculator.py` mentally or via the VDOT API to calculate VDOT. Tell them their VDOT and what their easy, tempo, and interval paces would be.
   - If no: estimate from Garmin data if available, or ask for a recent long run pace to estimate.

3. "Do you have any upcoming races? If so, what's the race, when is it, and what's your goal time?"
   - Collect as many races as they mention.

4. "Which days are you typically available to run, and roughly what time of day?"

5. "Any injuries or physical limitations I should know about?"

6. "Any dietary restrictions? For example, gluten-free, dairy-free, vegetarian?"

7. "How much detail do you want in coaching responses — brief and scannable, balanced, or comprehensive?"
   - Map to BRIEF / STANDARD / DETAILED

**Write the athlete files:**

Write `data/athlete/goals.md`:
```markdown
# Training Goals

## Primary Goal
[Derived from race goal or stated objective]

## Upcoming Races
[List from question 3]
```

Write `data/athlete/training_preferences.md`:
```markdown
# Training Preferences

## Schedule
- Available days: [from question 4]
- Preferred time: [from question 4]

## Dietary Requirements
[from question 6, or "None noted"]
```

Write `data/athlete/upcoming_races.md`:
```markdown
# Upcoming Races

[For each race:]
## [Race name] — [Date]
- Distance: [distance]
- Goal time: [time]
- Priority: A-Race
```

Write `data/athlete/communication_preferences.md`:
```markdown
# Current Mode: [BRIEF / STANDARD / DETAILED]

[One line description of what that means]
```

Write `data/athlete/current_training_status.md`:
```markdown
# Current Training Status

## VDOT
[Calculated value, or "Not yet determined — needs race result"]

## Training Paces
[Paces from VDOT calculator, or "TBD"]

## Current Phase
Base building
```

Write `data/athlete/training_history.md`:
```markdown
# Training History

## Injuries / Limitations
[from question 5, or "None reported"]
```

Confirm: "Profile saved. Here's a summary of what I've got for you: [brief recap]"

---

## Phase 4: Discord Bot Setup (Optional)

Ask: "Want to set up the Discord bot? It sends you a daily training report each morning and lets you check your workouts and ask questions from your phone. It takes about 5 minutes to configure."

**If no:** Say "No problem — you can always run @onboarding-wizard later to set it up." Skip to Phase 5.

**If yes, walk through these steps:**

**Step 1 — Create the bot application:**
Say: "Go to https://discord.com/developers/applications in your browser and click 'New Application'. Give it any name, like 'Running Coach'. Then go to the 'Bot' section in the left sidebar and click 'Add Bot'. Under the Token section, click 'Reset Token' and copy the token. Paste it here when you have it."

When they paste the token, write it:
```bash
mkdir -p config
echo "DISCORD_BOT_TOKEN=<token>" > config/discord.env
```

**Step 2 — Invite the bot to your server:**
Say: "Still in the developer portal, go to 'OAuth2' → 'URL Generator'. Check 'bot' under Scopes, then check 'Send Messages', 'Read Message History', and 'Use Slash Commands' under Bot Permissions. Copy the generated URL and open it in your browser to invite the bot to your server."

**Step 3 — Get channel IDs:**
Say: "In Discord, go to Settings → Advanced and turn on 'Developer Mode'. Then right-click the channel you want to use for coaching messages and click 'Copy Channel ID'. Paste it here."

When they paste the channel ID, append to config:
```bash
echo "COACH_CHANNEL_ID=<id>" >> config/discord.env
```

Ask for the morning report channel ID separately if they want reports in a different channel.

**Step 4 — Install and start the service:**
```bash
sudo systemctl enable running-coach-bot
sudo systemctl start running-coach-bot
```

Verify:
```bash
sudo systemctl status running-coach-bot
```

If the service fails, check logs:
```bash
journalctl -u running-coach-bot -n 20
```

**Step 5 — Test:**
Say: "Try typing `/report` in your Discord coach channel. You should get a response within 30 seconds."

---

## Phase 5: Final Status Board

Run:
```bash
python3 bin/check_setup.py
```

Show the human-readable output. For any remaining ❌ items, explain what they mean and how to fix them later. ⚠️ items are optional.

---

## Phase 6: Plan Offer

Say: "You're all set up. Want me to generate your first training plan now? I'll create a macro plan for the next training block and schedule your first week."

- If yes: invoke `@vdot-running-coach` and ask it to generate an initial macro plan based on the athlete context files just created.
- If no: say "Whenever you're ready, just ask me to generate your training plan or use `/coach_plan` in Discord."

---

## Re-run Behavior

If the user runs @onboarding-wizard after partial or full setup, check_setup.py will show what's already complete. Skip phases whose checks pass. Only work on what's missing or needs updating.
```

**Step 2: Verify the file was written correctly**

Read back `.claude/agents/onboarding-wizard.md` and confirm the frontmatter and phase structure look right.

**Step 3: Commit**

```bash
git add .claude/agents/onboarding-wizard.md
git commit -m "feat(onboarding): add onboarding-wizard agent"
```

---

### Task 4: End-to-end smoke test

**Goal:** Verify the full detection → prompt → wizard flow works as intended.

**Step 1: Simulate a fresh environment**

Temporarily rename `data/athlete/goals.md` if it exists:
```bash
mv data/athlete/goals.md data/athlete/goals.md.bak 2>/dev/null || true
```

**Step 2: Test check_setup.py detects onboarding needed**

```bash
python3 bin/check_setup.py --json | python3 -c "import json,sys; d=json.load(sys.stdin); print('onboarding_needed:', d['onboarding_needed'])"
```

Expected output: `onboarding_needed: True`

**Step 3: Test human-readable output**

```bash
python3 bin/check_setup.py
```

Expected: checklist with ❌ for athlete_files and health_cache, message about onboarding needed.

**Step 4: Restore**

```bash
mv data/athlete/goals.md.bak data/athlete/goals.md 2>/dev/null || true
```

**Step 5: Run full test suite to confirm nothing broken**

```bash
python -m pytest tests/ -v --tb=short -q
```

Expected: existing tests still pass. New check_setup tests pass.

**Step 6: Commit if any fixups needed**

```bash
git add -p
git commit -m "fix(onboarding): smoke test fixups"
```

---

### Task 5: Update QUICKSTART.md

**Files:**
- Modify: `docs/QUICKSTART.md`

**Step 1: Read the current Next Steps section**

Find the "Next Steps" section at the bottom.

**Step 2: Replace manual steps with onboarding wizard reference**

Replace the current "Next Steps" numbered list with:

```markdown
## Next Steps

The easiest way to get started is the onboarding wizard built into Claude Code:

1. Open this repository in [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
2. Claude will detect it's a fresh setup and ask if you want to run the wizard
3. Say **yes** — the wizard covers Garmin auth, your athlete profile, and optional Discord setup

If you prefer to set things up manually, the sections below cover each step individually.
```

**Step 3: Verify the file reads correctly**

Skim the updated QUICKSTART.md to make sure the flow makes sense.

**Step 4: Commit**

```bash
git add docs/QUICKSTART.md
git commit -m "docs(onboarding): update QUICKSTART to lead with wizard"
```
