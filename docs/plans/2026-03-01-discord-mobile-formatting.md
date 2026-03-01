# Discord Mobile Formatting Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make all Discord bot responses scannable on a small phone screen by removing inline fields, replacing code-block tables with bullets, and splitting long embed descriptions across multiple embeds.

**Architecture:** All changes are in `src/discord_bot.py`. Two new helper functions (`split_embeds`, `bullet_fields`) and one constant (`MOBILE_DESC_LIMIT = 1200`) replace the scattered `clamp(text, 3900)` pattern. No changes to schemas, data files, or other source files.

**Tech Stack:** discord.py, pytest

---

## Task 1: Add MOBILE_DESC_LIMIT constant and two helper functions

**Files:**
- Modify: `src/discord_bot.py:108-111` (after `clamp()`)

**Step 1: Open the file and find line 108**

The existing helpers are:
```python
def clamp(text: str, n: int) -> str:
    """Truncate text to n chars, adding ellipsis if cut."""
    return text if len(text) <= n else text[:n - 3] + "..."
```

**Step 2: Add the constant and two helpers immediately after `clamp()`**

Insert this block starting at line 112 (after the `clamp` function):

```python
# Mobile-safe embed description cap. Discord allows 4096 chars per embed
# description, but walls of text are unreadable on a phone screen.
MOBILE_DESC_LIMIT = 1200


def split_embeds(
    content: str,
    title: str,
    color: discord.Color,
    chunk_size: int = MOBILE_DESC_LIMIT,
) -> list:
    """
    Split long content into a list of Discord Embeds, each under chunk_size chars.

    Only the first embed gets the title. All share the same color.
    Splits on paragraph breaks (\\n\\n) first, sentence breaks second, hard cut last.
    Returns at least one embed even if content is empty.
    """
    content = content.strip()
    if not content:
        return [discord.Embed(title=title, description="(no content)", color=color)]

    # Build chunks
    chunks: list[str] = []
    current = ""
    for para in content.split("\n\n"):
        if len(para) > chunk_size:
            # Para itself is too long — split at sentence boundaries
            for sentence in para.split(". "):
                piece = sentence + ". "
                if len(current) + len(piece) > chunk_size:
                    if current:
                        chunks.append(current.rstrip())
                    current = piece
                else:
                    current += piece
        else:
            candidate = (current + "\n\n" + para) if current else para
            if len(candidate) > chunk_size:
                chunks.append(current.rstrip())
                current = para
            else:
                current = candidate
    if current:
        chunks.append(current.rstrip())

    if not chunks:
        chunks = [clamp(content, chunk_size)]

    embeds = []
    for i, chunk in enumerate(chunks):
        embed = discord.Embed(
            title=title if i == 0 else "",
            description=chunk,
            color=color,
        )
        if i == 0:
            embed.timestamp = datetime.now()
        embeds.append(embed)
    return embeds


def bullet_fields(pairs: list) -> str:
    """
    Format a list of (emoji, label, value) tuples as a mobile-friendly bullet string.

    Example:
        bullet_fields([("😴", "Sleep", "78/100"), ("🔋", "Battery", "62%")])
        → "😴 Sleep: 78/100\\n🔋 Battery: 62%"

    Skips pairs where value is "N/A" or None (caller passes "N/A" for missing data).
    """
    lines = []
    for emoji, label, value in pairs:
        if value is not None and str(value) != "N/A":
            lines.append(f"{emoji} {label}: {value}")
        else:
            lines.append(f"{emoji} {label}: —")
    return "\n".join(lines)
```

**Step 3: Verify the file is syntactically correct**

```bash
cd /home/coach/running-coach && python3 -c "import src.discord_bot" 2>&1 | head -20
```

Expected: no output (no import errors). The bot won't fully initialize without env vars but syntax errors will show.

**Step 4: Commit**

```bash
git add src/discord_bot.py
git commit -m "feat(discord): add MOBILE_DESC_LIMIT, split_embeds, bullet_fields helpers"
```

---

## Task 2: Write unit tests for the new helpers

**Files:**
- Create: `tests/test_discord_formatting.py`

**Step 1: Write the test file**

