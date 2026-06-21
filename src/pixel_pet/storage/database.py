import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "pixel_pet.db"

_IST = timezone(timedelta(hours=5, minutes=30))

NON_PRODUCTIVE_KEYWORDS = (
    "youtube",
    "netflix",
    "instagram",
    "facebook",
    "twitter",
    "x.com",
    "reddit",
    "tiktok",
    "discord",
    "game",
)


def init_db(db_path=DB_PATH):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with _connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS activity_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                payload TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_activity_events_timestamp
            ON activity_events(timestamp);

            CREATE TABLE IF NOT EXISTS daily_goals (
                goal_date TEXT PRIMARY KEY,
                goal_text TEXT NOT NULL,
                target_minutes INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS focus_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                goal TEXT NOT NULL DEFAULT '',
                planned_minutes INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                status TEXT NOT NULL DEFAULT 'planned'
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT NOT NULL,
                reminder_type TEXT NOT NULL DEFAULT 'once',
                remind_at TEXT,
                days_of_week TEXT,
                time_of_day TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                last_triggered_at TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        _migrate_focus_sessions(connection)


def _migrate_focus_sessions(connection):
    """Add columns introduced after the initial schema without dropping existing data."""
    for column, definition in [
        ("goal",       "TEXT NOT NULL DEFAULT ''"),
        ("started_at", "TEXT"),
        ("ended_at",   "TEXT"),
        ("summary",    "TEXT"),
    ]:
        try:
            connection.execute(
                f"ALTER TABLE focus_sessions ADD COLUMN {column} {definition}"
            )
        except Exception:
            pass


def store_event(event, db_path=DB_PATH):
    init_db(db_path)

    with _connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO activity_events (
                event_type,
                source,
                timestamp,
                payload
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                event.event_type.value,
                event.source,
                event.timestamp.isoformat(),
                json.dumps(event.payload),
            ),
        )


def get_recent_events(limit=50, db_path=DB_PATH):
    init_db(db_path)

    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, event_type, source, timestamp, payload
            FROM activity_events
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [_event_row_to_dict(row) for row in rows]


