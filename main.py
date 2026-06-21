import os
import time
import threading

from src.pixel_pet.ai import PetAiController
from src.pixel_pet.activity import EventCapture
from src.pixel_pet.config import load_env_file
from src.pixel_pet.handlers import PetBehaviorHandler
from src.pixel_pet.pet import Pet
from src.pixel_pet.pets import get_current_pet_key, get_idle_asset_path
from src.pixel_pet.state import FocusState
from src.pixel_pet.storage import (
    deactivate_reminder,
    get_active_focus_session,
    get_due_reminders,
    init_db,
    mark_reminder_triggered,
    store_event,
)
from src.pixel_pet.trackers import (
    ActiveWindowTracker,
    CameraPresenceTracker,
    IdleTracker,
)
from src.pixel_pet.web import create_app


def print_event(event):
    timestamp = event.timestamp.strftime("%H:%M:%S")
    print(
        f"[{timestamp}] {event.event_type.value} "
        f"from {event.source}: {event.payload}"
    )


def main():
    loaded_env_path = load_env_file()
    api_key_loaded = bool(os.getenv("OPENAI_API_KEY"))
    current_pet_key = get_current_pet_key()
    init_db()

    # Restore any in-progress session that was running when the server last stopped.
    _active = get_active_focus_session()
    if _active:
        FocusState.set_session(_active["task"], _active.get("goal", ""), _active["id"])
        print(f"Resumed active session: {_active['task']!r} (id={_active['id']})")

    capture = EventCapture(
        trackers=[
            ActiveWindowTracker(),
            IdleTracker(idle_threshold_seconds=10),
            CameraPresenceTracker(),
        ],
        poll_interval=1,
    )
    capture.add_listener(store_event)
    capture.add_listener(print_event)
    pet = Pet(
        idle_path=get_idle_asset_path(current_pet_key),
        scale=0.65,
        animation_speed=0.3,
    )
    pet_handler = PetBehaviorHandler(pet, pet_key=current_pet_key)
    pet_ai = PetAiController(pet_handler)
    capture.add_listener(pet_ai)
    app = create_app()

    reminder_thread = threading.Thread(
        target=_run_reminder_checker,
        args=(pet_handler,),
        daemon=True,
    )

    try:
        pet.start()
        capture.start()
        reminder_thread.start()
        print(
            "Environment file loaded:"
            f" {loaded_env_path if loaded_env_path else 'none'}"
        )
        print(
            "OpenAI API key loaded:"
            f" {'yes' if api_key_loaded else 'no'}"
        )
        print(f"Current pet profile: {current_pet_key}")
        print("Dashboard running at http://127.0.0.1:5000")
        app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

    finally:
        capture.stop()
        pet.stop()


def _run_reminder_checker(pet_handler):
    """Poll every 30 s for due reminders and trigger the cat."""
    time.sleep(10)  # small startup grace period
    while True:
        try:
            for reminder in get_due_reminders():
                print(f"[reminder] Firing: {reminder['label']}")
                pet_handler.remind(reminder["label"])
                mark_reminder_triggered(reminder["id"])
                if reminder["reminder_type"] == "once":
                    deactivate_reminder(reminder["id"])
        except Exception as exc:
            print(f"[reminder] Error: {exc}")
        time.sleep(30)


if __name__ == "__main__":
    main()
