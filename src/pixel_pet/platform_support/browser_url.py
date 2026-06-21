"""Best-effort: read the active browser tab's URL for richer focus context.

The window title alone is often too thin ("Home", "New Tab") for the cat to judge
whether a page is on-task. When the foreground app is a real browser we read its
address bar so the LLM can see ``youtube.com/watch...`` instead of just "Home".

This is strictly best-effort and always degrades to an empty string:
* Windows - via the optional ``uiautomation`` package (reads the omnibox).
* macOS   - via AppleScript against Safari / Chromium-family browsers.
* Linux   - not supported yet (returns "").
"""

import subprocess

from . import IS_MACOS, IS_WINDOWS

_BROWSER_PROCESSES = (
    "chrome", "msedge", "firefox", "brave", "opera", "vivaldi", "arc", "safari",
)

# Remember if the Windows automation lib is missing so we only probe once.
_uia_unavailable = False


def get_browser_url(process_name: str) -> str:
    """Return the active tab URL for a browser, or "" for anything else / on failure."""
    proc = (process_name or "").lower()
    if not any(browser in proc for browser in _BROWSER_PROCESSES):
        return ""
    try:
        if IS_WINDOWS:
            return _windows_url()
        if IS_MACOS:
            return _macos_url(proc)
    except Exception:
        return ""
    return ""


# ── Windows (UI Automation omnibox read) ───────────────────────────────────────

def _windows_url() -> str:
    global _uia_unavailable
    if _uia_unavailable:
        return ""

    try:
        import uiautomation as auto
    except ImportError:
        _uia_unavailable = True
        return ""

    try:
        # Bounded search so this can't stall the tracker thread.
        auto.SetGlobalSearchTimeout(0.5)
        window = auto.GetForegroundControl()
        if not window:
            return ""

        edit = window.EditControl(searchDepth=18)
        if edit.Exists(0, 0):
            value = ""
            try:
                value = (edit.GetValuePattern().Value or "").strip()
            except Exception:
                value = ""
            if _looks_like_url(value):
                return value
    except Exception:
        return ""
    return ""


# ── macOS (AppleScript) ────────────────────────────────────────────────────────

_SAFARI_SCRIPT = 'tell application "Safari" to return URL of front document'
_CHROMIUM_SCRIPT = 'tell application "{app}" to return URL of active tab of front window'

_CHROMIUM_APPS = {
    "chrome": "Google Chrome",
    "brave": "Brave Browser",
    "msedge": "Microsoft Edge",
    "vivaldi": "Vivaldi",
    "opera": "Opera",
    "arc": "Arc",
}


def _macos_url(process_name: str) -> str:
    if "safari" in process_name:
        return _osascript(_SAFARI_SCRIPT)
    for key, app in _CHROMIUM_APPS.items():
        if key in process_name:
            return _osascript(_CHROMIUM_SCRIPT.format(app=app))
    return ""


def _osascript(script: str) -> str:
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=2,
        )
        value = (result.stdout or "").strip()
        return value if _looks_like_url(value) else ""
    except Exception:
        return ""


# ── Shared ─────────────────────────────────────────────────────────────────────

def _looks_like_url(value: str) -> bool:
    value = (value or "").strip()
    if not value:
        return False
    if value.startswith(("http://", "https://")):
        return True
    # Domain-ish: has a dot and no spaces (e.g. "github.com/anthropics").
    return "." in value and " " not in value