def save_daily_goal(goal_text, target_minutes, goal_date=None, db_path=DB_PATH):
    init_db(db_path)

    now = _now_iso()
    goal_date = goal_date or _today()

    with _connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO daily_goals (
                goal_date,
                goal_text,
                target_minutes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(goal_date) DO UPDATE SET
                goal_text = excluded.goal_text,
                target_minutes = excluded.target_minutes,
                updated_at = excluded.updated_at
            """,
            (goal_date, goal_text, target_minutes, now, now),
        )

    return get_daily_goal(goal_date, db_path)


def get_daily_goal(goal_date=None, db_path=DB_PATH):
    init_db(db_path)

    goal_date = goal_date or _today()

    with _connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT goal_date, goal_text, target_minutes, created_at, updated_at
            FROM daily_goals
            WHERE goal_date = ?
            """,
            (goal_date,),
        ).fetchone()

    if not row:
        return None

    return {
        "date": row["goal_date"],
        "text": row["goal_text"],
        "target_minutes": row["target_minutes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_focus_session(task, planned_minutes, goal="", db_path=DB_PATH):
    init_db(db_path)

    created_at = _now_iso()

    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO focus_sessions (task, goal, planned_minutes, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (task, goal, planned_minutes, created_at),
        )
        session_id = cursor.lastrowid

    return {
        "id": session_id,
        "task": task,
        "goal": goal,
        "planned_minutes": planned_minutes,
        "created_at": created_at,
        "status": "planned",
    }


def start_focus_session(session_id, db_path=DB_PATH):
    init_db(db_path)
    with _connect(db_path) as connection:
        connection.execute(
            "UPDATE focus_sessions SET started_at = ?, status = 'active' WHERE id = ?",
            (_now_iso(), session_id),
        )


def end_focus_session(session_id, db_path=DB_PATH):
    init_db(db_path)
    with _connect(db_path) as connection:
        connection.execute(
            "UPDATE focus_sessions SET ended_at = ?, status = 'completed' WHERE id = ?",
            (_now_iso(), session_id),
        )


def save_session_summary(session_id, summary, db_path=DB_PATH):
    """Store the AI-generated summary for a completed session."""
    init_db(db_path)
    with _connect(db_path) as connection:
        connection.execute(
            "UPDATE focus_sessions SET summary = ? WHERE id = ?",
            (summary, session_id),
        )


def get_recent_focus_sessions(limit=10, db_path=DB_PATH):
    """Return the N most recent focus sessions, newest first."""
    init_db(db_path)
    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, task, goal, planned_minutes,
                   started_at, ended_at, created_at, status
            FROM focus_sessions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_active_focus_session(db_path=DB_PATH):
    """Return the in-progress focus session if one exists, else None."""
    init_db(db_path)
    with _connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT * FROM focus_sessions
            WHERE status = 'active'
            ORDER BY started_at DESC
            LIMIT 1
            """,
        ).fetchone()
    return dict(row) if row else None


def get_focus_session(session_id, db_path=DB_PATH):
    init_db(db_path)
    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM focus_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    return dict(row) if row else None


def get_session_analytics(session_id, db_path=DB_PATH):
    """Compute focus, distraction, and window-usage stats for a completed session."""
    session = get_focus_session(session_id, db_path)
    if not session:
        return None

    started_at = session.get("started_at")
    ended_at   = session.get("ended_at")

    empty = {
        "session": session,
        "duration_minutes": 0,
        "productive_minutes": 0,
        "nonproductive_minutes": 0,
        "focus_percentage": 0,
        "distraction_count": 0,
        "windows": [],
        "timeline": [],
    }

    if not started_at:
        return empty

    # If the session is still active (no ended_at), use now as the window edge.
    end_ts = ended_at or _now_iso()

    start_dt = datetime.fromisoformat(started_at)
    end_dt   = datetime.fromisoformat(end_ts)
    duration_minutes = max(0, round((end_dt - start_dt).total_seconds() / 60))

    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT event_type, timestamp, payload
            FROM activity_events
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
            """,
            (started_at, end_ts),
        ).fetchall()

    segments = _build_window_segments(rows)

    productive      = sum(s["minutes"] for s in segments if s["bucket"] == "productive")
    nonproductive   = sum(s["minutes"] for s in segments if s["bucket"] == "nonproductive")
    total_tracked   = productive + nonproductive
    focus_pct       = round(productive / total_tracked * 100) if total_tracked else 0
    distraction_cnt = sum(1 for s in segments if s["bucket"] == "nonproductive")

    timeline = []
    for s in segments[-30:]:
        p = s["payload"]
        timeline.append({
            "title":        p.get("title") or "Untitled",
            "process_name": p.get("process_name") or "Unknown",
            "minutes":      s["minutes"],
            "bucket":       s["bucket"],
            "started_at":   s["started_at"],
        })

    return {
        "session": {
            "id":              session["id"],
            "task":            session["task"],
            "goal":            session.get("goal", ""),
            "planned_minutes": session["planned_minutes"],
            "created_at":      session.get("created_at"),
            "started_at":      started_at,
            "ended_at":        ended_at,
            "status":          session.get("status", "completed"),
            "summary":         session.get("summary"),
        },
        "duration_minutes":     duration_minutes,
        "productive_minutes":   productive,
        "nonproductive_minutes": nonproductive,
        "focus_percentage":     focus_pct,
        "distraction_count":    distraction_cnt,
        "windows":              _top_usage(segments, "title"),
        "timeline":             timeline,
    }


def create_reminder(label, reminder_type="once", remind_at=None, days_of_week=None, time_of_day=None, db_path=DB_PATH):
    init_db(db_path)
    created_at = datetime.now(_IST).isoformat()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO reminders (label, reminder_type, remind_at, days_of_week, time_of_day, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (label, reminder_type, remind_at, days_of_week, time_of_day, created_at),
        )
        rid = cursor.lastrowid
    return get_reminder(rid, db_path)


def get_reminder(reminder_id, db_path=DB_PATH):
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
    return dict(row) if row else None


def get_reminders(active_only=False, db_path=DB_PATH):
    init_db(db_path)
    query = "SELECT * FROM reminders"
    if active_only:
        query += " WHERE active = 1"
    query += " ORDER BY created_at DESC"
    with _connect(db_path) as conn:
        rows = conn.execute(query).fetchall()
    return [dict(r) for r in rows]


def delete_reminder(reminder_id, db_path=DB_PATH):
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))