```python
"""Unit tests for Discord mobile formatting helpers."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub out discord module minimally so we can import helpers without a bot token
import types
discord_stub = types.ModuleType("discord")

class _Color:
    @staticmethod
    def blue(): return "blue"
    @staticmethod
    def green(): return "green"

class _Embed:
    def __init__(self, title="", description="", color=None, timestamp=None):
        self.title = title
        self.description = description
        self.color = color
        self.timestamp = timestamp

discord_stub.Color = _Color
discord_stub.Embed = _Embed
sys.modules["discord"] = discord_stub
sys.modules["discord.ext"] = types.ModuleType("discord.ext")
sys.modules["discord.ext.commands"] = types.ModuleType("discord.ext.commands")
sys.modules["discord.ext.tasks"] = types.ModuleType("discord.ext.tasks")
sys.modules["discord.app_commands"] = types.ModuleType("discord.app_commands")

# Now we can import the helpers
from src.discord_bot import split_embeds, bullet_fields, MOBILE_DESC_LIMIT


class TestSplitEmbeds:
    def test_short_content_returns_single_embed(self):
        embeds = split_embeds("Hello world", "Title", "blue")
        assert len(embeds) == 1
        assert embeds[0].title == "Title"
        assert embeds[0].description == "Hello world"

    def test_long_content_splits_at_paragraph_boundary(self):
        chunk = "x" * 600
        content = chunk + "\n\n" + chunk  # two 600-char paras = 1202 chars total
        embeds = split_embeds(content, "Title", "blue", chunk_size=1200)
        assert len(embeds) == 2
        assert embeds[0].title == "Title"
        assert embeds[1].title == ""  # continuation embeds have no title

    def test_only_first_embed_has_title(self):
        content = "\n\n".join(["word " * 100] * 5)
        embeds = split_embeds(content, "MyTitle", "blue", chunk_size=300)
        assert embeds[0].title == "MyTitle"
        for embed in embeds[1:]:
            assert embed.title == ""

    def test_empty_content_returns_one_embed(self):
        embeds = split_embeds("", "Title", "blue")
        assert len(embeds) == 1

    def test_each_embed_under_chunk_size(self):
        content = " ".join(["word"] * 2000)
        embeds = split_embeds(content, "T", "blue", chunk_size=500)
        for embed in embeds:
            assert len(embed.description) <= 500


class TestBulletFields:
    def test_basic_formatting(self):
        result = bullet_fields([("😴", "Sleep", "78/100"), ("🔋", "Battery", "62%")])
        assert result == "😴 Sleep: 78/100\n🔋 Battery: 62%"

    def test_na_value_shows_dash(self):
        result = bullet_fields([("❤️", "RHR", "N/A")])
        assert result == "❤️ RHR: —"

    def test_none_value_shows_dash(self):
        result = bullet_fields([("📈", "HRV", None)])
        assert result == "📈 HRV: —"

    def test_empty_list(self):
        result = bullet_fields([])
        assert result == ""
```

**Step 2: Run the tests**

```bash
cd /home/coach/running-coach && pytest tests/test_discord_formatting.py -v
```

Expected output:
```
tests/test_discord_formatting.py::TestSplitEmbeds::test_short_content_returns_single_embed PASSED
tests/test_discord_formatting.py::TestSplitEmbeds::test_long_content_splits_at_paragraph_boundary PASSED
tests/test_discord_formatting.py::TestSplitEmbeds::test_only_first_embed_has_title PASSED
tests/test_discord_formatting.py::TestSplitEmbeds::test_empty_content_returns_one_embed PASSED
tests/test_discord_formatting.py::TestSplitEmbeds::test_each_embed_under_chunk_size PASSED
tests/test_discord_formatting.py::TestBulletFields::test_basic_formatting PASSED
tests/test_discord_formatting.py::TestBulletFields::test_na_value_shows_dash PASSED
tests/test_discord_formatting.py::TestBulletFields::test_none_value_shows_dash PASSED
tests/test_discord_formatting.py::TestBulletFields::test_empty_list PASSED
9 passed
```

**Step 3: Commit**

```bash
git add tests/test_discord_formatting.py
git commit -m "test(discord): unit tests for split_embeds and bullet_fields helpers"
```

---

## Task 3: Fix `/status` — replace 5 inline fields with bullet_fields()

**Files:**
- Modify: `src/discord_bot.py:653-665`

