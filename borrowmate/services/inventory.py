"""Inventory: every item listed on BorrowMate, plus search.

Inventory is composed of a Repository (it *has a* store) rather than
inheriting from it, so it exposes only the operations that make sense
for items.
"""

from typing import List, Optional

from borrowmate.exceptions import ValidationError
from borrowmate.models.enums import Condition, ItemStatus
from borrowmate.models.hostel import Hostel
from borrowmate.models.item import Book, Electronics, HouseholdItem, Item
from borrowmate.models.person import Student
from borrowmate.services.repository import IdGenerator, Repository


class ItemFactory:
    """Creates the right Item subclass from a category name (factory pattern)."""

    _KINDS = {"electronics": Electronics, "book": Book, "household": HouseholdItem}

    @classmethod
    def kinds(cls) -> List[str]:
        return list(cls._KINDS)

    @classmethod
    def create(cls, kind: str, item_id: str, title: str, owner: Student,
               condition: Condition = Condition.GOOD, **extra) -> Item:
        item_class = cls._KINDS.get(kind.strip().lower())
        if item_class is None:
            raise ValidationError(f"Unknown category '{kind}'. Choose: {', '.join(cls._KINDS)}.")
        return item_class(item_id, title, owner, condition=condition, **extra)


class Inventory:
    """All listed items."""

    def __init__(self) -> None:
        self._items: Repository[Item] = Repository("Item")
        self._ids = IdGenerator("I")

    def next_id(self) -> str:
        return self._ids.next()

    def add(self, item: Item) -> Item:
        return self._items.add(item)

    def list_new(self, kind: str, title: str, owner: Student,
                 condition: Condition = Condition.GOOD, **extra) -> Item:
        """Create and list a new item for an owner."""
        return self.add(ItemFactory.create(kind, self.next_id(), title, owner, condition, **extra))

    def get(self, item_id: str) -> Item:
        return self._items.get(item_id)

    def all_items(self) -> List[Item]:
        """Every item that has not been removed."""
        return self._items.find(lambda i: i.status != ItemStatus.REMOVED)

    def items_of(self, owner: Student) -> List[Item]:
        return self._items.find(lambda i: i.owner is owner)

    def available(self, near: Optional[Hostel] = None,
                  radius_m: Optional[float] = None) -> List[Item]:
        """Available items, nearest first, optionally limited to a radius."""
        items = self._items.find(lambda i: i.is_available)
        if near is None:
            return items
        if radius_m is not None:
            items = [i for i in items if near.distance_to(i.owner.hostel) <= radius_m]
        return sorted(items, key=lambda i: near.distance_to(i.owner.hostel))

    def search(self, term: str) -> List[Item]:
        """Case-insensitive match on title or category."""
        needle = term.strip().lower()
        if not needle:
            return self.all_items()
        return [i for i in self.all_items()
                if needle in i.title.lower() or needle in i.category().lower()]