def toggle_reminder(reminder_id, active, db_path=DB_PATH):
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE reminders SET active = ? WHERE id = ?",
            (1 if active else 0, reminder_id),
        )
    return get_reminder(reminder_id, db_path)


def mark_reminder_triggered(reminder_id, db_path=DB_PATH):
    init_db(db_path)
    now = datetime.now(_IST).isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE reminders SET last_triggered_at = ? WHERE id = ?",
            (now, reminder_id),
        )


def deactivate_reminder(reminder_id, db_path=DB_PATH):
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute("UPDATE reminders SET active = 0 WHERE id = ?", (reminder_id,))


def get_due_reminders(db_path=DB_PATH):
    """Return all active reminders whose fire time has arrived (IST)."""
    now = datetime.now(_IST)
    due = []
    for r in get_reminders(active_only=True, db_path=db_path):
        if r["reminder_type"] == "once":
            if not r["remind_at"] or r["last_triggered_at"]:
                continue
            remind_at = datetime.fromisoformat(r["remind_at"])
            if remind_at.tzinfo is None:
                remind_at = remind_at.replace(tzinfo=_IST)
            if now >= remind_at:
                due.append(r)

        elif r["reminder_type"] == "recurring":
            if not r["days_of_week"] or not r["time_of_day"]:
                continue
            weekdays = [int(d) for d in r["days_of_week"].split(",") if d.strip()]
            if now.weekday() not in weekdays:
                continue
            h, m = map(int, r["time_of_day"].split(":"))
            trigger = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if now < trigger:
                continue
            if r["last_triggered_at"]:
                last = datetime.fromisoformat(r["last_triggered_at"])
                if last.tzinfo is None:
                    last = last.replace(tzinfo=_IST)
                if last.date() == now.date():
                    continue
            due.append(r)

    return due


