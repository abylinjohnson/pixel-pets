import os
import queue
import threading
import time
from pathlib import Path

import pygame

from src.pixel_pet.platform_support import create_overlay


# Pure black (0,0,0) is the win32 transparency colour key — never use it in
# bubble/cat colours, or those pixels would be punched transparent on Windows.
_TRANSPARENT = (0, 0, 0)

# Flat background drawn on platforms without per-pixel transparency (macOS/Linux),
# so the pet shows inside a clean light card instead of a black box.
_STAGE_BG = (244, 246, 249)

# ── Pixel-art speech bubble palette ────────────────────────────────────────────
_BUBBLE_BG     = (255, 255, 255)   # panel fill
_BUBBLE_BORDER = (24, 26, 33)      # chunky dark outline (not pure black)
_BUBBLE_SHADOW = (181, 188, 200)   # hard pixel drop-shadow
_BUBBLE_TEXT   = (24, 26, 33)
_BUBBLE_ACCENT = (16, 185, 129)    # emerald top strip — matches the web theme

# Size of one "pixel" block for the blocky corners/border, in screen pixels.
_PX = 4

# How many steps form each blocky corner (a 2-step staircase reads as pixel-art).
_CORNER_STEPS = 2


class Pet:
    def __init__(
        self,
        idle_path,
        width=360,
        height=360,
        scale=0.65,
        animation_speed=0.3,
        start_pos=(100, 100),
    ):
        self.idle_path = idle_path
        self.current_path = idle_path

        self.width = width
        self.height = height
        self.scale = scale
        self.animation_speed = animation_speed
        self.start_pos = start_pos

        self.command_queue = queue.Queue()
        self.running = False
        self.thread = None
        self._stop_requested = threading.Event()

        # Resolve audio directory relative to the pet's asset folder
        self._audio_dir = Path(idle_path).parent / "audio"

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        if self.thread and self.thread.is_alive():
            return

        self._stop_requested.clear()
        self.running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.start()

    def stop(self, timeout=5):
        if not self.thread or not self.thread.is_alive():
            self.running = False
            return

        self._stop_requested.set()
        self.command_queue.put({"type": "stop"})

        if pygame.get_init() and pygame.display.get_init():
            try:
                pygame.event.post(pygame.event.Event(pygame.QUIT))
            except pygame.error:
                pass

        if threading.current_thread() is not self.thread:
            self.thread.join(timeout)

            if self.thread.is_alive():
                raise TimeoutError("Pet did not stop before the timeout.")

    def play_animation(self, asset_path, duration=2):
        """Play another animation for `duration` seconds, then return to idle."""
        if not self.running:
            return

        self.command_queue.put({
            "type": "play",
            "path": asset_path,
            "duration": duration,
        })

    def set_idle_animation(self, asset_path, switch_now=False):
        if not self.running:
            self.idle_path = asset_path
            self.current_path = asset_path
            return

        self.command_queue.put({
            "type": "set_idle",
            "path": asset_path,
            "switch_now": switch_now,
        })

    def show_speech_bubble(self, text: str, duration: float = 6.0):
        """Display a speech bubble with `text` above the cat for `duration` seconds."""
        if not self.running:
            return

        self.command_queue.put({
            "type": "speech",
            "text": text.strip(),
            "duration": duration,
        })

    def hide_speech_bubble(self):
        """Immediately dismiss any visible speech bubble."""
        if not self.running:
            return

        self.command_queue.put({"type": "hide_speech"})

    # ── Internal render loop ──────────────────────────────────────────────────

    def _load_frames(self, asset_path):
        frames = []

        for file in sorted(os.listdir(asset_path)):
            if file.endswith(".png"):
                img = pygame.image.load(
                    os.path.join(asset_path, file)
                ).convert_alpha()

                new_width  = int(img.get_width()  * self.scale)
                new_height = int(img.get_height() * self.scale)

                img = pygame.transform.scale(img, (new_width, new_height))
                frames.append(img)

        return frames

    def _run(self):
        try:
            pygame.init()

            screen = pygame.display.set_mode(
                (self.width, self.height),
                pygame.NOFRAME,
            )
            pygame.display.set_caption("Desktop Cat")

            # Cross-platform window setup: borderless, on-top, transparent if able.
            overlay = create_overlay(self.width, self.height)
            overlay.apply(self.start_pos, _TRANSPARENT)

            # On Windows the colour key makes _TRANSPARENT punch through; elsewhere
            # we paint a flat card so the cat isn't sitting on a black rectangle.
            background_color = (
                overlay.transparent_color
                if overlay.transparent_color is not None
                else _STAGE_BG
            )

            # ── Audio setup ───────────────────────────────────────────────────
            meow_sound = None
            purr_sound = None
            purr_looping = False

            if pygame.mixer.get_init():
                meow_path = self._audio_dir / "meow.mp3"
                purr_path = self._audio_dir / "purring.mp3"
                try:
                    if meow_path.exists():
                        meow_sound = pygame.mixer.Sound(str(meow_path))
                        meow_sound.set_volume(0.65)
                    if purr_path.exists():
                        purr_sound = pygame.mixer.Sound(str(purr_path))
                        purr_sound.set_volume(0.4)
                except pygame.error:
                    pass

            def _play_sound_for(asset_path: str) -> None:
                """Auto-play the appropriate sound for an animation path."""
                nonlocal purr_looping
                basename = os.path.basename(asset_path)

                # Stop any looping purr before starting a new sound
                if purr_sound and purr_looping:
                    purr_sound.stop()
                    purr_looping = False

                if "meow" in basename:
                    if meow_sound:
                        meow_sound.play()
                elif "sleeping" in basename:
                    if purr_sound:
                        purr_sound.play(loops=-1)   # loop until animation ends
                        purr_looping = True
                elif any(kw in basename for kw in ("licking", "yawning", "idle")):
                    if purr_sound:
                        purr_sound.play()           # one-shot gentle purr

            def _stop_looping_sound() -> None:
                nonlocal purr_looping
                if purr_sound and purr_looping:
                    purr_sound.stop()
                    purr_looping = False

            # ── Animation / font setup ────────────────────────────────────────
            frames = self._load_frames(self.idle_path)
            clock  = pygame.time.Clock()
            frame  = 0
            timer  = 0.0

            dragging = False

            temporary_animation_end_time = None

            speech_font = self._load_pixel_font()

            speech_text     = None
            speech_end_time = 0.0

            # Periodically re-pin the window on top (cheap; ~once a second).
            next_top_reassert = 0.0

            while self.running and not self._stop_requested.is_set():
                dt = clock.tick(120) / 1000

                now = time.time()
                if now >= next_top_reassert:
                    overlay.reassert_on_top()
                    next_top_reassert = now + 1.0

                # Process commands
                while not self.command_queue.empty():
                    command = self.command_queue.get()

                    if command["type"] == "stop":
                        self.running = False

                    elif command["type"] == "set_idle":
                        self.idle_path = command["path"]
                        self.current_path = command["path"]

                        if command["switch_now"] or not temporary_animation_end_time:
                            frames = self._load_frames(self.idle_path)
                            frame  = 0
                            timer  = 0.0
                            temporary_animation_end_time = None

                    elif command["type"] == "play":
                        self.current_path = command["path"]
                        _play_sound_for(command["path"])
                        frames = self._load_frames(command["path"])
                        frame  = 0
                        timer  = 0.0
                        temporary_animation_end_time = time.time() + command["duration"]

                    elif command["type"] == "speech":
                        speech_text     = command["text"]
                        speech_end_time = time.time() + command["duration"]
                        if meow_sound:
                            meow_sound.play()

                    elif command["type"] == "hide_speech":
                        speech_text = None

                # Return to idle when a temporary animation finishes
                if temporary_animation_end_time and time.time() >= temporary_animation_end_time:
                    _stop_looping_sound()
                    frames = self._load_frames(self.idle_path)
                    frame  = 0
                    timer  = 0.0
                    temporary_animation_end_time = None

                # Expire speech bubble
                if speech_text and time.time() >= speech_end_time:
                    speech_text = None

                # Pygame events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False

                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        self.running = False

                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        dragging = True
                        overlay.begin_drag()

                    if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                        dragging = False
                        overlay.end_drag()

                if dragging:
                    overlay.update_drag()

                # Advance animation frame
                timer += dt
                if timer > self.animation_speed:
                    timer = 0.0
                    frame = (frame + 1) % len(frames)

                # Draw
                screen.fill(background_color)

                current = frames[frame]
                rect = current.get_rect(center=(self.width // 2, self.height // 2))
                screen.blit(current, rect)

                if speech_text:
                    self._draw_speech_bubble(screen, speech_text, speech_font)

                pygame.display.update()

        finally:
            self.running = False
            self._stop_requested.set()
            if pygame.mixer.get_init():
                pygame.mixer.stop()
            pygame.quit()

    # ── Fonts ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _load_pixel_font():
        """Pick a crisp monospace face for the blocky pixel bubble."""
        # Prefer classic bitmap/monospace faces; fall back to pygame's own font.
        for name in ("Fixedsys", "Perfect DOS VGA 437", "Consolas",
                     "Courier New", "DejaVu Sans Mono", "Menlo", "Monaco"):
            try:
                font = pygame.font.SysFont(name, 20)
                if font:
                    return font
            except Exception:
                continue
        return pygame.font.Font(None, 22)

    # ── Pixel-art speech bubble renderer ────────────────────────────────────────

    def _draw_speech_bubble(self, screen, text: str, font) -> None:
        """Draw a retro, pixel-art speech bubble in the upper part of the window."""
        padding = 12
        margin  = 22
        accent_h = _PX * 2                     # emerald title strip height
        max_text_w = self.width - margin * 2 - padding * 2

        lines = self._wrap_text(text, font, max_text_w)
        if not lines:
            return

        line_height = font.get_linesize() + 2
        bx = margin
        by = 12
        bw = self.width - margin * 2
        bh = len(lines) * line_height + padding * 2 + accent_h

        # 1. Hard pixel drop-shadow, offset down-right (no blur).
        self._fill_blocky(screen, _BUBBLE_SHADOW, bx + _PX, by + _PX, bw, bh)

        # 2. Chunky dark border, then the white panel inset inside it.
        self._fill_blocky(screen, _BUBBLE_BORDER, bx, by, bw, bh)
        self._fill_blocky(
            screen, _BUBBLE_BG,
            bx + _PX, by + _PX, bw - 2 * _PX, bh - 2 * _PX,
        )

        # 3. Emerald accent strip along the top (inside the border).
        screen.fill(
            _BUBBLE_ACCENT,
            pygame.Rect(bx + _PX * 3, by + _PX, bw - _PX * 6, accent_h),
        )

        # 4. Blocky tail stepping down toward the cat.
        tail_cx  = self.width // 2
        tail_top = by + bh
        self._draw_blocky_tail(screen, tail_cx, tail_top)

        # 5. Pixel text (antialiasing OFF for crisp edges).
        text_top = by + _PX + accent_h + padding - 4
        for i, line in enumerate(lines):
            surf = font.render(line, False, _BUBBLE_TEXT)
            screen.blit(surf, (bx + padding, text_top + i * line_height))

    @staticmethod
    def _wrap_text(text, font, max_width):
        lines: list[str] = []
        current: list[str] = []
        for word in text.split():
            test = " ".join(current + [word])
            if font.size(test)[0] <= max_width:
                current.append(word)
            else:
                if current:
                    lines.append(" ".join(current))
                current = [word]
        if current:
            lines.append(" ".join(current))
        return lines

    @staticmethod
    def _fill_blocky(screen, color, x, y, w, h, steps=_CORNER_STEPS):
        """Filled rectangle with a stepped, staircase pixel-art corner."""
        x, y, w, h = int(x), int(y), int(w), int(h)
        inset = steps * _PX

        # Central full-width block...
        screen.fill(color, pygame.Rect(x, y + inset, w, h - 2 * inset))
        # ...plus a staircase of bands shrinking toward the top and bottom edges.
        for k in range(steps):
            side = (steps - k) * _PX
            screen.fill(color, pygame.Rect(x + side, y + k * _PX, w - 2 * side, _PX))
            screen.fill(color, pygame.Rect(x + side, y + h - (k + 1) * _PX, w - 2 * side, _PX))

    @staticmethod
    def _draw_blocky_tail(screen, cx, top):
        """Stepped pixel tail (stacked shrinking blocks) with shadow + border."""
        steps = 3
        for i in range(steps):
            half = (steps - i) * _PX
            row_y = top - _PX + i * _PX
            # shadow
            screen.fill(_BUBBLE_SHADOW, pygame.Rect(cx - half + _PX, row_y + _PX, half * 2, _PX))
            # border
            screen.fill(_BUBBLE_BORDER, pygame.Rect(cx - half, row_y, half * 2, _PX))
            # fill (inset by one pixel block on each side)
            if half - _PX > 0:
                screen.fill(_BUBBLE_BG, pygame.Rect(cx - half + _PX, row_y, (half - _PX) * 2, _PX))
