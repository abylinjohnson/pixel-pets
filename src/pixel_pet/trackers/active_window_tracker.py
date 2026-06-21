from src.pixel_pet.activity.events import ActivityEvent, ActivityEventType
from src.pixel_pet.platform_support import get_active_window, get_browser_url
from src.pixel_pet.trackers.base_tracker import BaseTracker


class ActiveWindowTracker(BaseTracker):
    name = "active_window_tracker"

    def __init__(self):
        self._last_window = None

    def poll(self):
        window = get_active_window()
        hwnd = window.get("hwnd")
        title = window.get("title", "")
        current_window = (hwnd, title)

        if current_window == self._last_window:
            return []

        self._last_window = current_window

        process_name = window.get("process_name", "Unknown application")

        # Only read the URL when the window actually changed (it's a ~0.5s UI
        # Automation call), and only for real browsers.
        url = get_browser_url(process_name)

        return [
            ActivityEvent(
                event_type=ActivityEventType.ACTIVE_WINDOW_CHANGED,
                source=self.name,
                payload={
                    "hwnd": hwnd,
                    "process_id": window.get("process_id"),
                    "process_name": process_name,
                    "title": title,
                    "url": url,
                },
            )
        ]
