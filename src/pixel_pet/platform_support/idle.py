"""Return seconds since the last user input across Windows, macOS and Linux."""

import shutil
import subprocess

from . import IS_LINUX, IS_MACOS, IS_WINDOWS

# Remembers whether the Linux idle tool is missing so we only warn/probe once.
_linux_idle_supported: bool | None = None


def get_idle_seconds() -> float:
    """Seconds since the last keyboard/mouse input. Returns 0.0 when unknown."""
    try:
        if IS_WINDOWS:
            return _windows_idle_seconds()
        if IS_MACOS:
            return _macos_idle_seconds()
        if IS_LINUX:
            return _linux_idle_seconds()
    except Exception:
        pass
    return 0.0


# ── Windows ────────────────────────────────────────────────────────────────────

def _windows_idle_seconds() -> float:
    import win32api

    last_input_tick = win32api.GetLastInputInfo()
    current_tick = win32api.GetTickCount()
    return max(0, current_tick - last_input_tick) / 1000.0


# ── macOS (HIDIdleTime is reported in nanoseconds) ─────────────────────────────

def _macos_idle_seconds() -> float:
    result = subprocess.run(
        ["ioreg", "-c", "IOHIDSystem"],
        capture_output=True,
        text=True,
        timeout=2,
    )
    for line in (result.stdout or "").splitlines():
        if "HIDIdleTime" in line:
            # ... "HIDIdleTime" = 12345678 ...
            nanoseconds = line.rsplit("=", 1)[-1].strip()
            if nanoseconds.isdigit():
                return int(nanoseconds) / 1_000_000_000.0
    return 0.0


# ── Linux (xprintidle reports milliseconds) ────────────────────────────────────

def _linux_idle_seconds() -> float:
    global _linux_idle_supported

    if _linux_idle_supported is False:
        return 0.0

    if not shutil.which("xprintidle"):
        _linux_idle_supported = False
        return 0.0

    result = subprocess.run(
        ["xprintidle"],
        capture_output=True,
        text=True,
        timeout=2,
    )
    value = (result.stdout or "").strip()
    if value.isdigit():
        _linux_idle_supported = True
        return int(value) / 1000.0
    return 0.0
