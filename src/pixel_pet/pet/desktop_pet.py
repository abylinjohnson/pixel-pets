import pygame
import win32gui
import win32con
import win32api
import os
import threading
import queue
import time


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

    def start(self):
        if self.thread and self.thread.is_alive():
            return

        self._stop_requested.clear()
        self.running = True
        self.thread = threading.Thread(
            target=self._run
        )
        self.thread.start()

    def stop(self, timeout=5):
        """
        Ask the pet window to close and wait for the pygame thread to finish.
        """
        if not self.thread or not self.thread.is_alive():
            self.running = False
            return

        self._stop_requested.set()
        self.command_queue.put({
            "type": "stop"
        })

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
        """
        Plays another animation for `duration` seconds,
        then automatically goes back to idle.
        """
        if not self.running:
            return

        self.command_queue.put({
            "type": "play",
            "path": asset_path,
            "duration": duration
        })

    def _load_frames(self, asset_path):
        frames = []

        for file in sorted(os.listdir(asset_path)):
            if file.endswith(".png"):
                img = pygame.image.load(
                    os.path.join(asset_path, file)
                ).convert_alpha()

                new_width = int(img.get_width() * self.scale)
                new_height = int(img.get_height() * self.scale)

                img = pygame.transform.scale(
                    img,
                    (new_width, new_height)
                )

                frames.append(img)

        return frames

    def _run(self):
        try:
            pygame.init()

            screen = pygame.display.set_mode(
                (self.width, self.height),
                pygame.NOFRAME
            )

            pygame.display.set_caption("Desktop Cat")

            transparent = (0, 0, 0)

            hwnd = pygame.display.get_wm_info()["window"]

            styles = win32gui.GetWindowLong(
                hwnd,
                win32con.GWL_EXSTYLE
            )

            win32gui.SetWindowLong(
                hwnd,
                win32con.GWL_EXSTYLE,
                styles | win32con.WS_EX_LAYERED
            )

            win32gui.SetLayeredWindowAttributes(
                hwnd,
                win32api.RGB(*transparent),
                0,
                win32con.LWA_COLORKEY
            )

            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                self.start_pos[0],
                self.start_pos[1],
                0,
                0,
                win32con.SWP_NOSIZE
            )

            frames = self._load_frames(self.idle_path)

            clock = pygame.time.Clock()

            frame = 0
            timer = 0

            dragging = False
            drag_offset_x = 0
            drag_offset_y = 0

            temporary_animation_end_time = None

            while self.running and not self._stop_requested.is_set():
                dt = clock.tick(120) / 1000

                while not self.command_queue.empty():
                    command = self.command_queue.get()

                    if command["type"] == "stop":
                        self.running = False

                    elif command["type"] == "play":
                        frames = self._load_frames(command["path"])
                        frame = 0
                        timer = 0
                        temporary_animation_end_time = (
                            time.time() + command["duration"]
                        )

                if temporary_animation_end_time:
                    if time.time() >= temporary_animation_end_time:
                        frames = self._load_frames(self.idle_path)
                        frame = 0
                        timer = 0
                        temporary_animation_end_time = None

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False

                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            self.running = False

                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:
                            dragging = True
                            mouse_x, mouse_y = pygame.mouse.get_pos()
                            drag_offset_x = mouse_x
                            drag_offset_y = mouse_y

                    if event.type == pygame.MOUSEBUTTONUP:
                        if event.button == 1:
                            dragging = False

                if dragging:
                    mouse_screen_x, mouse_screen_y = win32api.GetCursorPos()

                    win32gui.SetWindowPos(
                        hwnd,
                        win32con.HWND_TOPMOST,
                        mouse_screen_x - drag_offset_x,
                        mouse_screen_y - drag_offset_y,
                        0,
                        0,
                        win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
                    )

                timer += dt

                if timer > self.animation_speed:
                    timer = 0
                    frame = (frame + 1) % len(frames)

                screen.fill(transparent)

                current = frames[frame]

                rect = current.get_rect(
                    center=(self.width // 2, self.height // 2)
                )

                screen.blit(current, rect)

                pygame.display.update()
        finally:
            self.running = False
            self._stop_requested.set()
            pygame.quit()
