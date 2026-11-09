"""Rules for loan extensions and ratings."""

from typing import Dict, List, Optional, Tuple

from borrowmate.exceptions import (BookingConflictError, NotEligibleError,
                                   PermissionDeniedError)
from borrowmate.models.enums import LoanStatus
from borrowmate.models.feedback import ExtensionRequest, ExtensionStatus, Rating
from borrowmate.models.loan import Loan
from borrowmate.models.person import Person
from borrowmate.services.community import Community
from borrowmate.services.repository import IdGenerator, Repository


class ExtensionManager:
    """Borrowers ask for more time; owners approve or decline."""

    def __init__(self, community: Community):
        self._c = community
        self._requests: Repository[ExtensionRequest] = Repository("Extension request")
        self._ids = IdGenerator("E")

    def request(self, borrower: Person, loan_id: str, extra_hours: int,
                reason: str = "") -> ExtensionRequest:
        loan = self._c.loans.get(loan_id)
        if borrower is not loan.borrower:
            raise PermissionDeniedError("Only the borrower can ask for more time.")
        if loan.status not in (LoanStatus.HANDED_OVER, LoanStatus.OVERDUE):
            raise NotEligibleError("You can only extend an item you currently have.")
        if self.pending_for_loan(loan):
            raise NotEligibleError("You already have an extension request waiting for an answer.")
        request = ExtensionRequest(self._ids.next(), loan, extra_hours, self._c.clock.now(), reason)
        self._check_no_clash(request)
        self._requests.add(request)
        self._tell(loan.lender, f"{borrower.full_name} asks to keep '{loan.item.title}' "
                                f"{extra_hours}h longer (until {request.proposed_due:%a %d %b %H:%M})."
                                f" Request {request.id}.")
        return request

    def approve(self, lender: Person, request_id: str) -> ExtensionRequest:
        request = self._owned_request(lender, request_id)
        self._check_no_clash(request)
        new_due = request.proposed_due
        request.loan.extend_to(new_due, self._c.clock.now())
        request.approve()
        self._tell(request.loan.borrower, f"Extension approved: return '{request.loan.item.title}' "
                                          f"by {new_due:%a %d %b %H:%M}.")
        return request

    def decline(self, lender: Person, request_id: str) -> ExtensionRequest:
        request = self._owned_request(lender, request_id)
        request.decline()
        self._tell(request.loan.borrower, f"Extension declined: please return "
                                          f"'{request.loan.item.title}' by "
                                          f"{request.loan.due_at:%a %d %b %H:%M}.")
        return request

    def pending_for_lender(self, lender: Person) -> List[ExtensionRequest]:
        return self._requests.find(lambda r: r.status == ExtensionStatus.PENDING
                                   and r.loan.lender is lender)

    def pending_for_loan(self, loan: Loan) -> List[ExtensionRequest]:
        return self._requests.find(lambda r: r.status == ExtensionStatus.PENDING and r.loan is loan)

    def history(self, person: Person) -> List[ExtensionRequest]:
        return self._requests.find(lambda r: person in (r.loan.borrower, r.loan.lender))

    def _owned_request(self, lender: Person, request_id: str) -> ExtensionRequest:
        request = self._requests.get(request_id)
        if lender is not request.loan.lender:
            raise PermissionDeniedError("Only the item's owner can answer this request.")
        return request

    def _check_no_clash(self, request: ExtensionRequest) -> None:
        """More time must not eat into someone else's confirmed booking."""
        loan = request.loan
        for other in self._c.loans.upcoming_loans():
            if other.item is loan.item and other.start_at < request.proposed_due:
                raise BookingConflictError(
                    f"'{loan.item.title}' is booked by {other.borrower.full_name} from "
                    f"{other.start_at:%a %d %b %H:%M}, so it cannot be kept that long.")

    def _tell(self, person: Person, message: str) -> None:
        self._c.notifier.notify(person, message, self._c.clock.now())


class RatingBook:
    """Stores ratings; each person may rate the other once per returned loan."""

    def __init__(self, community: Community):
        self._c = community
        self._ratings: Dict[Tuple[str, str], Rating] = {}

    def rate(self, rater: Person, loan_id: str, score: int, comment: str = "") -> Rating:
        loan = self._c.loans.get(loan_id)
        if rater is loan.borrower:
            ratee = loan.lender
        elif rater is loan.lender:
            ratee = loan.borrower
        else:
            raise PermissionDeniedError("Only the borrower or owner can rate this loan.")
        if loan.status != LoanStatus.RETURNED:
            raise NotEligibleError("You can rate a loan once the item has been returned.")
        key = (loan.id, rater.id)
        if key in self._ratings:
            raise NotEligibleError("You have already rated this loan.")
        rating = Rating(loan, rater, ratee, score, comment)
        self._ratings[key] = rating
        self._c.notifier.notify(ratee, f"{rater.full_name} rated you {score}/5 for "
                                       f"'{loan.item.title}'.", self._c.clock.now())
        return rating

    def ratings_for(self, person: Person) -> List[Rating]:
        return [r for r in self._ratings.values() if r.ratee is person]

    def average_for(self, person: Person) -> Optional[float]:
        scores = [r.score for r in self.ratings_for(person)]
        return round(sum(scores) / len(scores), 1) if scores else None

    def unrated_loans(self, person: Person) -> List[Loan]:
        """Returned loans this person took part in but has not rated yet."""
        return [l for l in self._c.loans.loans_of(person)
                if l.status == LoanStatus.RETURNED and (l.id, person.id) not in self._ratings]
