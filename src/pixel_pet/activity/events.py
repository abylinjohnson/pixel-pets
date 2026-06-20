from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ActivityEventType(str, Enum):
    ACTIVE_WINDOW_CHANGED = "active_window_changed"
    USER_IDLE = "user_idle"
    USER_ACTIVE = "user_active"
    USER_PRESENT = "user_present"
    USER_ABSENT = "user_absent"
    TRACKER_ERROR = "tracker_error"


@dataclass(frozen=True)
class ActivityEvent:
    event_type: ActivityEventType
    source: str
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    payload: dict = field(default_factory=dict)
