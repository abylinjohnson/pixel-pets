import win32api

from src.pixel_pet.activity.events import ActivityEvent, ActivityEventType
from src.pixel_pet.trackers.base_tracker import BaseTracker


class IdleTracker(BaseTracker):
    name = "idle_tracker"

    def __init__(self, idle_threshold_seconds=60):
        self.idle_threshold_seconds = idle_threshold_seconds
        self._was_idle = False

    def poll(self):
        idle_seconds = self._get_idle_seconds()
        is_idle = idle_seconds >= self.idle_threshold_seconds

        if is_idle == self._was_idle:
            return []

        self._was_idle = is_idle

        event_type = (
            ActivityEventType.USER_IDLE
            if is_idle
            else ActivityEventType.USER_ACTIVE
        )

        return [
            ActivityEvent(
                event_type=event_type,
                source=self.name,
                payload={
                    "idle_seconds": idle_seconds,
                    "idle_threshold_seconds": self.idle_threshold_seconds,
                },
            )
        ]

    def _get_idle_seconds(self):
        last_input_tick = win32api.GetLastInputInfo()
        current_tick = win32api.GetTickCount()
        idle_milliseconds = current_tick - last_input_tick

        return idle_milliseconds / 1000
