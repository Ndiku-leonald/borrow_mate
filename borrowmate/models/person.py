"""People who use BorrowMate.

OOP concepts shown here:
- Abstraction: Person is an abstract base class; you cannot create a bare Person.
- Inheritance: Student and Admin both extend Person.
- Encapsulation: state lives in private attributes; changes go through
  methods that enforce the rules (e.g. reliability stays between 0 and 5).
- Polymorphism: role(), can_moderate() and max_active_loans() behave
  differently depending on the concrete class.
"""

from abc import ABC, abstractmethod

from borrowmate.exceptions import ValidationError
from borrowmate.models.enums import ValueTier
from borrowmate.models.hostel import Hostel


class Person(ABC):
    """Abstract base for anyone with a BorrowMate account."""

    def __init__(self, person_id: str, full_name: str, email: str, hostel: Hostel):
        if not full_name or not full_name.strip():
            raise ValidationError("Name cannot be empty.")
        if "@" not in email:
            raise ValidationError(f"'{email}' is not a valid email address.")
        self._id = person_id
        self._full_name = full_name.strip()
        self._email = email.strip().lower()
        self._hostel = hostel
        self._suspended = False

    # --- read-only properties (encapsulation) ---------------------------
    @property
    def id(self) -> str:
        return self._id

    @property
    def full_name(self) -> str:
        return self._full_name

    @property
    def email(self) -> str:
        return self._email

    @property
    def hostel(self) -> Hostel:
        return self._hostel

    @property
    def is_suspended(self) -> bool:
        return self._suspended

    # --- behaviour --------------------------------------------------------
    def move_to(self, hostel: Hostel) -> None:
        """Change the hostel this person lives in."""
        self._hostel = hostel

    def suspend(self) -> None:
        self._suspended = True

    def restore(self) -> None:
        self._suspended = False

    # --- polymorphic interface ---------------------------------------------
    @abstractmethod
    def role(self) -> str:
        """Human-readable role name."""

    @abstractmethod
    def can_moderate(self) -> bool:
        """Whether this person may resolve disputes and suspend users."""

    @abstractmethod
    def max_active_loans(self) -> int:
        """How many items this person may hold at once."""

    def __str__(self) -> str:
        return f"{self._full_name} ({self.role()}, {self._hostel})"

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._id!r}, {self._full_name!r})"


class Student(Person):
    """A student who can borrow and lend items.

    Trust ladder: reliability rises with on-time returns and falls with late
    ones. New students start at 3.0 and may only borrow LOW value items until
    they have proved themselves.
    """

    _MIN_SCORE = 0.0
    _MAX_SCORE = 5.0

    def __init__(self, person_id: str, full_name: str, email: str, hostel: Hostel,
                 reliability: float = 3.0):
        super().__init__(person_id, full_name, email, hostel)
        self._reliability = self._clamp(reliability)
        self._completed_loans = 0
        self._late_returns = 0

    @property
    def reliability(self) -> float:
        return round(self._reliability, 2)

    @property
    def completed_loans(self) -> int:
        return self._completed_loans

    @property
    def late_returns(self) -> int:
        return self._late_returns

    def record_return(self, on_time: bool) -> None:
        """Update the trust score after a loan is closed."""
        self._completed_loans += 1
        if on_time:
            self._reliability = self._clamp(self._reliability + 0.2)
        else:
            self._late_returns += 1
            self._reliability = self._clamp(self._reliability - 0.5)

    def max_value_tier(self) -> ValueTier:
        """Highest value tier this student is trusted to borrow."""
        if self._reliability >= 4.0 and self._completed_loans >= 5:
            return ValueTier.HIGH
        if self._reliability >= 3.0 and self._completed_loans >= 2:
            return ValueTier.MEDIUM
        return ValueTier.LOW

    def role(self) -> str:
        return "Student"

    def can_moderate(self) -> bool:
        return False

    def max_active_loans(self) -> int:
        return 3 if self._completed_loans >= 2 else 1

    @classmethod
    def _clamp(cls, value: float) -> float:
        return max(cls._MIN_SCORE, min(cls._MAX_SCORE, value))


class Admin(Person):
    """A moderator. Admins manage the community and do not borrow."""

    def role(self) -> str:
        return "Admin"

    def can_moderate(self) -> bool:
        return True

    def max_active_loans(self) -> int:
        return 0
