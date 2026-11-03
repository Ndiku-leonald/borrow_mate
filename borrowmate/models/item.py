"""Items that students can lend.

OOP concepts shown here:
- Abstraction: Item is abstract; every real item is a specific kind.
- Inheritance: Electronics, Book and HouseholdItem extend Item.
- Polymorphism: category(), value_tier(), default_max_hours() and
  details() give different answers per subclass, and the rest of the
  system calls them without knowing which subclass it has.
- Encapsulation: status can only change through pause(), resume(),
  mark_on_loan() and mark_returned(), which enforce the rules.
"""

from abc import ABC, abstractmethod
from typing import Optional

from borrowmate.exceptions import ItemNotAvailableError, ValidationError
from borrowmate.models.enums import Condition, ItemStatus, ValueTier
from borrowmate.models.person import Student


class Item(ABC):
    """Abstract base for anything that can be lent."""

    def __init__(self, item_id: str, title: str, owner: Student,
                 condition: Condition = Condition.GOOD,
                 max_hours: Optional[int] = None):
        if not title or not title.strip():
            raise ValidationError("Item title cannot be empty.")
        self._id = item_id
        self._title = title.strip()
        self._owner = owner
        self._condition = condition
        self._status = ItemStatus.AVAILABLE
        limit = max_hours if max_hours is not None else self.default_max_hours()
        if limit <= 0:
            raise ValidationError("Maximum borrowing hours must be positive.")
        self._max_hours = limit

    # --- read-only properties ---------------------------------------------
    @property
    def id(self) -> str:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    @property
    def owner(self) -> Student:
        return self._owner

    @property
    def condition(self) -> Condition:
        return self._condition

    @property
    def status(self) -> ItemStatus:
        return self._status

    @property
    def max_hours(self) -> int:
        return self._max_hours

    @property
    def is_available(self) -> bool:
        return self._status == ItemStatus.AVAILABLE

    # --- state changes (guarded) -------------------------------------------
    def pause(self) -> None:
        """Owner takes the item off the market. Not allowed while on loan."""
        if self._status == ItemStatus.ON_LOAN:
            raise ItemNotAvailableError(f"'{self._title}' is on loan and cannot be paused.")
        self._status = ItemStatus.PAUSED

    def resume(self) -> None:
        if self._status != ItemStatus.PAUSED:
            raise ItemNotAvailableError(f"'{self._title}' is not paused.")
        self._status = ItemStatus.AVAILABLE

    def mark_on_loan(self) -> None:
        if self._status != ItemStatus.AVAILABLE:
            raise ItemNotAvailableError(f"'{self._title}' is {self._status.value.lower()}.")
        self._status = ItemStatus.ON_LOAN

    def mark_returned(self, condition: Condition) -> None:
        if self._status != ItemStatus.ON_LOAN:
            raise ItemNotAvailableError(f"'{self._title}' is not on loan.")
        self._condition = condition
        self._status = ItemStatus.AVAILABLE

    # --- polymorphic interface ---------------------------------------------
    @abstractmethod
    def category(self) -> str:
        """Display name of the item's category."""

    @abstractmethod
    def value_tier(self) -> ValueTier:
        """Value tier used by the trust ladder."""

    @abstractmethod
    def default_max_hours(self) -> int:
        """Default longest loan for this kind of item."""

    @abstractmethod
    def details(self) -> str:
        """Category-specific extra information."""

    def summary(self) -> str:
        return (f"[{self._id}] {self._title} - {self.category()}, "
                f"{self._condition.value}, owner {self._owner.full_name} "
                f"({self._owner.hostel})")

    def __str__(self) -> str:
        return self.summary()

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._id!r}, {self._title!r})"


class Electronics(Item):
    """Calculators, chargers, extension cables, irons..."""

    def __init__(self, item_id: str, title: str, owner: Student, brand: str = "",
                 needs_power: bool = True, high_value: bool = False, **kwargs):
        self._high_value = high_value  # needed by value_tier() during __init__
        super().__init__(item_id, title, owner, **kwargs)
        self._brand = brand
        self._needs_power = needs_power

    def category(self) -> str:
        return "Electronics"

    def value_tier(self) -> ValueTier:
        return ValueTier.HIGH if self._high_value else ValueTier.MEDIUM

    def default_max_hours(self) -> int:
        return 24

    def details(self) -> str:
        power = "needs power" if self._needs_power else "battery/no power"
        brand = self._brand or "unbranded"
        return f"{brand}, {power}"


class Book(Item):
    """Textbooks and course readers."""

    def __init__(self, item_id: str, title: str, owner: Student, author: str = "",
                 course_unit: str = "", **kwargs):
        super().__init__(item_id, title, owner, **kwargs)
        self._author = author
        self._course_unit = course_unit

    @property
    def course_unit(self) -> str:
        return self._course_unit

    def category(self) -> str:
        return "Book"

    def value_tier(self) -> ValueTier:
        return ValueTier.LOW

    def default_max_hours(self) -> int:
        return 72

    def details(self) -> str:
        author = self._author or "unknown author"
        unit = f", for {self._course_unit}" if self._course_unit else ""
        return f"by {author}{unit}"


class HouseholdItem(Item):
    """Buckets, umbrellas, screwdrivers, basins..."""

    def category(self) -> str:
        return "Household"

    def value_tier(self) -> ValueTier:
        return ValueTier.LOW

    def default_max_hours(self) -> int:
        return 6

    def details(self) -> str:
        return "everyday item"
