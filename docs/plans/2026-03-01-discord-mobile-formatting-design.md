# Discord Mobile Formatting — Design Document

**Date:** 2026-03-01
**Status:** Approved
**Scope:** `src/discord_bot.py` only — no schema or data changes

---

## Problem

The Discord bot is primarily used on Android (Google Pixel 9). Current responses have three mobile-hostile patterns:

1. **Inline fields** — side-by-side columns collapse unpredictably on mobile
2. **Code-block tables** — force horizontal scrolling, unreadable on small screens
3. **Long embed descriptions** — up to 3900 chars per embed creates walls of text that are hard to scan

---

## Approach: Fix Embeds, Keep Structure (Option A)

Keep Discord embeds as the primary response format. Fix the content patterns inside them. No change to plain-text responses (check-ins, VDOT alerts, weekly synthesis are already conversational and mobile-friendly).

---

## Core Rules (apply universally)

1. **No inline fields.** All `add_field(..., inline=True)` → `inline=False`. Fields stack vertically.
2. **No tables in code blocks.** Replace `| col | col |` tables with bullet lists.
3. **Description cap: 1200 chars** (was 3900–4000). Long content splits across multiple embeds.
4. **Emoji anchors as section headers.** Each logical section starts with a consistent emoji so the eye can jump without reading everything.

---

## Command-by-Command Changes

### `/status`
- **Before:** 2–3 inline fields per row (Sleep | Battery | Readiness side-by-side)
- **After:** All non-inline. Use `bullet_fields()` helper to format metrics as a bullet string in the embed description.
- **Example output:**
  ```
  😴 Sleep: 78/100 · 7h 12m
  🔋 Battery: 62%
  🎯 Readiness: 71/100
  ❤️ RHR: 46 bpm
  ```

### `/coach_schedule`
- **Before:** Markdown table in a code block (worst mobile offender)
- **After:** One non-inline field per day. `name="Mon Mar 2"`, `value="🏃 Easy 45 min E"`.
- Day cards stack vertically — fully readable on any screen width.

### `/report` (morning report)
- **Before:** Single embed, ~3900 chars of prose
- **After:** Three embeds sent together:
  1. Key metrics as emoji bullets (sleep, battery, HRV, readiness)
  2. Workout recommendation (what to do and why in ≤1200 chars)
  3. Rationale / notes (optional, only if content remains)

### `/coach_plan`
- **Before:** Single embed dumping full plan output (~3900 chars)
- **After:** Two embeds:
  1. Week summary (phase, target volume, quality session target)
  2. Day-by-day schedule as bullets

### `/ask`
- **Before:** Single embed up to 4000 chars
- **After:** 1200-char cap per embed; `split_embeds()` generates sequential embeds if answer is longer

### `/workout`
- Already uses multiple embeds per workout section
- Only change: audit for any remaining `inline=True` and remove them

### Unchanged
- Check-in messages (plain text, conversational — already mobile-friendly)
- VDOT alerts (plain text)
- Weekly synthesis (plain text)
- Observability test results (plain text)

---

## New Code: Helpers

### `MOBILE_DESC_LIMIT = 1200`
Single constant replacing scattered magic numbers (`3900`, `4000`, `1800`). One place to tune.

### `split_embeds(content, title, color, chunk_size=MOBILE_DESC_LIMIT) → list[discord.Embed]`
- Splits `content` into chunks ≤ `chunk_size` chars
- Split priority: paragraph breaks (`\n\n`) first, sentence breaks second, hard cut last
- Returns a list of `discord.Embed` objects, each with the same `color`; only the first has `title`
- Callers: `await interaction.followup.send(embeds=split_embeds(...))`

### `bullet_fields(pairs) → str`
- Input: list of `(emoji, label, value)` tuples
- Output: newline-joined string — e.g. `"😴 Sleep: 78/100 · 7h 12m\n🔋 Battery: 62%"`
- Replaces `embed.add_field(..., inline=True)` calls for metrics displays

---

## Implementation Scope

- **File:** `src/discord_bot.py` (single file, all changes)
- **No changes to:** data files, schemas, other source files, Discord slash command definitions
- **Risk:** Low — formatting only, no logic changes. Each command is independently testable by running it in Discord.

---

## Success Criteria

- No `inline=True` anywhere in the file
- No markdown tables (`|`) in any embed description or field value
- No single embed description exceeds 1200 chars
- `/coach_schedule` displays as day cards (one field per day)
- `/report` sends as 2–3 smaller embeds instead of one large one
