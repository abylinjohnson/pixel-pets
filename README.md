# 🐱 Pixel Pets

A local desktop **focus companion**. A pixel-art cat named **Nila** lives on your
screen, watches how you work, and gently nudges you back on track when you drift —
backed by a clean web dashboard for goals, focus sessions, reminders, and analytics.

Everything runs **on your own machine**. Activity stays in a local SQLite database;
the only thing that ever leaves your computer is a tiny JSON payload sent to the
OpenAI API (and only if you provide a key).

---

## ✨ Features

- **Desktop pet (Nila)** — a transparent, always-on-top, draggable pixel cat that
  animates based on what you're doing (focus, distraction, idle, sleep) and talks
  to you through a retro **pixel-art speech bubble**, with meow/purr sound effects.
- **Focus sessions** — set a task, a goal and a duration. While a session runs, the
  cat checks whether your active window/tab is actually relevant to your goal.
- **Smart distraction detection** — combines fast keyword rules with an LLM that
  judges each window against *your specific task and goal*. It reads the active
  **browser URL** (not just the title) for much better accuracy, and only nudges
  when something is clearly off-task.
- **Reminders** — phone-alarm-style reminders: one-time (date + time) or recurring
  (days of the week + time). The cat delivers them with a meow and a speech bubble.
- **Analytics dashboard** — daily focus score, productive vs. non-productive time,
  per-window breakdown, a session timeline, and an AI-written session summary.
- **Event logs** — a live view of the raw tracker events feeding the system.
- **Cross-platform** — runs on **Windows, macOS and Linux** (see notes below).

---

## 🖥️ How it works

```
┌────────────┐     events      ┌──────────────┐    decisions    ┌──────────────┐
│  Trackers  │ ──────────────► │ PetAiController │ ────────────► │  Desktop Pet │
│ window/idle│                 │  (rules + LLM)  │   animations  │  (pygame)    │
│ /camera    │                 └──────────────┘   + speech       └──────────────┘
└─────┬──────┘                         │
      │ store                          │ summaries / nudges
      ▼                                ▼
┌────────────┐                  ┌──────────────┐
│   SQLite   │ ◄──────────────► │  Flask web   │  http://127.0.0.1:5000
│ pixel_pet.db│   analytics     │  dashboard   │
└────────────┘                  └──────────────┘
```

- **Trackers** poll once per second for the active window (+ browser URL), idle
  time, and webcam face presence, emitting `ActivityEvent`s.
- **EventCapture** fans those events out to listeners: the database, the console,
  and the AI controller.
- **PetAiController** decides how the cat should react — using keyword rules first,
  then an LLM for the nuanced "is this relevant to my goal?" calls.
- **Flask app** serves the dashboard and the reminders/focus/analytics APIs.

---

## 📦 Requirements

- **Python 3.10+** (developed on 3.13)
- An **OpenAI API key** *(optional)* — without it, the app still runs fully on
  deterministic keyword rules; you just lose the smart, context-aware judgments
  and AI summaries.
- A **webcam** *(optional)* — used only for present/absent detection. If absent or
  unavailable, that tracker disables itself gracefully.

### Platform notes

| Platform | Active window | Idle time | URL read | Transparent overlay |
|----------|---------------|-----------|----------|---------------------|
| **Windows** | `pywin32` | `pywin32` | `uiautomation` | Per-pixel (colour-key) |
| **macOS**   | `osascript` | `ioreg` | AppleScript | Borderless on-top card |
| **Linux**   | `xdotool` → `xprop` | `xprintidle` | — | Borderless on-top card |

- **Windows** dependencies (`pywin32`, `uiautomation`) install automatically.
- **Linux** needs system tools for full functionality:
  ```bash
  sudo apt install xdotool xprintidle
  ```
- **macOS** uses built-in tools (`osascript`, `ioreg`) — nothing extra to install.
  You may need to grant **Accessibility** and **Screen Recording** permissions for
  window/URL detection.

> True per-pixel desktop transparency (the cat floating with no visible box) is
> Windows-only today. On macOS/Linux the cat shows inside a small borderless,
> always-on-top card.

---

## 🚀 Setup

```bash
# 1. Clone and enter the project
cd pixel-pets

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your OpenAI key (optional but recommended)
#    Create a file named .env in the project root:
echo "OPENAI_API_KEY=sk-..." >> .env
echo "OPENAI_MODEL=gpt-4.1-mini" >> .env
```

### Configuration (environment variables)

Loaded from `.env` or `src/pixel_pet/.env` (first found wins). `.env` is
git-ignored, so your key never gets committed:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(none)* | Enables all AI features. Without it, rules-only. |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Model used for classification, nudges, summaries. |
| `OPENAI_TIMEOUT` | `6` | Per-request timeout (seconds) so AI can't stall the loop. |
| `PIXEL_PET_KEY` | `nila` | Which pet profile to load. |

---

## ▶️ Running

**Full app** (desktop pet + activity tracking + dashboard):

```bash
python main.py
```

This launches the floating cat, starts the trackers, and serves the dashboard at
**http://127.0.0.1:5000**. Press `Esc` on the cat window (or stop the process) to quit.

**Dashboard only** (no pet / no tracking):

```bash
python dashboard.py
```

---

## 🗂️ Project structure

```
pixel-pets/
├── main.py                       # Entry point: pet + trackers + dashboard
├── dashboard.py                  # Dashboard-only entry point
├── requirements.txt
├── assets/nila/                  # Pixel-art animation frames + audio
└── src/pixel_pet/
    ├── activity/                 # EventCapture + ActivityEvent definitions
    ├── ai/                       # PetAiController (rules + LLM decisions)
    ├── handlers/                 # PetBehaviorHandler (maps behaviours → animations)
    ├── pet/                      # Desktop pet window + pixel speech bubble (pygame)
    ├── pets/                     # Pet profiles, actions, registry (Nila)
    ├── platform_support/         # Cross-platform: active window, idle, URL, overlay
    ├── storage/                  # SQLite database + analytics
    ├── trackers/                 # Active-window, idle, camera-presence trackers
    ├── web/                      # Flask app, templates, static assets
    ├── config.py                 # .env loading
    └── state.py                  # Thread-safe focus-session state
```

---

## 🧠 AI & privacy

- **What the AI does:** classifies whether your current window/tab is relevant to
  your focus goal, writes short friendly nudges, and generates a 2–3 sentence
  session summary.
- **Model:** OpenAI `gpt-4.1-mini` (configurable) — chosen for low latency/cost
  since decisions run inline on the tracking loop.
- **Data:** activity is stored **locally** in `data/pixel_pet.db`. Only a minimal
  payload (task, goal, window title, URL, process name, aggregate stats) is sent to
  the OpenAI API, and only when a key is configured.
- **Guardrails:** keyword fallbacks when the API is unavailable, strict JSON parsing
  with safe defaults, request timeouts, response caching, per-page cooldowns, a bias
  toward *not* interrupting on ambiguous data, and self-exclusion (the app never
  flags its own windows).
- **Face detection** uses a local OpenCV Haar cascade — classical computer vision,
  not generative AI. No images are stored; only a present/absent boolean.

---

## 🔧 Tech stack

Python · Flask · pygame · SQLite · OpenCV · OpenAI API · vanilla JS/CSS frontend

---

## 📝 Notes

- Day boundaries for analytics/goals are computed in **IST (UTC+5:30)**.
- The cat re-pins itself on top once per second so it stays visible above other
  windows (without stealing keyboard focus).
- All activity data is local and user-deletable — just remove `data/pixel_pet.db`.