**Context — current code (lines 653–665):**
```python
embed = discord.Embed(
    title=f"{status_emoji} Recovery Status",
    color=color,
    timestamp=datetime.now()
)

embed.add_field(name="😴 Sleep", value=f"{sleep_score}/100" if sleep_score != "N/A" else "N/A", inline=True)
embed.add_field(name="🔋 Body Battery", value=f"{body_battery}%" if body_battery != "N/A" else "N/A", inline=True)
embed.add_field(name="❤️ RHR", value=f"{rhr} bpm" if rhr != "N/A" else "N/A", inline=True)
embed.add_field(name="📈 HRV", value=f"{hrv} ms" if hrv != "N/A" else "N/A", inline=True)
embed.add_field(name="🎯 Readiness", value=f"{readiness_score}/100 ({readiness_level})" if readiness_score != "N/A" else "N/A", inline=True)

await interaction.followup.send(embed=embed)
```

**Step 1: Replace the embed block**

Replace those 10 lines with:

```python
sleep_val = f"{sleep_score}/100" if sleep_score != "N/A" else "N/A"
battery_val = f"{body_battery}%" if body_battery != "N/A" else "N/A"
rhr_val = f"{rhr} bpm" if rhr != "N/A" else "N/A"
hrv_val = f"{hrv} ms{' · ' + hrv_status if hrv_status else ''}" if hrv != "N/A" else "N/A"
readiness_val = f"{readiness_score}/100 ({readiness_level})" if readiness_score != "N/A" else "N/A"

description = bullet_fields([
    ("😴", "Sleep", sleep_val),
    ("🔋", "Battery", battery_val),
    ("❤️", "RHR", rhr_val),
    ("📈", "HRV", hrv_val),
    ("🎯", "Readiness", readiness_val),
])
embed = discord.Embed(
    title=f"{status_emoji} Recovery Status",
    description=description,
    color=color,
    timestamp=datetime.now(),
)
await interaction.followup.send(embed=embed)
```

**Step 2: Syntax check**

```bash
cd /home/coach/running-coach && python3 -c "import src.discord_bot" 2>&1 | head -5
```

**Step 3: Commit**

```bash
git add src/discord_bot.py
git commit -m "fix(discord): replace inline status fields with mobile-friendly bullet list"
```

---

## Task 4: Fix `/report` — split 4000-char blob into multiple embeds

**Files:**
- Modify: `src/discord_bot.py:470-478`

**Context — current code (lines 470–478):**
```python
report = '\n'.join(filtered_lines).strip()[:4000]  # Discord embed limit

embed = discord.Embed(
    title="🌅 Morning Training Report",
    description=report,
    color=discord.Color.blue(),
    timestamp=datetime.now()
)
await interaction.followup.send(embed=embed)
```

**Step 1: Replace with split_embeds()**

```python
report = '\n'.join(filtered_lines).strip()

embeds = split_embeds(report, "🌅 Morning Training Report", discord.Color.blue())
await interaction.followup.send(embeds=embeds[:10])
```

**Step 2: Syntax check**

```bash
cd /home/coach/running-coach && python3 -c "import src.discord_bot" 2>&1 | head -5
```

**Step 3: Commit**

```bash
git add src/discord_bot.py
git commit -m "fix(discord): split /report into paginated embeds (mobile-friendly)"
```

---

## Task 5: Fix `/workout` — remove inline=True from Duration fields

**Files:**
- Modify: `src/discord_bot.py:540` and `src/discord_bot.py:595`

**Context — line 540:**
```python
embed.add_field(name="Duration", value=f"{dur} min", inline=True)
```

**Context — line 595:**
```python
embed.add_field(name="Duration", value=f"{w['duration_min']} min", inline=True)
```

Also check `src/discord_bot.py:549` — Structure field is already `inline=False`, leave it.

**Step 1: Change both inline=True to inline=False**

Line 540:
```python
embed.add_field(name="Duration", value=f"{dur} min", inline=False)
```

Line 595:
```python
embed.add_field(name="Duration", value=f"{w['duration_min']} min", inline=False)
```

**Step 2: Grep to confirm no remaining inline=True in workout section**

```bash
grep -n "inline=True" /home/coach/running-coach/src/discord_bot.py
```

Expected: no output (all inline=True should now be gone).

**Step 3: Syntax check**

```bash
cd /home/coach/running-coach && python3 -c "import src.discord_bot" 2>&1 | head -5
```

**Step 4: Commit**

