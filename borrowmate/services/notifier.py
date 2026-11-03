"""Notifications.

Notifier is an abstract interface. InAppNotifier keeps an inbox per user
for the CLI; later the team can add SmsNotifier or PushNotifier without
touching LoanManager, which only knows about the Notifier interface.
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple

from borrowmate.models.person import Person


class Notifier(ABC):
    """Anything that can deliver a message to a person."""

    @abstractmethod
    def notify(self, person: Person, message: str, at: datetime) -> None:
        """Deliver a message."""


class InAppNotifier(Notifier):
    """Stores messages so a user can read them when they log in."""

    def __init__(self) -> None:
        self._inbox: Dict[str, List[Tuple[datetime, str]]] = defaultdict(list)

    def notify(self, person: Person, message: str, at: datetime) -> None:
        self._inbox[person.id].append((at, message))

    def inbox(self, person: Person) -> List[Tuple[datetime, str]]:
        return list(self._inbox[person.id])

    def clear(self, person: Person) -> None:
        self._inbox[person.id].clear()
