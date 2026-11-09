"""'I Need This' requests: demand-driven borrowing.

A student posts what they need, nearby students make offers, and the
requester picks one. NeedRequest *owns* its Offers (composition): an
offer cannot exist without the request it answers.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

from borrowmate.exceptions import InvalidTransitionError, ValidationError
from borrowmate.models.person import Student


class NeedStatus(Enum):
    OPEN = "Open"
    FULFILLED = "Fulfilled"
    CANCELLED = "Cancelled"
    EXPIRED = "Expired"


class OfferStatus(Enum):
    PENDING = "Pending"
    ACCEPTED = "Accepted"
    DECLINED = "Declined"


class Offer:
    """A student saying 'I have that, you can borrow mine'."""

    def __init__(self, offer_id: str, need: "NeedRequest", offerer: Student, message: str = ""):
        self._id = offer_id
        self._need = need
        self._offerer = offerer
        self._message = message.strip()
        self._status = OfferStatus.PENDING

    @property
    def id(self) -> str:
        return self._id

    @property
    def need(self) -> "NeedRequest":
        return self._need

    @property
    def offerer(self) -> Student:
        return self._offerer

    @property
    def message(self) -> str:
        return self._message

    @property
    def status(self) -> OfferStatus:
        return self._status

    def _set(self, status: OfferStatus) -> None:
        if self._status != OfferStatus.PENDING:
            raise InvalidTransitionError(f"Offer {self._id} was already {self._status.value.lower()}.")
        self._status = status


class NeedRequest:
    """A public 'I need X for N hours' post."""

    def __init__(self, need_id: str, requester: Student, title: str, kind: str, hours: int,
                 radius_m: int, posted_at: datetime, valid_hours: int = 24):
        if not title or not title.strip():
            raise ValidationError("Say what you need.")
        if hours <= 0:
            raise ValidationError("Borrowing time must be at least 1 hour.")
        if radius_m <= 0:
            raise ValidationError("Search radius must be positive.")
        if valid_hours <= 0:
            raise ValidationError("The request must stay open for at least 1 hour.")
        self._id = need_id
        self._requester = requester
        self._title = title.strip()
        self._kind = kind.strip().lower()
        self._hours = hours
        self._radius_m = radius_m
        self._posted_at = posted_at
        self._expires_at = posted_at + timedelta(hours=valid_hours)
        self._status = NeedStatus.OPEN
        self._offers: List[Offer] = []

    # --- read-only properties -----------------------------------------------
    @property
    def id(self) -> str:
        return self._id

    @property
    def requester(self) -> Student:
        return self._requester

    @property
    def title(self) -> str:
        return self._title

    @property
    def kind(self) -> str:
        return self._kind

    @property
    def hours(self) -> int:
        return self._hours

    @property
    def radius_m(self) -> int:
        return self._radius_m

    @property
    def posted_at(self) -> datetime:
        return self._posted_at

    @property
    def expires_at(self) -> datetime:
        return self._expires_at

    @property
    def status(self) -> NeedStatus:
        return self._status

    @property
    def is_open(self) -> bool:
        return self._status == NeedStatus.OPEN

    def offers(self) -> List[Offer]:
        return list(self._offers)  # a copy, so callers cannot edit the real list

    def pending_offers(self) -> List[Offer]:
        return [o for o in self._offers if o.status == OfferStatus.PENDING]

    # --- behaviour ------------------------------------------------------------
    def add_offer(self, offer_id: str, offerer: Student, message: str = "") -> Offer:
        self._require_open()
        if offerer is self._requester:
            raise ValidationError("You cannot offer on your own request.")
        if any(o.offerer is offerer and o.status == OfferStatus.PENDING for o in self._offers):
            raise ValidationError("You have already offered on this request.")
        offer = Offer(offer_id, self, offerer, message)
        self._offers.append(offer)
        return offer

    def accept(self, offer: Offer) -> List[Offer]:
        """Accept one offer; returns the other offers, which are declined."""
        self._require_open()
        if offer not in self._offers:
            raise ValidationError(f"Offer {offer.id} is not for this request.")
        offer._set(OfferStatus.ACCEPTED)
        others = self.pending_offers()
        for other in others:
            other._set(OfferStatus.DECLINED)
        self._status = NeedStatus.FULFILLED
        return others

    def cancel(self) -> None:
        self._require_open()
        self._status = NeedStatus.CANCELLED
        for offer in self.pending_offers():
            offer._set(OfferStatus.DECLINED)

    def expire_if_due(self, now: datetime) -> bool:
        if self.is_open and now >= self._expires_at:
            self._status = NeedStatus.EXPIRED
            for offer in self.pending_offers():
                offer._set(OfferStatus.DECLINED)
            return True
        return False

    def _require_open(self) -> None:
        if not self.is_open:
            raise InvalidTransitionError(f"Request {self._id} is {self._status.value.lower()}.")

    def time_left(self, now: datetime) -> Optional[timedelta]:
        return self._expires_at - now if self.is_open else None

    def __str__(self) -> str:
        return (f"Need {self._id}: {self._title} for {self._hours}h within "
                f"{self._radius_m} m - {self._requester.full_name} [{self._status.value}]")
