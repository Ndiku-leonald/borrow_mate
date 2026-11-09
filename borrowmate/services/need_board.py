"""NeedBoard: posting needs, collecting offers and turning one into a loan."""

from datetime import datetime
from typing import List

from borrowmate.exceptions import NotEligibleError, PermissionDeniedError
from borrowmate.models.loan import Loan
from borrowmate.models.need import NeedRequest, Offer
from borrowmate.models.person import Person, Student
from borrowmate.services.community import Community
from borrowmate.services.inventory import ItemFactory
from borrowmate.services.repository import IdGenerator, Repository


class NeedBoard:
    """The public board of 'I Need This' requests."""

    def __init__(self, community: Community):
        self._c = community
        self._needs: Repository[NeedRequest] = Repository("Need request")
        self._need_ids = IdGenerator("N")
        self._offer_ids = IdGenerator("O")

    # --- posting ------------------------------------------------------------
    def post(self, requester: Person, title: str, kind: str, hours: int,
             radius_m: int = 1000, valid_hours: int = 24) -> NeedRequest:
        student = self._require_student(requester)
        ItemFactory.create(kind, "CHECK", title, student)  # fails early on a bad category
        need = self._needs.add(NeedRequest(self._need_ids.next(), student, title, kind, hours,
                                           radius_m, self._c.clock.now(), valid_hours))
        for neighbour in self.students_in_range(need):
            self._tell(neighbour, f"{student.full_name} needs '{need.title}' for {hours}h "
                                  f"({self._distance(student, neighbour)} away). "
                                  f"Can you help? Request {need.id}.")
        return need

    def cancel(self, requester: Person, need_id: str) -> NeedRequest:
        need = self._needs.get(need_id)
        if requester is not need.requester:
            raise PermissionDeniedError("Only the person who posted it can cancel this request.")
        need.cancel()
        return need

    # --- offering -----------------------------------------------------------
    def offer(self, offerer: Person, need_id: str, message: str = "") -> Offer:
        student = self._require_student(offerer)
        need = self._needs.get(need_id)
        if not self._in_range(need, student):
            raise NotEligibleError("You are outside the area this request is looking in.")
        offer = need.add_offer(self._offer_ids.next(), student, message)
        self._tell(need.requester, f"{student.full_name} can lend you '{need.title}'. "
                                   f"Offer {offer.id}.")
        return offer

    def accept_offer(self, requester: Person, need_id: str, offer_id: str) -> Loan:
        """Requester picks an offer. The item is listed for the offerer and a
        confirmed loan is created, ready for handover."""
        need = self._needs.get(need_id)
        if requester is not need.requester:
            raise PermissionDeniedError("Only the person who posted the request can choose an offer.")
        offer = next((o for o in need.offers() if o.id == offer_id.strip().upper()), None)
        if offer is None:
            raise NotEligibleError(f"Offer {offer_id} is not on request {need.id}.")

        # Check every borrowing rule BEFORE changing anything, so a refusal
        # leaves no half-created item or loan behind.
        inventory = self._c.inventory
        item = ItemFactory.create(need.kind, inventory.next_id(), need.title, offer.offerer)
        self._c.loans.check_eligibility(need.requester, item)

        inventory.add(item)
        loan = self._c.loans.request(need.requester, item.id, need.hours)
        self._c.loans.accept(offer.offerer, loan.id)
        for declined in need.accept(offer):
            self._tell(declined.offerer, f"Thanks for offering '{need.title}' - "
                                         f"{need.requester.full_name} chose another offer.")
        return loan

    # --- queries --------------------------------------------------------------
    def open_needs_for(self, person: Person) -> List[NeedRequest]:
        """Open requests from other students that this person is close enough to answer."""
        return sorted((n for n in self._needs
                       if n.is_open and n.requester is not person and self._in_range(n, person)),
                      key=lambda n: n.expires_at)

    def needs_of(self, person: Person) -> List[NeedRequest]:
        return self._needs.find(lambda n: n.requester is person)

    def all_needs(self) -> List[NeedRequest]:
        return self._needs.all()

    def students_in_range(self, need: NeedRequest) -> List[Student]:
        return [s for s in self._c.students()
                if s is not need.requester and not s.is_suspended and self._in_range(need, s)]

    def expire_old(self, now: datetime) -> List[NeedRequest]:
        expired = [n for n in self._needs if n.expire_if_due(now)]
        for need in expired:
            self._tell(need.requester, f"Your request for '{need.title}' expired with no "
                                       f"accepted offer. Try a wider radius.")
        return expired

    # --- helpers ---------------------------------------------------------------
    def _in_range(self, need: NeedRequest, person: Person) -> bool:
        return need.requester.hostel.distance_to(person.hostel) <= need.radius_m

    @staticmethod
    def _require_student(person: Person) -> Student:
        if not isinstance(person, Student):
            raise NotEligibleError(f"{person.role()} accounts cannot post or answer requests.")
        if person.is_suspended:
            raise NotEligibleError("Your account is suspended.")
        return person

    @staticmethod
    def _distance(a: Person, b: Person) -> str:
        metres = a.hostel.distance_to(b.hostel)
        return f"{metres:.0f} m" if metres < 1000 else f"{metres / 1000:.1f} km"

    def _tell(self, person: Person, message: str) -> None:
        self._c.notifier.notify(person, message, self._c.clock.now())
