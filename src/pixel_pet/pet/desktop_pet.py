import pygame
import win32gui
import win32con
import win32api
import os
import threading
import queue
import time


# Pure black (0,0,0) is the win32 transparency color key — never use it in bubble colors.
_TRANSPARENT   = (0, 0, 0)
_BUBBLE_BG     = (255, 255, 255)  # white
_BUBBLE_BORDER = (18, 18, 18)     # near-black (not pure black)
_BUBBLE_TEXT   = (12, 12, 12)     # near-black (not pure black)
_BUBBLE_TAIL   = (255, 255, 255)


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

            hwnd = pygame.display.get_wm_info()["window"]

            styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(
                hwnd,
                win32con.GWL_EXSTYLE,
                styles | win32con.WS_EX_LAYERED,
            )
            win32gui.SetLayeredWindowAttributes(
                hwnd,
                win32api.RGB(*_TRANSPARENT),
                0,
                win32con.LWA_COLORKEY,
            )
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                self.start_pos[0],
                self.start_pos[1],
                0,
                0,
                win32con.SWP_NOSIZE,
            )

            frames = self._load_frames(self.idle_path)
            clock  = pygame.time.Clock()
            frame  = 0
            timer  = 0.0

            dragging      = False
            drag_offset_x = 0
            drag_offset_y = 0

            temporary_animation_end_time = None

            # Pixel font: Fixedsys is a classic Windows bitmap pixel font.
            # pygame.font.Font(None, size) is pygame's own pixel bitmap — reliable fallback.
            speech_font = pygame.font.SysFont("Fixedsys", 16) or pygame.font.Font(None, 17)

            speech_text     = None
            speech_end_time = 0.0

            while self.running and not self._stop_requested.is_set():
                dt = clock.tick(120) / 1000

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
                        frames = self._load_frames(command["path"])
                        frame  = 0
                        timer  = 0.0
                        temporary_animation_end_time = time.time() + command["duration"]

                    elif command["type"] == "speech":
                        speech_text     = command["text"]
                        speech_end_time = time.time() + command["duration"]

                    elif command["type"] == "hide_speech":
                        speech_text = None

                # Return to idle when a temporary animation finishes
                if temporary_animation_end_time and time.time() >= temporary_animation_end_time:
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
                        dragging      = True
                        drag_offset_x, drag_offset_y = pygame.mouse.get_pos()

                    if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                        dragging = False

                if dragging:
                    mx, my = win32api.GetCursorPos()
                    win32gui.SetWindowPos(
                        hwnd,
                        win32con.HWND_TOPMOST,
                        mx - drag_offset_x,
                        my - drag_offset_y,
                        0,
                        0,
                        win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
                    )

                # Advance animation frame
                timer += dt
                if timer > self.animation_speed:
                    timer = 0.0
                    frame = (frame + 1) % len(frames)

                # Draw
                screen.fill(_TRANSPARENT)

                current = frames[frame]
                rect = current.get_rect(center=(self.width // 2, self.height // 2))
                screen.blit(current, rect)

                if speech_text:
                    self._draw_speech_bubble(screen, speech_text, speech_font)

                pygame.display.update()

        finally:
            self.running = False
            self._stop_requested.set()
            pygame.quit()

    # ── Speech bubble renderer ────────────────────────────────────────────────

    def _draw_speech_bubble(self, screen, text: str, font) -> None:
        """Render a rounded speech bubble with a tail in the upper portion of the window."""
        padding = 12
        margin  = 22
        max_text_w = self.width - margin * 2 - padding * 2
        bx = margin
        by = 10

        # Word-wrap
        words = text.split()
        lines: list[str] = []
        current_line: list[str] = []

        for word in words:
            test = " ".join(current_line + [word])
            if font.size(test)[0] <= max_text_w:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        if not lines:
            return

        line_height = font.get_linesize() + 2
        bw = self.width - margin * 2
        bh = len(lines) * line_height + padding * 2

        # Bubble body
        bubble_rect = pygame.Rect(bx, by, bw, bh)
        pygame.draw.rect(screen, _BUBBLE_BG,     bubble_rect, border_radius=12)
        pygame.draw.rect(screen, _BUBBLE_BORDER, bubble_rect, width=2, border_radius=12)

        # Tail triangle pointing down toward cat center
        tail_cx = self.width // 2
        tail_top = by + bh

        pygame.draw.polygon(
            screen,
            _BUBBLE_TAIL,
            [
                (tail_cx - 9, tail_top),
                (tail_cx + 9, tail_top),
                (tail_cx,     tail_top + 13),
            ],
        )
        # Tail border lines (left and right sides only — not the closing base)
        pygame.draw.line(screen, _BUBBLE_BORDER, (tail_cx - 9, tail_top),  (tail_cx, tail_top + 13), 2)
        pygame.draw.line(screen, _BUBBLE_BORDER, (tail_cx + 9, tail_top),  (tail_cx, tail_top + 13), 2)

        # Text
        for i, line in enumerate(lines):
            surf = font.render(line, True, _BUBBLE_TEXT)
            screen.blit(surf, (bx + padding, by + padding + i * line_height))
