"""Cross-platform helpers that isolate every OS-specific call in one place.

The rest of the app imports from here and never touches ``win32``/``ctypes``/
``subprocess`` directly, so the same code runs on Windows, macOS and Linux.
"""

import sys

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# Submodule imports come after the flags so the submodules can read them.
from .active_window import get_active_window  # noqa: E402
from .browser_url import get_browser_url  # noqa: E402
from .idle import get_idle_seconds  # noqa: E402
from .overlay import create_overlay  # noqa: E402

__all__ = [
    "IS_WINDOWS",
    "IS_MACOS",
    "IS_LINUX",
    "get_active_window",
    "get_browser_url",
    "get_idle_seconds",
    "create_overlay",
]
