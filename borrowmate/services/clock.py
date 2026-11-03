"""Clocks.

The rest of the system never calls datetime.now() directly; it asks a
Clock. That abstraction lets tests freeze time and lets the CLI demo
fast-forward to show overdue loans, without changing any business code.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta


class Clock(ABC):
    """Source of the current time."""

    @abstractmethod
    def now(self) -> datetime:
        """Return the current time."""


class SystemClock(Clock):
    """The real wall clock."""

    def now(self) -> datetime:
        return datetime.now().replace(second=0, microsecond=0)


class SimulatedClock(Clock):
    """A clock you can set and move forward (for tests and demos)."""

    def __init__(self, start: datetime):
        self._current = start

    def now(self) -> datetime:
        return self._current

    def advance(self, hours: float = 0, minutes: float = 0) -> datetime:
        if hours < 0 or minutes < 0:
            raise ValueError("Time can only move forward.")
        self._current += timedelta(hours=hours, minutes=minutes)
        return self._current
