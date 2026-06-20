import os

import win32api
import win32con
import win32gui
import win32process

from src.pixel_pet.activity.events import ActivityEvent, ActivityEventType
from src.pixel_pet.trackers.base_tracker import BaseTracker


class ActiveWindowTracker(BaseTracker):
    name = "active_window_tracker"

    def __init__(self):
        self._last_window = None

    def poll(self):
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        process_id, process_name = self._get_process_details(hwnd)
        current_window = (hwnd, title)

        if current_window == self._last_window:
            return []

        self._last_window = current_window

        return [
            ActivityEvent(
                event_type=ActivityEventType.ACTIVE_WINDOW_CHANGED,
                source=self.name,
                payload={
                    "hwnd": hwnd,
                    "process_id": process_id,
                    "process_name": process_name,
                    "title": title,
                },
            )
        ]

    def _get_process_details(self, hwnd):
        try:
            _, process_id = win32process.GetWindowThreadProcessId(hwnd)
            handle = win32api.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION
                | win32con.PROCESS_VM_READ,
                False,
                process_id,
            )
            process_path = win32process.GetModuleFileNameEx(handle, 0)
            win32api.CloseHandle(handle)

            return process_id, os.path.basename(process_path)

        except Exception:
            return None, "Unknown application"
