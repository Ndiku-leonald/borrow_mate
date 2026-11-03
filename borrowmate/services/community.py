"""Community: one object that wires the whole system together.

The CLI (and tests) talk to a Community, which owns the hostels, the
people, the inventory and the loan manager (composition).
"""

from typing import List, Optional

from borrowmate.exceptions import ValidationError
from borrowmate.models.hostel import Hostel
from borrowmate.models.person import Admin, Person, Student
from borrowmate.services.clock import Clock, SystemClock
from borrowmate.services.inventory import Inventory
from borrowmate.services.loan_manager import LoanManager
from borrowmate.services.notifier import InAppNotifier
from borrowmate.services.repository import IdGenerator, Repository


class Community:
    """The whole BorrowMate system for one campus."""

    def __init__(self, clock: Optional[Clock] = None):
        self.clock = clock or SystemClock()
        self.notifier = InAppNotifier()
        self.hostels: Repository[Hostel] = Repository("Hostel")
        self.people: Repository[Person] = Repository("User")
        self.inventory = Inventory()
        self.loans = LoanManager(self.inventory, self.clock, self.notifier)
        self._hostel_ids = IdGenerator("H")
        self._user_ids = IdGenerator("U")

    def add_hostel(self, name: str, latitude: float, longitude: float) -> Hostel:
        return self.hostels.add(Hostel(self._hostel_ids.next(), name, latitude, longitude))

    def register_student(self, full_name: str, email: str, hostel: Hostel,
                         reliability: float = 3.0) -> Student:
        self._ensure_unique_email(email)
        return self.people.add(Student(self._user_ids.next(), full_name, email, hostel,
                                       reliability))  # type: ignore[return-value]

    def register_admin(self, full_name: str, email: str, hostel: Hostel) -> Admin:
        self._ensure_unique_email(email)
        return self.people.add(Admin(self._user_ids.next(), full_name, email,
                                     hostel))  # type: ignore[return-value]

    def students(self) -> List[Student]:
        return [p for p in self.people if isinstance(p, Student)]

    def _ensure_unique_email(self, email: str) -> None:
        if self.people.first(lambda p: p.email == email.strip().lower()):
            raise ValidationError(f"'{email}' is already registered.")
