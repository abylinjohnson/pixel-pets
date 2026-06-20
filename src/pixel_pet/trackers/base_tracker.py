from abc import ABC, abstractmethod


class BaseTracker(ABC):
    name = "base_tracker"

    @abstractmethod
    def poll(self):
        """Return a list of activity events captured during this poll."""
        raise NotImplementedError
