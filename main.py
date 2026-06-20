from src.pixel_pet.activity import EventCapture
from src.pixel_pet.pet import Pet
from src.pixel_pet.storage import init_db, store_event
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
    init_db()

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
        idle_path="assets/nila/sit-idle-tail",
        scale=0.65,
        animation_speed=0.3,
    )

    app = create_app()

    try:
        pet.start()
        capture.start()
        print("Dashboard running at http://127.0.0.1:5000")
        app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

    finally:
        capture.stop()
        pet.stop()


if __name__ == "__main__":
    main()
