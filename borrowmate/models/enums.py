"""Enumerations shared across the BorrowMate domain.

Using Enum instead of raw strings means an invalid status can never be
stored by accident (e.g. "returnd" instead of "RETURNED").
"""

from enum import Enum


class ItemStatus(Enum):
    """Where an item is in its lending life."""

    AVAILABLE = "Available"
    ON_LOAN = "On loan"
    PAUSED = "Paused by owner"
    REMOVED = "Removed"


class LoanStatus(Enum):
    """States of the loan state machine (see Loan for allowed transitions)."""

    REQUESTED = "Requested"
    ACCEPTED = "Accepted"
    HANDED_OVER = "Handed over"
    OVERDUE = "Overdue"
    RETURNED = "Returned"
    DECLINED = "Declined"
    CANCELLED = "Cancelled"
    DISPUTED = "Disputed"

    @property
    def is_active(self) -> bool:
        """True while the loan holds (or is about to hold) the item."""
        return self in (LoanStatus.ACCEPTED, LoanStatus.HANDED_OVER, LoanStatus.OVERDUE)

    @property
    def is_closed(self) -> bool:
        """True once the loan can no longer change."""
        return self in (LoanStatus.RETURNED, LoanStatus.DECLINED, LoanStatus.CANCELLED)


class ValueTier(Enum):
    """Rough value of an item; drives the trust ladder."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


class Condition(Enum):
    """Physical condition recorded at handover and at return."""

    NEW = "New"
    GOOD = "Good"
    FAIR = "Fair"
    DAMAGED = "Damaged"
