"""Extension requests and ratings: what happens around a loan.

ExtensionRequest: a borrower asks the owner for more time.
Rating: after a loan is returned, each side can rate the other once.
"""

from datetime import datetime, timedelta
from enum import Enum

from borrowmate.exceptions import InvalidTransitionError, ValidationError
from borrowmate.models.loan import Loan
from borrowmate.models.person import Person


class ExtensionStatus(Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    DECLINED = "Declined"


class ExtensionRequest:
    """A request to move a loan's return time later."""

    MAX_EXTRA_HOURS = 24

    def __init__(self, request_id: str, loan: Loan, extra_hours: int, asked_at: datetime,
                 reason: str = ""):
        if not 1 <= extra_hours <= self.MAX_EXTRA_HOURS:
            raise ValidationError(
                f"You can ask for between 1 and {self.MAX_EXTRA_HOURS} extra hours.")
        self._id = request_id
        self._loan = loan
        self._extra_hours = extra_hours
        self._asked_at = asked_at
        self._reason = reason.strip()
        self._status = ExtensionStatus.PENDING

    @property
    def id(self) -> str:
        return self._id

    @property
    def loan(self) -> Loan:
        return self._loan

    @property
    def extra_hours(self) -> int:
        return self._extra_hours

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def status(self) -> ExtensionStatus:
        return self._status

    @property
    def proposed_due(self) -> datetime:
        return self._loan.due_at + timedelta(hours=self._extra_hours)

    def approve(self) -> None:
        self._decide(ExtensionStatus.APPROVED)

    def decline(self) -> None:
        self._decide(ExtensionStatus.DECLINED)

    def _decide(self, outcome: ExtensionStatus) -> None:
        if self._status != ExtensionStatus.PENDING:
            raise InvalidTransitionError(f"Extension {self._id} was already {self._status.value.lower()}.")
        self._status = outcome

    def __str__(self) -> str:
        return (f"Extension {self._id}: +{self._extra_hours}h on '{self._loan.item.title}' "
                f"[{self._status.value}]")


class Rating:
    """One person's 1-5 star rating of the other person in a finished loan."""

    def __init__(self, loan: Loan, rater: Person, ratee: Person, score: int, comment: str = ""):
        if not 1 <= score <= 5:
            raise ValidationError("A rating must be between 1 and 5 stars.")
        if rater is ratee:
            raise ValidationError("You cannot rate yourself.")
        self._loan = loan
        self._rater = rater
        self._ratee = ratee
        self._score = score
        self._comment = comment.strip()

    @property
    def loan(self) -> Loan:
        return self._loan

    @property
    def rater(self) -> Person:
        return self._rater

    @property
    def ratee(self) -> Person:
        return self._ratee

    @property
    def score(self) -> int:
        return self._score

    @property
    def comment(self) -> str:
        return self._comment

    def stars(self) -> str:
        return "*" * self._score + "-" * (5 - self._score)