```bash
git add src/discord_bot.py
git commit -m "fix(discord): remove all inline=True fields from /workout response"
```

---

## Task 6: Fix `/ask` — split AI responses with split_embeds()

**Files:**
- Modify: `src/discord_bot.py:806-825`

**Context — current code (lines 806–825):**
```python
# Truncate if needed
response = response[:4000] if len(response) > 4000 else response

# Set color and footer based on provider
if provider == 'claude':
    color = discord.Color.purple()
    footer_text = f"Powered by Claude • {question[:80]}"
else:  # gemini
    color = discord.Color.blue()
    footer_text = f"Powered by Gemini (Claude unavailable) • {question[:60]}"

embed = discord.Embed(
    title="🤖 Coach Response",
    description=response,
    color=color,
    timestamp=datetime.now()
)
embed.set_footer(text=footer_text)

await interaction.followup.send(embed=embed)
```

**Step 1: Replace with split_embeds()**

```python
if provider == 'claude':
    color = discord.Color.purple()
    footer_text = f"Powered by Claude • {question[:80]}"
else:  # gemini
    color = discord.Color.blue()
    footer_text = f"Powered by Gemini (Claude unavailable) • {question[:60]}"

embeds = split_embeds(response or "(no response)", "🤖 Coach Response", color)
embeds[0].set_footer(text=footer_text)
await interaction.followup.send(embeds=embeds[:10])
```

**Step 2: Syntax check**

```bash
cd /home/coach/running-coach && python3 -c "import src.discord_bot" 2>&1 | head -5
```

**Step 3: Commit**

```bash
git add src/discord_bot.py
git commit -m "fix(discord): split /ask AI responses into paginated mobile embeds"
```

---

## Task 7: Fix `/coach_plan` — split plan + export into two separate embeds

**Files:**
- Modify: `src/discord_bot.py:921-963`

**Context — current code (lines 921–963):** The plan command:
1. Runs `coach plan --week`
2. Shows a progress embed via `edit_original_response`
3. Runs `coach export-garmin --live`
4. Shows final result as a single embed containing both plan + export output concatenated

**Step 1: Replace the final embed block (success path, lines 941–963)**

Current:
```python
if exp_rc == 0:
    embed = discord.Embed(
        title="✓ Plan Generated + Garmin Updated",
        description=f"{plan_msg}\n\n---\n{export_msg}",
        color=discord.Color.blue(),
        timestamp=datetime.now(),
    )
else:
    embed = discord.Embed(
        title="⚠ Plan Generated, Garmin Publish Failed",
        description=f"{plan_msg}\n\n---\n{export_msg}",
        color=discord.Color.orange(),
        timestamp=datetime.now(),
    )
...
await interaction.edit_original_response(embed=embed)
```

Replace with:
```python
plan_embeds = split_embeds(
    plan_msg, "✓ Plan Generated", discord.Color.blue()
)
if exp_rc == 0:
    export_embeds = split_embeds(
        export_msg, "📤 Garmin Updated", discord.Color.green()
    )
else:
    export_embeds = split_embeds(
        export_msg, "⚠ Garmin Publish Failed", discord.Color.orange()
    )

# Edit the "thinking" indicator away, then send the real content
await interaction.edit_original_response(
    embed=discord.Embed(title="✓ Done", color=discord.Color.green(), timestamp=datetime.now())
)
all_embeds = (plan_embeds + export_embeds)[:10]
await interaction.followup.send(embeds=all_embeds)
```

Also update the failure path (lines 955–963):

Current:
```python
else:
    msg = stderr.strip() or stdout.strip() or "Unknown error"
    embed = discord.Embed(
        title="❌ Plan Generation Failed",
        description=clamp(msg, 1800),
        color=discord.Color.red(),
        timestamp=datetime.now(),
    )
await interaction.edit_original_response(embed=embed)
```

Replace with:
```python
else:
    msg = stderr.strip() or stdout.strip() or "Unknown error"
    await interaction.edit_original_response(
        embed=discord.Embed(
            title="❌ Plan Generation Failed",
            description=clamp(msg, MOBILE_DESC_LIMIT),
            color=discord.Color.red(),
            timestamp=datetime.now(),
        )
    )
    return
```

Note: add `return` after the failure path so the success-path `followup.send` is not reached on failure.

**Step 2: Syntax check**

