"""A small generic in-memory store.

Repository is generic over the type it stores, so the same class keeps
users, items and loans. Swapping it for a database later only means
writing another class with the same methods.
"""

from itertools import count
from typing import Callable, Dict, Generic, Iterator, List, Optional, TypeVar

from borrowmate.exceptions import NotFoundError, ValidationError

T = TypeVar("T")


class Repository(Generic[T]):
    """Stores objects by their .id attribute."""

    def __init__(self, label: str):
        self._label = label
        self._items: Dict[str, T] = {}

    def add(self, obj: T) -> T:
        key = obj.id  # type: ignore[attr-defined]
        if key in self._items:
            raise ValidationError(f"{self._label} '{key}' already exists.")
        self._items[key] = obj
        return obj

    def get(self, key: str) -> T:
        try:
            return self._items[key.strip().upper()]
        except KeyError:
            raise NotFoundError(f"No {self._label.lower()} with id '{key}'.") from None

    def find(self, predicate: Callable[[T], bool]) -> List[T]:
        return [obj for obj in self._items.values() if predicate(obj)]

    def first(self, predicate: Callable[[T], bool]) -> Optional[T]:
        return next((obj for obj in self._items.values() if predicate(obj)), None)

    def all(self) -> List[T]:
        return list(self._items.values())

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[T]:
        return iter(self._items.values())


class IdGenerator:
    """Produces readable ids such as I001, L001."""

    def __init__(self, prefix: str, start: int = 1):
        self._prefix = prefix
        self._counter = count(start)

    def next(self) -> str:
        return f"{self._prefix}{next(self._counter):03d}"