def get_activity_summary(days=7, db_path=DB_PATH):
    init_db(db_path)

    end_date = datetime.now(_IST).date()
    start_date = end_date - timedelta(days=days - 1)
    # Use IST midnight as the cutoff so the SQL query includes all events
    # that belong to start_date in IST (which may start at 18:30 UTC the prior day).
    start_timestamp = datetime.combine(start_date, datetime.min.time(), tzinfo=_IST).astimezone(timezone.utc)

    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT event_type, timestamp, payload
            FROM activity_events
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
            """,
            (start_timestamp.isoformat(),),
        ).fetchall()

    history = {
        (start_date + timedelta(days=offset)).isoformat(): {
            "date": (start_date + timedelta(days=offset)).isoformat(),
            "productive": 0,
            "nonproductive": 0,
        }
        for offset in range(days)
    }

    window_segments = _build_window_segments(rows)
    _add_window_durations(window_segments, history)

    ordered_history = list(history.values())
    ordered_history.reverse()

    today = ordered_history[0]
    total_today = today["productive"] + today["nonproductive"]
    focus_score = round((today["productive"] / total_today) * 100) if total_today else 0

    return {
        "history": ordered_history,
        "today": today,
        "focus_score": focus_score,
        "focus_streak": _calculate_streak(ordered_history),
        "top_titles": _top_usage(window_segments, "title"),
        "timeline": _build_timeline(rows, window_segments),
        "timeline_graph": _build_timeline_graph(rows, window_segments),
    }


def _build_window_segments(rows):
    segments = []
    previous = None

    for row in rows:
        event_type = row["event_type"]

        if event_type != "active_window_changed":
            continue

        current_time = datetime.fromisoformat(row["timestamp"])

        if previous:
            previous_time, previous_payload = previous
            minutes = max(
                0,
                min(30, round((current_time - previous_time).total_seconds() / 60)),
            )
            segments.append(
                {
                    "started_at": previous_time.isoformat(),
                    "ended_at": current_time.isoformat(),
                    "minutes": minutes,
                    "payload": previous_payload,
                    "bucket": _activity_bucket(previous_payload),
                }
            )

        previous = (current_time, json.loads(row["payload"]))

    return segments


def _add_window_durations(window_segments, history):
    for segment in window_segments:
        started_at = datetime.fromisoformat(segment["started_at"])
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        date_key = started_at.astimezone(_IST).date().isoformat()

        if date_key in history:
            history[date_key][segment["bucket"]] += segment["minutes"]


def _top_usage(window_segments, field):
    totals = {}

    for segment in window_segments:
        payload = segment["payload"]
        name = payload.get(field) or "Unknown"
        minutes = segment["minutes"]

        if not name.strip():
            name = "Untitled"

        totals[name] = totals.get(name, 0) + minutes

    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)

    return [
        {
            "name": name,
            "minutes": minutes,
        }
        for name, minutes in ranked[:6]
        if minutes > 0
    ]


def _build_timeline(rows, window_segments):
    timeline = []

    for segment in window_segments[-20:]:
        payload = segment["payload"]
        timeline.append(
            {
                "type": "window",
                "timestamp": segment["started_at"],
                "title": payload.get("title") or "Untitled window",
                "process_name": payload.get("process_name")
                or "Unknown application",
                "minutes": segment["minutes"],
                "bucket": segment["bucket"],
            }
        )

    for row in rows:
        event_type = row["event_type"]

        if event_type not in (
            "user_idle",
            "user_active",
            "user_absent",
            "user_present",
        ):
            continue

        timeline.append(
            {
                "type": "status",
                "event_type": event_type,
                "timestamp": row["timestamp"],
                "payload": json.loads(row["payload"]),
            }
        )

    timeline.sort(key=lambda item: item["timestamp"], reverse=True)

    return timeline[:24]


def _build_timeline_graph(rows, window_segments):
    segments = []

    for segment in window_segments:
        payload = segment["payload"]
        minutes = segment["minutes"]

        if minutes <= 0:
            continue

        segments.append(
            {
                "type": segment["bucket"],
                "started_at": segment["started_at"],
                "ended_at": segment["ended_at"],
                "minutes": minutes,
                "label": payload.get("title") or "Untitled window",
            }
        )

    segments.extend(_build_afk_segments(rows))
    segments.sort(key=lambda item: item["started_at"])

    if not segments:
        return {
            "started_at": None,
            "ended_at": None,
            "segments": [],
        }

    return {
        "started_at": segments[0]["started_at"],
        "ended_at": segments[-1]["ended_at"],
        "segments": segments[-36:],
    }


def _build_afk_segments(rows):
    segments = []
    afk_started_at = None

    for row in rows:
        event_type = row["event_type"]

        if event_type in ("user_idle", "user_absent"):
            afk_started_at = datetime.fromisoformat(row["timestamp"])
            continue

        if event_type not in ("user_active", "user_present"):
            continue

        if not afk_started_at:
            continue

        ended_at = datetime.fromisoformat(row["timestamp"])
        minutes = max(
            1,
            min(180, round((ended_at - afk_started_at).total_seconds() / 60)),
        )

        segments.append(
            {
                "type": "afk",
                "started_at": afk_started_at.isoformat(),
                "ended_at": ended_at.isoformat(),
                "minutes": minutes,
                "label": "AFK / away",
            }
        )
        afk_started_at = None

    if afk_started_at:
        ended_at = datetime.now(timezone.utc)
        minutes = max(
            1,
            min(180, round((ended_at - afk_started_at).total_seconds() / 60)),
        )
        segments.append(
            {
                "type": "afk",
                "started_at": afk_started_at.isoformat(),
                "ended_at": ended_at.isoformat(),
                "minutes": minutes,
                "label": "AFK / away",
            }
        )

    return segments


def _activity_bucket(payload):
    # Fold the URL (when captured) into the haystack — it's a far more reliable
    # signal than the page title for analytics bucketing.
    haystack = f"{payload.get('title', '')} {payload.get('url', '')}".lower()

    if any(keyword in haystack for keyword in NON_PRODUCTIVE_KEYWORDS):
        return "nonproductive"

    return "productive"


def _calculate_streak(history):
    goal = get_daily_goal()
    target = goal["target_minutes"] if goal else 240
    streak = 0

    for row in history:
        if row["productive"] < target:
            break

        streak += 1

    return streak


def _event_row_to_dict(row):
    return {
        "id": row["id"],
        "event_type": row["event_type"],
        "source": row["source"],
        "timestamp": row["timestamp"],
        "payload": json.loads(row["payload"]),
    }


def _connect(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def _today():
    return datetime.now(_IST).date().isoformat()


def _now_iso():
    return datetime.now(timezone.utc).isoformat()
