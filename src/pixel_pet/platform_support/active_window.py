"""Return the currently focused window across Windows, macOS and Linux."""

import os
import shutil
import subprocess

from . import IS_LINUX, IS_MACOS, IS_WINDOWS

_UNKNOWN = {"hwnd": None, "process_id": None, "process_name": "Unknown application", "title": ""}


def get_active_window() -> dict:
    """Return ``{"hwnd", "process_id", "process_name", "title"}`` for the focused window.

    Always returns a dict; on failure (or unsupported environment such as Wayland
    without tools installed) it returns a safe "Unknown application" placeholder.
    """
    try:
        if IS_WINDOWS:
            return _windows_active_window()
        if IS_MACOS:
            return _macos_active_window()
        if IS_LINUX:
            return _linux_active_window()
    except Exception:
        pass
    return dict(_UNKNOWN)


# ── Windows ────────────────────────────────────────────────────────────────────

def _windows_active_window() -> dict:
    import win32api
    import win32con
    import win32gui
    import win32process

    hwnd = win32gui.GetForegroundWindow()
    title = win32gui.GetWindowText(hwnd)

    process_id = None
    process_name = "Unknown application"
    try:
        _, process_id = win32process.GetWindowThreadProcessId(hwnd)
        handle = win32api.OpenProcess(
            win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
            False,
            process_id,
        )
        process_path = win32process.GetModuleFileNameEx(handle, 0)
        win32api.CloseHandle(handle)
        process_name = os.path.basename(process_path)
    except Exception:
        pass

    return {
        "hwnd": hwnd,
        "process_id": process_id,
        "process_name": process_name,
        "title": title,
    }


# ── macOS ──────────────────────────────────────────────────────────────────────

_MACOS_SCRIPT = '''
tell application "System Events"
    set frontApp to first application process whose frontmost is true
    set appName to name of frontApp
    set windowTitle to ""
    try
        set windowTitle to name of front window of frontApp
    end try
end tell
return appName & "|||" & windowTitle
'''


def _macos_active_window() -> dict:
    result = subprocess.run(
        ["osascript", "-e", _MACOS_SCRIPT],
        capture_output=True,
        text=True,
        timeout=2,
    )
    output = (result.stdout or "").strip()
    app_name, _, window_title = output.partition("|||")
    return {
        "hwnd": None,
        "process_id": None,
        "process_name": (app_name or "Unknown application").strip(),
        "title": window_title.strip(),
    }


# ── Linux (X11 via xdotool, with an xprop fallback) ────────────────────────────

def _linux_active_window() -> dict:
    if shutil.which("xdotool"):
        win_id = _run(["xdotool", "getactivewindow"])
        if win_id:
            title = _run(["xdotool", "getactivewindow", "getwindowname"]) or ""
            pid = _run(["xdotool", "getactivewindow", "getwindowpid"])
            process_name = _process_name_from_pid(pid)
            return {
                "hwnd": win_id,
                "process_id": int(pid) if pid and pid.isdigit() else None,
                "process_name": process_name,
                "title": title,
            }

    if shutil.which("xprop"):
        # _NET_ACTIVE_WINDOW -> window id, then read its name.
        active = _run(["xprop", "-root", "_NET_ACTIVE_WINDOW"])
        win_id = active.split()[-1] if active else ""
        if win_id and win_id != "0x0":
            name = _run(["xprop", "-id", win_id, "_NET_WM_NAME"])
            title = name.split("=", 1)[-1].strip().strip('"') if "=" in name else ""
            return {
                "hwnd": win_id,
                "process_id": None,
                "process_name": "Unknown application",
                "title": title,
            }

    return dict(_UNKNOWN)


def _process_name_from_pid(pid) -> str:
    if not pid or not str(pid).isdigit():
        return "Unknown application"
    try:
        with open(f"/proc/{pid}/comm", "r", encoding="utf-8") as handle:
            return handle.read().strip() or "Unknown application"
    except OSError:
        return "Unknown application"


def _run(command) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=2)
        return (result.stdout or "").strip()
    except Exception:
        return ""
