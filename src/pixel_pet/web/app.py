import json
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory

import threading

from src.pixel_pet.storage import (
    create_focus_session,
    end_focus_session,
    get_activity_summary,
    get_daily_goal,
    get_recent_events,
    get_recent_focus_sessions,
    get_session_analytics,
    init_db,
    save_daily_goal,
    save_session_summary,
    start_focus_session,
)
from src.pixel_pet.pets import (
    get_current_pet_key,
    get_current_pet_profile,
    list_pet_profiles,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ASSETS_DIR = PROJECT_ROOT / "assets"


def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    init_db()

    # ── Pages ─────────────────────────────────────────────────────────────────

    @app.get("/")
    def overview():
        return render_template("overview.html")

    @app.get("/focus")
    def focus():
        return render_template("focus.html")

    @app.get("/events")
    def event_logs():
        return render_template("event_logs.html")

    @app.get("/assets/<path:filename>")
    def assets(filename):
        return send_from_directory(ASSETS_DIR, filename)

    # ── Summary / events APIs ─────────────────────────────────────────────────

    @app.get("/api/summary")
    def api_summary():
        days = request.args.get("days", default=7, type=int)
        days = max(1, min(days, 30))
        return jsonify(get_activity_summary(days=days))

    @app.get("/api/events")
    def api_events():
        limit = request.args.get("limit", default=50, type=int)
        limit = max(1, min(limit, 200))
        return jsonify({"events": get_recent_events(limit=limit)})

    # ── Pet API ───────────────────────────────────────────────────────────────

    @app.get("/api/pet")
    def api_pet():
        return jsonify(
            {
                "pet": get_current_pet_profile().to_dict(),
                "current_pet_key": get_current_pet_key(),
                "available_pets": [
                    profile.to_dict() for profile in list_pet_profiles()
                ],
            }
        )

    # ── Daily goal APIs ───────────────────────────────────────────────────────

    @app.get("/api/goals/today")
    def api_get_goal():
        return jsonify({"goal": get_daily_goal()})

    @app.post("/api/goals/today")
    def api_save_goal():
        data = request.get_json(force=True)
        goal_text = data.get("text", "").strip()
        target_minutes = int(data.get("target_minutes", 0))

        if not goal_text:
            return jsonify({"error": "Goal text is required."}), 400
        if target_minutes <= 0:
            return jsonify({"error": "Target minutes must be positive."}), 400

        return jsonify({"goal": save_daily_goal(goal_text, target_minutes)})

    # ── Focus session APIs ────────────────────────────────────────────────────

    @app.get("/api/focus-sessions/recent")
    def api_recent_focus_sessions():
        limit = request.args.get("limit", default=10, type=int)
        limit = max(1, min(limit, 50))
        return jsonify({"sessions": get_recent_focus_sessions(limit=limit)})

    @app.post("/api/focus-sessions")
    def api_create_focus_session():
        data = request.get_json(force=True)
        task           = data.get("task", "").strip()
        goal           = data.get("goal", "").strip()
        planned_minutes = int(data.get("planned_minutes", 0))

        if not task:
            return jsonify({"error": "Task is required."}), 400
        if planned_minutes <= 0:
            return jsonify({"error": "Planned minutes must be positive."}), 400

        session = create_focus_session(task, planned_minutes, goal=goal)
        return jsonify({"session": session}), 201

    @app.post("/api/focus-sessions/active")
    def api_set_focus_session_active():
        from src.pixel_pet.state import FocusState
        data       = request.get_json(force=True)
        active     = bool(data.get("active", False))
        session_id = data.get("session_id")

        if active:
            task = data.get("task", "")
            goal = data.get("goal", "")
            FocusState.set_session(task, goal, session_id)
            if session_id:
                start_focus_session(int(session_id))
        else:
            FocusState.set_active(False)
            if session_id:
                end_focus_session(int(session_id))
                t = threading.Thread(
                    target=_generate_and_save_summary,
                    args=(int(session_id),),
                    daemon=True,
                )
                t.start()

        return jsonify({"active": active})

    @app.get("/api/focus-sessions/<int:session_id>/analytics")
    def api_focus_session_analytics(session_id):
        analytics = get_session_analytics(session_id)
        if not analytics:
            return jsonify({"error": "Session not found."}), 404
        return jsonify({"analytics": analytics})

    @app.post("/api/focus-sessions/<int:session_id>/summary")
    def api_focus_session_summary(session_id):
        analytics = get_session_analytics(session_id)
        if not analytics:
            return jsonify({"error": "Session not found."}), 404
        cached = analytics["session"].get("summary")
        if cached:
            return jsonify({"summary": cached})
        summary = _generate_session_summary(analytics)
        if summary:
            save_session_summary(session_id, summary)
        return jsonify({"summary": summary})

    return app


# ── LLM session summary ───────────────────────────────────────────────────────

def _generate_and_save_summary(session_id: int) -> None:
    """Background task: generate summary once and persist to DB."""
    analytics = get_session_analytics(session_id)
    if not analytics:
        return
    if analytics["session"].get("summary"):
        return  # already generated
    summary = _generate_session_summary(analytics)
    if summary:
        save_session_summary(session_id, summary)


def _generate_session_summary(analytics: dict) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        session = analytics["session"]
        payload = {
            "task":                session["task"],
            "goal":                session.get("goal", ""),
            "planned_minutes":     session["planned_minutes"],
            "actual_minutes":      analytics["duration_minutes"],
            "productive_minutes":  analytics["productive_minutes"],
            "focus_percentage":    analytics["focus_percentage"],
            "distraction_count":   analytics["distraction_count"],
            "top_windows":         [w["name"] for w in analytics["windows"][:5]],
        }

        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are a warm, encouraging productivity coach. "
                        "Write a 2–3 sentence summary of this focus session. "
                        "Be specific about what went well and offer one gentle, constructive suggestion. "
                        "Sound personal and human — not generic."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(payload),
                },
            ],
        )
        return response.output_text.strip() or None

    except Exception:
        return None
