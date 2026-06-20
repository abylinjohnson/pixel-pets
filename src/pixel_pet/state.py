import threading


class FocusState:
    """Thread-safe session state shared between Flask and PetAiController."""

    _lock = threading.Lock()
    _active = False
    _task = ""
    _goal = ""
    _session_id = None

    @classmethod
    def set_session(cls, task: str, goal: str, session_id: int | None = None) -> None:
        with cls._lock:
            cls._active = True
            cls._task = task
            cls._goal = goal
            cls._session_id = session_id

    @classmethod
    def set_active(cls, active: bool) -> None:
        with cls._lock:
            cls._active = bool(active)
            if not active:
                cls._task = ""
                cls._goal = ""
                cls._session_id = None

    @classmethod
    def is_active(cls) -> bool:
        with cls._lock:
            return cls._active

    @classmethod
    def get_context(cls) -> dict:
        with cls._lock:
            return {
                "active": cls._active,
                "task": cls._task,
                "goal": cls._goal,
                "session_id": cls._session_id,
            }
