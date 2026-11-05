"""Loan: the accountability record of one borrowing.

A loan is a small state machine. The _TRANSITIONS table lists every legal
move; anything else raises InvalidTransitionError. Because status is private
and only changes through _move_to(), no code can put a loan into an
impossible state (encapsulation protecting an invariant).

    REQUESTED -> ACCEPTED -> HANDED_OVER -> RETURNED
        |            |            |
        |            |            +-> OVERDUE -> RETURNED
        |            |                   |
        v            v                   v
    DECLINED     CANCELLED           DISPUTED -> RETURNED
"""

from datetime import datetime, timedelta
from typing import Optional

from borrowmate.exceptions import InvalidTransitionError, ValidationError
from borrowmate.models.enums import Condition, LoanStatus
from borrowmate.models.item import Item
from borrowmate.models.person import Student

_TRANSITIONS = {
    LoanStatus.REQUESTED: {LoanStatus.ACCEPTED, LoanStatus.DECLINED, LoanStatus.CANCELLED},
    LoanStatus.ACCEPTED: {LoanStatus.HANDED_OVER, LoanStatus.CANCELLED},
    LoanStatus.HANDED_OVER: {LoanStatus.RETURNED, LoanStatus.OVERDUE, LoanStatus.DISPUTED},
    LoanStatus.OVERDUE: {LoanStatus.RETURNED, LoanStatus.DISPUTED, LoanStatus.HANDED_OVER},
    LoanStatus.DISPUTED: {LoanStatus.RETURNED},
    LoanStatus.RETURNED: set(),
    LoanStatus.DECLINED: set(),
    LoanStatus.CANCELLED: set(),
}


class Loan:
    """One borrowing of one item by one student for an agreed time window."""

    def __init__(self, loan_id: str, item: Item, borrower: Student,
                 start_at: datetime, hours: int):
        if hours <= 0:
            raise ValidationError("Borrowing time must be at least 1 hour.")
        if hours > item.max_hours:
            raise ValidationError(
                f"'{item.title}' can be borrowed for at most {item.max_hours} hours.")
        if borrower is item.owner:
            raise ValidationError("You cannot borrow your own item.")
        self._id = loan_id
        self._item = item
        self._borrower = borrower
        self._start_at = start_at
        self._due_at = start_at + timedelta(hours=hours)
        self._status = LoanStatus.REQUESTED
        self._handed_over_at: Optional[datetime] = None
        self._returned_at: Optional[datetime] = None
        self._condition_out: Optional[Condition] = None
        self._condition_in: Optional[Condition] = None
        self._dispute_reason: Optional[str] = None

    # --- read-only properties ---------------------------------------------
    @property
    def id(self) -> str:
        return self._id

    @property
    def item(self) -> Item:
        return self._item

    @property
    def borrower(self) -> Student:
        return self._borrower

    @property
    def lender(self) -> Student:
        return self._item.owner

    @property
    def start_at(self) -> datetime:
        return self._start_at

    @property
    def due_at(self) -> datetime:
        return self._due_at

    @property
    def status(self) -> LoanStatus:
        return self._status

    @property
    def handed_over_at(self) -> Optional[datetime]:
        return self._handed_over_at

    @property
    def returned_at(self) -> Optional[datetime]:
        return self._returned_at

    @property
    def condition_in(self) -> Optional[Condition]:
        return self._condition_in

    @property
    def dispute_reason(self) -> Optional[str]:
        return self._dispute_reason

    # --- state machine ------------------------------------------------------
    def _move_to(self, new_status: LoanStatus) -> None:
        if new_status not in _TRANSITIONS[self._status]:
            raise InvalidTransitionError(
                f"Loan {self._id} cannot go from {self._status.value} to {new_status.value}.")
        self._status = new_status

    def accept(self) -> None:
        self._move_to(LoanStatus.ACCEPTED)

    def decline(self) -> None:
        self._move_to(LoanStatus.DECLINED)

    def cancel(self) -> None:
        self._move_to(LoanStatus.CANCELLED)

    def hand_over(self, at: datetime) -> None:
        """Both parties confirm the item changed hands."""
        self._move_to(LoanStatus.HANDED_OVER)
        self._item.mark_on_loan()
        self._handed_over_at = at
        self._condition_out = self._item.condition

    def mark_overdue(self) -> None:
        self._move_to(LoanStatus.OVERDUE)

    def raise_dispute(self, reason: str) -> None:
        if not reason or not reason.strip():
            raise ValidationError("Please describe the problem.")
        self._move_to(LoanStatus.DISPUTED)
        self._dispute_reason = reason.strip()

    def complete_return(self, at: datetime, condition: Condition) -> bool:
        """Lender confirms the item is back. Returns True if it was on time."""
        self._move_to(LoanStatus.RETURNED)
        self._item.mark_returned(condition)
        self._returned_at = at
        self._condition_in = condition
        return at <= self._due_at

    def extend_to(self, new_due: datetime, now: datetime) -> None:
        """Move the return deadline later (after the owner approves).

        An overdue loan whose new deadline is in the future goes back to
        HANDED_OVER, so the borrower is no longer treated as late.
        """
        if self._status not in (LoanStatus.HANDED_OVER, LoanStatus.OVERDUE):
            raise InvalidTransitionError(
                f"Only a loan that is out with the borrower can be extended "
                f"(loan {self._id} is {self._status.value}).")
        if new_due <= self._due_at:
            raise ValidationError("The new return time must be later than the current one.")
        self._due_at = new_due
        if self._status == LoanStatus.OVERDUE and new_due > now:
            self._move_to(LoanStatus.HANDED_OVER)

    # --- queries ------------------------------------------------------------
    def overlaps(self, other: "Loan") -> bool:
        """True if both loans are for the same item and their windows overlap."""
        if other is self or other.item is not self._item:
            return False
        return self._start_at < other.due_at and other.start_at < self._due_at

    def is_past_due(self, now: datetime) -> bool:
        return self._status in (LoanStatus.HANDED_OVER, LoanStatus.OVERDUE) and now > self._due_at

    def time_left(self, now: datetime) -> timedelta:
        return self._due_at - now

    def __str__(self) -> str:
        return (f"Loan {self._id}: {self._item.title} -> {self._borrower.full_name} "
                f"[{self._status.value}] due {self._due_at:%a %d %b %H:%M}")

    def __repr__(self) -> str:
        return f"Loan({self._id!r}, {self._item.id!r}, {self._status.name})"
