import queue
import threading
import time

from src.pixel_pet.activity.events import ActivityEvent, ActivityEventType


class EventCapture:
    def __init__(self, trackers=None, poll_interval=1.0):
        self.trackers = list(trackers or [])
        self.poll_interval = poll_interval
        self.events = queue.Queue()
        self.listeners = []
        self.running = False
        self.thread = None
        self._stop_requested = threading.Event()

    def add_tracker(self, tracker):
        self.trackers.append(tracker)

    def add_listener(self, listener):
        self.listeners.append(listener)

    def start(self):
        if self.thread and self.thread.is_alive():
            return

        self._stop_requested.clear()
        self.running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.start()

    def stop(self, timeout=5):
        self._stop_requested.set()
        self.running = False

        if self.thread and threading.current_thread() is not self.thread:
            self.thread.join(timeout)

            if self.thread.is_alive():
                raise TimeoutError("Event capture did not stop before timeout.")

        self._close_trackers()

    def poll_once(self):
        captured_events = []

        for tracker in self.trackers:
            try:
                captured_events.extend(tracker.poll())
            except Exception as error:
                captured_events.append(
                    ActivityEvent(
                        event_type=ActivityEventType.TRACKER_ERROR,
                        source=tracker.name,
                        payload={
                            "error": str(error),
                            "tracker": tracker.name,
                        },
                    )
                )

        for event in captured_events:
            self._emit(event)

        return captured_events

    def get_event(self, timeout=None):
        return self.events.get(timeout=timeout)

    def _run(self):
        try:
            while not self._stop_requested.is_set():
                self.poll_once()
                time.sleep(self.poll_interval)
        finally:
            self.running = False
            self._stop_requested.set()
            self._close_trackers()

    def _emit(self, event):
        self.events.put(event)

        for listener in self.listeners:
            listener(event)

    def _close_trackers(self):
        for tracker in self.trackers:
            close = getattr(tracker, "close", None)

            if close:
                close()
