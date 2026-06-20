from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory

from src.pixel_pet.storage import (
    create_focus_session,
    get_activity_summary,
    get_daily_goal,
    get_recent_events,
    init_db,
    save_daily_goal,
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

    @app.get("/")
    def overview():
        return render_template("overview.html")

    @app.get("/events")
    def event_logs():
        return render_template("event_logs.html")

    @app.get("/assets/<path:filename>")
    def assets(filename):
        return send_from_directory(ASSETS_DIR, filename)

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

        goal = save_daily_goal(goal_text, target_minutes)

        return jsonify({"goal": goal})

    @app.post("/api/focus-sessions")
    def api_create_focus_session():
        data = request.get_json(force=True)
        task = data.get("task", "").strip()
        planned_minutes = int(data.get("planned_minutes", 0))

        if not task:
            return jsonify({"error": "Task is required."}), 400

        if planned_minutes <= 0:
            return jsonify({"error": "Planned minutes must be positive."}), 400

        session = create_focus_session(task, planned_minutes)

        return jsonify({"session": session}), 201

    return app
