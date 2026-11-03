"""LoanManager: the rules of borrowing.

It decides who may borrow what, detects conflicts between bookings,
moves loans through their states, flags overdue items and tells people
what happened. It depends on the Clock and Notifier *interfaces*, not
on concrete classes, so either can be swapped.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from borrowmate.exceptions import (BookingConflictError, ItemNotAvailableError,
                                   NotEligibleError, PermissionDeniedError)
from borrowmate.models.enums import Condition, ItemStatus, LoanStatus
from borrowmate.models.item import Item
from borrowmate.models.loan import Loan
from borrowmate.models.person import Person, Student
from borrowmate.services.clock import Clock
from borrowmate.services.inventory import Inventory
from borrowmate.services.notifier import Notifier
from borrowmate.services.repository import IdGenerator, Repository


@dataclass(frozen=True)
class Conflict:
    """Two bookings of the same item whose time windows overlap."""

    item: Item
    first: Loan
    second: Loan

    @property
    def severity(self) -> str:
        if self.first.status.is_active and self.second.status.is_active:
            return "CLASH"        # should never happen; flagged loudly if it does
        if self.first.status.is_active or self.second.status.is_active:
            return "BLOCKED"      # a request overlaps a confirmed booking
        return "COMPETING"        # two pending requests want the same slot

    def describe(self) -> str:
        return (f"{self.item.title}: {self.first.borrower.full_name} "
                f"({self.first.status.value}, {self.first.start_at:%d %b %H:%M}-"
                f"{self.first.due_at:%H:%M}) vs {self.second.borrower.full_name} "
                f"({self.second.status.value}, {self.second.start_at:%d %b %H:%M}-"
                f"{self.second.due_at:%H:%M})")


class LoanManager:
    """Applies BorrowMate's borrowing rules."""

    def __init__(self, inventory: Inventory, clock: Clock, notifier: Notifier):
        self._inventory = inventory
        self._clock = clock
        self._notifier = notifier
        self._loans: Repository[Loan] = Repository("Loan")
        self._ids = IdGenerator("L")

    # --- eligibility ---------------------------------------------------------
    def check_eligibility(self, borrower: Person, item: Item) -> None:
        """Raise NotEligibleError/ItemNotAvailableError explaining why not."""
        if not isinstance(borrower, Student):
            raise NotEligibleError(f"{borrower.role()} accounts cannot borrow items.")
        if borrower.is_suspended:
            raise NotEligibleError("Your account is suspended.")
        if item.owner is borrower:
            raise NotEligibleError("You cannot borrow your own item.")
        if item.status in (ItemStatus.PAUSED, ItemStatus.REMOVED):
            raise ItemNotAvailableError(f"'{item.title}' is {item.status.value.lower()}.")
        if self.overdue_loans(borrower):
            raise NotEligibleError("Return your overdue item before borrowing again.")
        if len(self.active_loans_of(borrower)) >= borrower.max_active_loans():
            raise NotEligibleError(
                f"You can hold at most {borrower.max_active_loans()} item(s) at a time.")
        if item.value_tier().value > borrower.max_value_tier().value:
            raise NotEligibleError(
                f"'{item.title}' is a {item.value_tier().name} value item. Complete more "
                f"on-time returns to unlock it (current limit: {borrower.max_value_tier().name}).")

    def is_eligible(self, borrower: Person, item: Item) -> bool:
        try:
            self.check_eligibility(borrower, item)
            return True
        except (NotEligibleError, ItemNotAvailableError):
            return False

    # --- creating and deciding requests ------------------------------------
    def request(self, borrower: Person, item_id: str, hours: int,
                start_at: Optional[datetime] = None) -> Loan:
        """Borrower asks to borrow an item from start_at (default: now)."""
        item = self._inventory.get(item_id)
        self.check_eligibility(borrower, item)
        start = start_at or self._clock.now()
        if start < self._clock.now():
            raise NotEligibleError("The start time cannot be in the past.")
        loan = Loan(self._ids.next(), item, borrower, start, hours)  # type: ignore[arg-type]
        blocking = self._blocking_loan(loan)
        if blocking is not None:
            raise BookingConflictError(
                f"'{item.title}' is already booked until {blocking.due_at:%a %d %b %H:%M}. "
                f"Try a start time after that.")
        self._loans.add(loan)
        self._tell(item.owner, f"{borrower.full_name} wants to borrow '{item.title}' "
                               f"({loan.start_at:%d %b %H:%M} - {loan.due_at:%d %b %H:%M}). "
                               f"Loan {loan.id}.")
        return loan

    def accept(self, lender: Person, loan_id: str) -> Loan:
        loan = self._loans.get(loan_id)
        self._require_lender(lender, loan)
        blocking = self._blocking_loan(loan)
        if blocking is not None:
            raise BookingConflictError(
                f"Loan {loan.id} overlaps loan {blocking.id}, which is already confirmed.")
        loan.accept()
        self._tell(loan.borrower, f"{lender.full_name} accepted your request for "
                                  f"'{loan.item.title}'. Collect it from {lender.hostel}.")
        for rival in self._competing_requests(loan):
            rival.decline()
            self._tell(rival.borrower, f"Your request for '{rival.item.title}' was declined: "
                                       f"the slot was given to another borrower.")
        return loan

    def decline(self, lender: Person, loan_id: str) -> Loan:
        loan = self._loans.get(loan_id)
        self._require_lender(lender, loan)
        loan.decline()
        self._tell(loan.borrower, f"Your request for '{loan.item.title}' was declined.")
        return loan

    def cancel(self, actor: Person, loan_id: str) -> Loan:
        loan = self._loans.get(loan_id)
        if actor is not loan.borrower and actor is not loan.lender:
            raise PermissionDeniedError("Only the borrower or lender can cancel this loan.")
        loan.cancel()
        other = loan.lender if actor is loan.borrower else loan.borrower
        self._tell(other, f"Loan {loan.id} for '{loan.item.title}' was cancelled.")
        return loan

    # --- handover and return ----------------------------------------------
    def hand_over(self, lender: Person, loan_id: str) -> Loan:
        loan = self._loans.get(loan_id)
        self._require_lender(lender, loan)
        if loan.item.status != ItemStatus.AVAILABLE:
            raise ItemNotAvailableError(
                f"'{loan.item.title}' is {loan.item.status.value.lower()}; it cannot be handed over yet.")
        loan.hand_over(self._clock.now())
        self._tell(loan.borrower, f"You now have '{loan.item.title}'. "
                                  f"Return it by {loan.due_at:%a %d %b %H:%M}.")
        return loan

    def confirm_return(self, lender: Person, loan_id: str,
                       condition: Condition = Condition.GOOD) -> Loan:
        """Only the lender can close a loan, so a borrower cannot fake a return."""
        loan = self._loans.get(loan_id)
        self._require_lender(lender, loan)
        on_time = loan.complete_return(self._clock.now(), condition)
        loan.borrower.record_return(on_time)
        note = "on time" if on_time else "late"
        self._tell(loan.borrower, f"Return of '{loan.item.title}' confirmed ({note}, "
                                  f"condition: {condition.value}).")
        return loan

    def raise_dispute(self, actor: Person, loan_id: str, reason: str) -> Loan:
        loan = self._loans.get(loan_id)
        if actor is not loan.borrower and actor is not loan.lender:
            raise PermissionDeniedError("Only people involved in this loan can dispute it.")
        loan.raise_dispute(reason)
        other = loan.lender if actor is loan.borrower else loan.borrower
        self._tell(other, f"{actor.full_name} reported a problem with loan {loan.id}: {reason}")
        return loan

    def refresh_overdue(self) -> List[Loan]:
        """Mark loans past their due time as overdue and remind both sides."""
        now = self._clock.now()
        flagged = []
        for loan in self._loans.find(lambda l: l.status == LoanStatus.HANDED_OVER):
            if loan.is_past_due(now):
                loan.mark_overdue()
                flagged.append(loan)
                self._tell(loan.borrower, f"'{loan.item.title}' was due "
                                          f"{loan.due_at:%a %d %b %H:%M}. Please return it or "
                                          f"talk to {loan.lender.full_name}.")
                self._tell(loan.lender, f"'{loan.item.title}' is overdue from "
                                        f"{loan.borrower.full_name}.")
        return flagged

    # --- reports -----------------------------------------------------------
    def get(self, loan_id: str) -> Loan:
        return self._loans.get(loan_id)

    def all_loans(self) -> List[Loan]:
        return self._loans.all()

    def taken_loans(self) -> List[Loan]:
        """Items currently out with a borrower, soonest due first."""
        out = self._loans.find(lambda l: l.status in (LoanStatus.HANDED_OVER,
                                                       LoanStatus.OVERDUE,
                                                       LoanStatus.DISPUTED))
        return sorted(out, key=lambda l: l.due_at)

    def upcoming_loans(self) -> List[Loan]:
        """Accepted bookings waiting for handover."""
        return sorted(self._loans.find(lambda l: l.status == LoanStatus.ACCEPTED),
                      key=lambda l: l.start_at)

    def pending_for(self, lender: Person) -> List[Loan]:
        return self._loans.find(lambda l: l.status == LoanStatus.REQUESTED and l.lender is lender)

    def loans_of(self, person: Person) -> List[Loan]:
        return self._loans.find(lambda l: person in (l.borrower, l.lender))

    def active_loans_of(self, borrower: Person) -> List[Loan]:
        return self._loans.find(lambda l: l.borrower is borrower and l.status.is_active)

    def overdue_loans(self, borrower: Optional[Person] = None) -> List[Loan]:
        now = self._clock.now()
        return self._loans.find(lambda l: l.is_past_due(now)
                                and (borrower is None or l.borrower is borrower))

    def disputes(self) -> List[Loan]:
        return self._loans.find(lambda l: l.status == LoanStatus.DISPUTED)

    def conflicts(self) -> List[Conflict]:
        """Every pair of open bookings for the same item with overlapping times."""
        open_loans = [l for l in self._loans.all()
                      if l.status == LoanStatus.REQUESTED or l.status.is_active]
        found = []
        for index, first in enumerate(open_loans):
            for second in open_loans[index + 1:]:
                if first.overlaps(second):
                    found.append(Conflict(first.item, first, second))
        return found

    # --- helpers -------------------------------------------------------------
    def _blocking_loan(self, loan: Loan) -> Optional[Loan]:
        return self._loans.first(lambda other: other.status.is_active and loan.overlaps(other))

    def _competing_requests(self, loan: Loan) -> List[Loan]:
        return self._loans.find(lambda other: other.status == LoanStatus.REQUESTED
                                and loan.overlaps(other))

    @staticmethod
    def _require_lender(actor: Person, loan: Loan) -> None:
        if actor is not loan.lender:
            raise PermissionDeniedError("Only the item's owner can do that.")

    def _tell(self, person: Person, message: str) -> None:
        self._notifier.notify(person, message, self._clock.now())
