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

Say: "I need to connect to your Garmin account to pull your training data. There are two ways to do this — I'll recommend the more reliable one first."

**Recommended: Token-based auth (more reliable for automated sync)**

Run:
```bash
python3 bin/generate_garmin_tokens.py
```

This opens a browser prompt. Walk the user through logging in. Once complete, test:
```bash
python3 src/garmin_token_auth.py --test
```

If they prefer the simpler option or if token generation fails:

**Alternative: Password-based auth**

Ask for email, then password. Write them to `~/.bashrc`:
```bash
echo 'export GARMIN_EMAIL=<email>' >> ~/.bashrc
echo 'export GARMIN_PASSWORD=<password>' >> ~/.bashrc
source ~/.bashrc
```

Test:
```bash
python3 src/garmin_token_auth.py --test
```

If this fails with a 403 error, fall back to token-based auth above.

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
   - If yes: calculate VDOT using `python3 src/vdot_calculator.py` or the VDOT API. Tell them their VDOT and easy, tempo, and interval paces.
   - If no: estimate from Garmin data if available, or ask for a recent long run pace to estimate.

3. "Do you have any upcoming races? If so, what's the race, when is it, and what's your goal time?"
   - Collect as many races as they mention.

4. "Which days are you typically available to run, and roughly what time of day?"

5. "Any injuries or physical limitations I should know about?"

6. "Any dietary restrictions? For example, gluten-free, dairy-free, vegetarian?"

7. "How much detail do you want in coaching responses — brief and scannable, balanced, or comprehensive?"
   - Map to BRIEF / STANDARD / DETAILED

**Write the athlete files after collecting all answers:**

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

**If yes, walk through these steps one at a time:**

**Step 1 — Create the bot application:**
Say: "Go to https://discord.com/developers/applications in your browser and click 'New Application'. Give it any name, like 'Running Coach'. Then go to the 'Bot' section in the left sidebar and click 'Add Bot'. Under the Token section, click 'Reset Token' and copy the token. Paste it here when you have it."

When they paste the token, write it:
```bash
mkdir -p config
echo "DISCORD_BOT_TOKEN=<token>" > config/discord_bot.env
```

**Step 2 — Invite the bot to your server:**
Say: "Still in the developer portal, go to 'OAuth2' → 'URL Generator'. Check 'bot' under Scopes, then check 'Send Messages', 'Read Message History', and 'Use Slash Commands' under Bot Permissions. Copy the generated URL and open it in your browser to invite the bot to your server."

**Step 3 — Get channel IDs:**
Say: "In Discord, go to Settings → Advanced and turn on 'Developer Mode'. Then right-click the channel you want to use for coaching messages and click 'Copy Channel ID'. Paste it here."

When they paste the channel ID, append to config:
```bash
echo "COACH_CHANNEL_ID=<id>" >> config/discord_bot.env
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

Show the human-readable output. For any remaining ❌ items, explain what they mean and how to fix them later.

---

## Phase 6: Plan Offer

Say: "You're all set up. Want me to generate your first training plan now? I'll create a macro plan for the next training block and schedule your first week."

- If yes: invoke `@vdot-running-coach` and ask it to generate an initial macro plan based on the athlete context files just created.
- If no: say "Whenever you're ready, just ask me to generate your training plan or use `/coach_plan` in Discord."

---

## Re-run Behavior

If invoked after partial or full setup, check_setup.py will show what's already complete. Skip phases whose checks pass. Only work on what's missing or needs updating.
