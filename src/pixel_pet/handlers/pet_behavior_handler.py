import threading
import time

from src.pixel_pet.pets import get_action_map, get_current_pet_profile


class PetBehaviorHandler:
    def __init__(self, pet, pet_key=None):
        self.pet = pet
        self.profile = (
            get_current_pet_profile()
            if pet_key is None
            else None
        )
        if pet_key is not None:
            from src.pixel_pet.pets import get_pet_profile
            self.profile = get_pet_profile(pet_key)

        self.action_map = get_action_map(self.profile.key)
        self.current_idle_action_key = self.profile.idle_action
        self._sequence_generation = 0
        self._sequence_lock = threading.Lock()

    def available_actions(self):
        return self.profile.actions

    def available_behaviors(self):
        return (
            "focus_idle",
            "focus_groom",
            "distraction_nudge",
            "return_greeting",
            "rest_settle",
            "sleep_sequence",
            "calm_meow",
        )

    def perform(self, action_key, duration=None, interrupt_sequence=True):
        if interrupt_sequence:
            self.stop_sequence()
        action = self.action_map.get(action_key)

        if not action:
            raise ValueError(f"Unknown pet action: {action_key}")

        if action.key == self.profile.idle_action:
            return self.set_idle()

        self.pet.play_animation(
            action.asset_path,
            duration=duration or action.duration,
        )

    def set_idle(self):
        idle_action = self.action_map[self.current_idle_action_key]
        self.pet.play_animation(
            idle_action.asset_path,
            duration=idle_action.duration,
        )

    def set_idle_action(self, action_key, switch_now=False):
        action = self.action_map.get(action_key)

        if not action:
            raise ValueError(f"Unknown idle action: {action_key}")

        self.current_idle_action_key = action_key
        self.pet.set_idle_animation(action.asset_path, switch_now=switch_now)

    def perform_behavior(self, behavior_key):
        if behavior_key == "focus_idle":
            self.set_idle_action("sit_idle_tail", switch_now=True)
            return

        if behavior_key == "focus_groom":
            self.set_idle_action("sit_idle_tail")
            self.perform("sit_licking")
            return

        if behavior_key == "distraction_nudge":
            self.set_idle_action("sit_idle_tail")
            self.perform("sit_tap_screen")
            return

        if behavior_key == "return_greeting":
            self.set_idle_action("sit_idle_tail")
            self.perform_sequence([
                ("sit_lookup_meow", None),
                ("sit_idle_tail", None),
            ])
            return

        if behavior_key == "rest_settle":
            self.set_idle_action("laydown_idle")
            self.perform_sequence([
                ("sit_yawning", None),
                ("laydown_idle", None),
            ])
            return

        if behavior_key == "sleep_sequence":
            self.set_idle_action("laydown_sleeping")
            self.perform_sequence([
                ("sit_yawning", None),
                ("laydown_idle", 4.0),
                ("laydown_sleeping", 180.0),
            ])
            return

        if behavior_key == "calm_meow":
            self.set_idle_action("laydown_idle")
            self.perform("laydown_meow")
            return

        raise ValueError(f"Unknown pet behavior: {behavior_key}")

    def perform_sequence(self, steps):
        with self._sequence_lock:
            self._sequence_generation += 1
            generation = self._sequence_generation

        thread = threading.Thread(
            target=self._run_sequence,
            args=(generation, steps),
            daemon=True,
        )
        thread.start()

    def stop_sequence(self):
        with self._sequence_lock:
            self._sequence_generation += 1

    def _run_sequence(self, generation, steps):
        for action_key, duration in steps:
            if not self._is_current_sequence(generation):
                return

            action = self.action_map[action_key]
            play_duration = duration or action.duration
            self.pet.play_animation(action.asset_path, duration=play_duration)
            self._sleep_with_cancellation(generation, play_duration)

        if self._is_current_sequence(generation):
            self.set_idle()

    def _is_current_sequence(self, generation):
        with self._sequence_lock:
            return generation == self._sequence_generation

    def _sleep_with_cancellation(self, generation, duration):
        deadline = time.time() + duration

        while time.time() < deadline:
            if not self._is_current_sequence(generation):
                return

            time.sleep(0.2)

    def show_speech(self, text: str, duration: float = 10.0) -> None:
        self.pet.show_speech_bubble(text, duration=duration)

    def react_to_focus(self):
        self.perform_behavior("focus_idle")

    def react_to_distraction(self):
        self.perform_behavior("distraction_nudge")

    def react_to_afk(self):
        self.perform_behavior("sleep_sequence")

    def react_to_return(self):
        self.perform_behavior("return_greeting")
