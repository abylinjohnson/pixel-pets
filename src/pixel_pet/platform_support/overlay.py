"""Cross-platform control of the floating pet window.

Responsibilities that used to be hard-wired to win32 now live here:

* keep the window borderless and always-on-top,
* move it (initial placement + click-and-drag),
* enable per-pixel transparency where the OS supports it.

Window positioning works everywhere through ``pygame._sdl2`` (SDL ships with
pygame). Per-pixel transparency (the cat floating with no visible box) is only
available on Windows via a layered colour-key window; on macOS/Linux the pet
shows inside a small borderless card instead.
"""

import glob
import os

from . import IS_WINDOWS


def create_overlay(width: int, height: int):
    return _Overlay(width, height)


class _Overlay:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        # The colour-key used for per-pixel transparency, or None when the
        # platform can't punch a hole in the window (macOS/Linux).
        self.transparent_color = None
        self._window = None
        self._grab = None
        self._hwnd = None  # cached native handle on Windows

        try:
            from pygame._sdl2.video import Window
            self._window = Window.from_display_module()
        except Exception:
            self._window = None

    # ── Setup ──────────────────────────────────────────────────────────────────

    def apply(self, start_pos, transparent_color) -> None:
        """Place the window, pin it on top and enable transparency if possible."""
        if IS_WINDOWS:
            self._cache_hwnd()

        self.move_to(*start_pos)
        self._set_always_on_top()

        if IS_WINDOWS and self._apply_win32_colorkey(transparent_color):
            self.transparent_color = transparent_color
        else:
            self.transparent_color = None

    def _cache_hwnd(self) -> None:
        try:
            import pygame

            self._hwnd = pygame.display.get_wm_info()["window"]
        except Exception:
            self._hwnd = None

    # ── Movement / dragging ────────────────────────────────────────────────────

    def move_to(self, x: int, y: int) -> None:
        # On Windows, move with SetWindowPos(HWND_TOPMOST, ...) so the window
        # keeps its always-on-top Z-order on every move (the SDL position setter
        # silently drops topmost).
        if IS_WINDOWS and self._hwnd is not None:
            try:
                import win32con
                import win32gui

                win32gui.SetWindowPos(
                    self._hwnd,
                    win32con.HWND_TOPMOST,
                    int(x), int(y), 0, 0,
                    win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
                )
                return
            except Exception:
                pass

        if self._window:
            try:
                self._window.position = (int(x), int(y))
            except Exception:
                pass

    def _position(self):
        if not self._window:
            return None
        try:
            return self._window.position
        except Exception:
            return None

    def begin_drag(self) -> None:
        """Record where the cursor grabbed the window (window-relative)."""
        import pygame

        self._grab = pygame.mouse.get_pos()

    def update_drag(self) -> None:
        """Move the window so the grabbed point keeps following the cursor."""
        if self._grab is None:
            return

        import pygame

        rel = pygame.mouse.get_pos()
        pos = self._position()
        if pos is None:
            return

        dx = rel[0] - self._grab[0]
        dy = rel[1] - self._grab[1]
        if dx or dy:
            self.move_to(pos[0] + dx, pos[1] + dy)

    def end_drag(self) -> None:
        self._grab = None

    # ── Always on top ──────────────────────────────────────────────────────────

    def reassert_on_top(self) -> None:
        """Re-pin the window on top. Call periodically — focus changes and the SDL
        position setter can quietly knock the window out of the topmost band."""
        self._set_always_on_top()

    def _set_always_on_top(self) -> None:
        if IS_WINDOWS and self._win32_topmost():
            return
        # Portable best-effort for macOS/Linux (and a Windows fallback).
        self._sdl_always_on_top()

    def _win32_topmost(self) -> bool:
        if self._hwnd is None:
            self._cache_hwnd()
        if self._hwnd is None:
            return False
        try:
            import win32con
            import win32gui

            win32gui.SetWindowPos(
                self._hwnd,
                win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOSIZE | win32con.SWP_NOMOVE | win32con.SWP_NOACTIVATE,
            )
            return True
        except Exception:
            return False

    def _sdl_always_on_top(self) -> None:
        """Call SDL_SetWindowAlwaysOnTop via ctypes (SDL >= 2.0.16)."""
        if not self._window:
            return
        try:
            import ctypes

            lib = self._load_sdl()
            if lib is None:
                return

            window_id = self._window.id
            lib.SDL_GetWindowFromID.restype = ctypes.c_void_p
            lib.SDL_GetWindowFromID.argtypes = [ctypes.c_uint32]
            window_ptr = lib.SDL_GetWindowFromID(ctypes.c_uint32(window_id))
            if not window_ptr:
                return

            lib.SDL_SetWindowAlwaysOnTop.argtypes = [ctypes.c_void_p, ctypes.c_int]
            lib.SDL_SetWindowAlwaysOnTop(ctypes.c_void_p(window_ptr), 1)
        except Exception:
            pass

    @staticmethod
    def _load_sdl():
        import ctypes
        import ctypes.util

        import pygame

        base = os.path.dirname(pygame.__file__)
        candidates = (
            glob.glob(os.path.join(base, "*SDL2*"))
            + glob.glob(os.path.join(base, ".dylibs", "*SDL2*"))
            + glob.glob(os.path.join(base, "..", "pygame.libs", "*SDL2*"))
        )
        for path in candidates:
            if path.lower().endswith((".dll", ".dylib", ".so")) or ".so." in path:
                try:
                    return ctypes.CDLL(path)
                except Exception:
                    continue

        found = ctypes.util.find_library("SDL2")
        if found:
            try:
                return ctypes.CDLL(found)
            except Exception:
                return None
        return None

    # ── Per-pixel transparency (Windows) ───────────────────────────────────────

    def _apply_win32_colorkey(self, color) -> bool:
        try:
            import pygame
            import win32api
            import win32con
            import win32gui

            hwnd = pygame.display.get_wm_info()["window"]
            styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(
                hwnd,
                win32con.GWL_EXSTYLE,
                styles | win32con.WS_EX_LAYERED,
            )
            win32gui.SetLayeredWindowAttributes(
                hwnd,
                win32api.RGB(*color),
                0,
                win32con.LWA_COLORKEY,
            )
            return True
        except Exception:
            return False