```bash
cd /home/coach/running-coach && python3 -c "import src.discord_bot" 2>&1 | head -5
```

**Step 3: Commit**

```bash
git add src/discord_bot.py
git commit -m "fix(discord): split /coach_plan into separate plan + export embeds"
```

---

## Task 8: Fix remaining bulk commands — replace clamp(3900) with split_embeds()

These six commands all follow the identical pattern: `description=clamp(msg, 3900)`. Each gets the same treatment.

**Files:**
- Modify: `src/discord_bot.py` — lines 879, 902, 987, 1011, 1027, 1044

**Commands and their current lines:**

| Command | Success title | Success color | Current line |
|---|---|---|---|
| `/coach_today` | `"📋 Today's Workout"` | `green` | 877–882 |
| `/coach_sync` | `"✓ Coach Sync Complete"` | `green` | 900–905 |
| `/coach_macro` | `"📊 Macro Plan"` | `blue` | 985–990 |
| `/coach_export` | `"📤 Garmin Export Preview"` | `green` | 1008–1014 |
| `/coach_status` | `"🔧 Agent Status"` | `green` | 1025–1030 |
| `/coach_memory` | `f"🔍 Memory: {clamp(query, 60)}"` | `blue` | 1042–1047 |

**Step 1: For each command, replace the success embed block**

Pattern — replace:
```python
embed = discord.Embed(
    title="TITLE",
    description=clamp(msg, 3900),
    color=discord.Color.COLOR(),
    timestamp=datetime.now(),
)
await interaction.followup.send(embed=embed)
```

With:
```python
await interaction.followup.send(
    embeds=split_embeds(msg, "TITLE", discord.Color.COLOR())[:10]
)
```

Apply this to all six commands. Error/failure branches in each command use `clamp(msg, 1800)` — change those caps to `MOBILE_DESC_LIMIT`:
```python
description=clamp(msg, MOBILE_DESC_LIMIT),
```

**Step 2: After all six edits, grep to verify no remaining clamp(3900) or [:4000]**

```bash
grep -n "3900\|4000\|3500" /home/coach/running-coach/src/discord_bot.py
```

Expected: no output.

**Step 3: Full syntax check**

```bash
cd /home/coach/running-coach && python3 -c "import src.discord_bot" 2>&1 | head -5
```

**Step 4: Run all tests to confirm nothing broken**

```bash
cd /home/coach/running-coach && pytest tests/test_discord_formatting.py -v
```

Expected: 9 passed.

**Step 5: Commit**

```bash
git add src/discord_bot.py
git commit -m "fix(discord): replace all clamp(3900) with split_embeds for mobile readability"
```

---

## Task 9: Restart bot and do a quick live smoke test

**Step 1: Restart the bot service**

```bash
sudo systemctl restart running-coach-bot
```

**Step 2: Check it came up clean**

```bash
sudo systemctl status running-coach-bot | head -20
```

Expected: `Active: active (running)`

**Step 3: Tail logs for 10 seconds to catch startup errors**

```bash
journalctl -u running-coach-bot -f --since "1 minute ago" | head -30
```

Expected: no ERROR or CRITICAL lines.

**Step 4: In Discord, run each command and visually confirm**

- `/status` — metrics should appear as stacked bullet rows, no side-by-side columns
- `/workout` — Duration field should be full-width, not inline
- `/report` — should arrive as 2–3 smaller embeds instead of one wall
- `/ask what day is it` — short answer in one embed; long answer splits across multiple
- `/coach_schedule` — already plain text, verify still works
- `/coach_today` — if content is long, should split into multiple embeds

**Step 5: Final commit (if any cosmetic fixes needed from smoke test)**

```bash
git add src/discord_bot.py
git commit -m "fix(discord): smoke test fixes"
```

---

## Success Criteria Checklist

- [ ] `grep -n "inline=True" src/discord_bot.py` returns nothing
- [ ] `grep -n "3900\|:4000\|3500" src/discord_bot.py` returns nothing
- [ ] `pytest tests/test_discord_formatting.py` — 9 passed
- [ ] `/status` renders as stacked bullet rows on phone
- [ ] `/report` arrives as multiple embeds (not one scroll-forever embed)
- [ ] `/coach_plan` arrives as plan embed + export embed separately
- [ ] Bot restarts cleanly with no errors
