"""Custom exception hierarchy.

Every BorrowMate error inherits from BorrowMateError, so the CLI can catch
one base type and show a friendly message, while tests can check for the
exact subclass. This is inheritance applied to errors.
"""


class BorrowMateError(Exception):
    """Base class for all BorrowMate errors."""


class ValidationError(BorrowMateError):
    """Raised when input data is invalid (empty name, negative hours...)."""


class NotFoundError(BorrowMateError):
    """Raised when an item, user or loan id does not exist."""


class ItemNotAvailableError(BorrowMateError):
    """Raised when an item is paused, removed or otherwise not lendable."""


class BookingConflictError(BorrowMateError):
    """Raised when a loan would overlap another active loan of the same item."""


class NotEligibleError(BorrowMateError):
    """Raised when a borrower is not allowed to borrow a given item."""


class PermissionDeniedError(BorrowMateError):
    """Raised when a user tries an action reserved for someone else."""


class InvalidTransitionError(BorrowMateError):
    """Raised when a loan is moved to a state its current state forbids."""
