"""The interactive command-line app.

Input and output are injected (input_fn / output_fn), so the whole menu
can be driven by tests without a keyboard.
"""

from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from borrowmate.cli.display import countdown, distance, heading, table, when
from borrowmate.exceptions import BorrowMateError, ValidationError
from borrowmate.models.enums import Condition, ItemStatus
from borrowmate.models.item import Item
from borrowmate.models.person import Person, Student
from borrowmate.services.clock import SimulatedClock
from borrowmate.services.community import Community
from borrowmate.services.inventory import ItemFactory

MenuEntry = Tuple[str, Callable[[], None]]


class BorrowMateCLI:
    """Menu-driven interface on top of a Community."""

    def __init__(self, community: Community,
                 input_fn: Callable[[str], str] = input,
                 output_fn: Callable[[str], None] = print):
        self._c = community
        self._ask = input_fn
        self._say = output_fn
        self._user: Optional[Person] = None
        self._running = False

    # --- main loop ---------------------------------------------------------
    def run(self) -> None:
        self._say("Welcome to BorrowMate - borrow it, don't buy it.")
        self._running = True
        self._login()
        while self._running:
            self._c.loans.refresh_overdue()
            menu = self._menu()
            self._say(heading(f"Menu - {self._user}  |  now {when(self._c.clock.now())}"))
            for key, (label, _) in menu.items():
                self._say(f"  {key:>2}. {label}")
            choice = self._ask("\nChoose an option: ").strip()
            action = menu.get(choice)
            if action is None:
                self._say("  Unknown option, try again.")
                continue
            try:
                action[1]()
            except BorrowMateError as error:
                self._say(f"  ! {error}")
            except ValueError:
                self._say("  ! Please enter a number where a number is expected.")

    def _menu(self) -> Dict[str, MenuEntry]:
        entries: List[MenuEntry] = [
            ("All listed items", self.show_all_items),
            ("Available items near me", self.show_available),
            ("Taken items and return times", self.show_taken),
            ("Booking conflicts", self.show_conflicts),
            ("Overdue items", self.show_overdue),
            ("Search items", self.search),
        ]
        if isinstance(self._user, Student):
            entries += [
                ("Request to borrow an item", self.request_item),
                ("Requests waiting for my approval", self.review_requests),
                ("Hand over an item (lender)", self.hand_over),
                ("Confirm an item was returned (lender)", self.confirm_return),
                ("Cancel a request or booking", self.cancel),
                ("Report a problem with a loan", self.dispute),
                ("List a new item", self.list_item),
                ("Pause / resume one of my items", self.toggle_pause),
                ("My loans and profile", self.my_loans),
            ]
        else:
            entries += [
                ("Disputed loans", self.show_disputes),
                ("Suspend / restore a user", self.toggle_suspension),
            ]
        entries.append(("Notifications", self.show_notifications))
        if isinstance(self._c.clock, SimulatedClock):
            entries.append(("Move demo clock forward", self.advance_clock))
        entries.append(("Switch user", self._login))
        menu = {str(i): entry for i, entry in enumerate(entries, start=1)}
        menu["0"] = ("Exit", self._quit)
        return menu

    def _quit(self) -> None:
        self._say("Goodbye!")
        self._running = False

    def _login(self) -> None:
        people = self._c.people.all()
        self._say(heading("Who are you?"))
        self._say(table(["Id", "Name", "Role", "Hostel"],
                        [[p.id, p.full_name, p.role(), p.hostel] for p in people]))
        while True:
            try:
                self._user = self._c.people.get(self._ask("Enter your user id: "))
                unread = len(self._c.notifier.inbox(self._user))
                self._say(f"  Logged in as {self._user.full_name}. "
                          f"You have {unread} notification(s).")
                return
            except BorrowMateError as error:
                self._say(f"  ! {error}")

    # --- views -------------------------------------------------------------
    def show_all_items(self) -> None:
        self._say(heading("All listed items"))
        self._item_table(self._c.inventory.all_items())

    def show_available(self) -> None:
        radius_text = self._ask("Search radius in metres (Enter for any distance): ").strip()
        radius = float(radius_text) if radius_text else None
        items = self._c.inventory.available(self._user.hostel, radius)
        self._say(heading("Available items, nearest first"))
        rows = []
        for item in items:
            booking = self._next_booking(item)
            rows.append([item.id, item.title, item.category(), item.condition.value,
                         f"{item.max_hours}h", item.owner.hostel,
                         distance(self._user.hostel.distance_to(item.owner.hostel)),
                         f"booked from {when(booking)}" if booking else "free",
                         "yes" if self._c.loans.is_eligible(self._user, item) else "no"])
        self._say(table(["Id", "Item", "Type", "Condition", "Max", "Hostel", "Distance",
                         "Upcoming", "You can borrow"], rows))

    def show_taken(self) -> None:
        now = self._c.clock.now()
        self._say(heading("Items currently taken"))
        rows = [[l.item.id, l.item.title, l.borrower.full_name, l.lender.full_name,
                 when(l.handed_over_at), when(l.due_at), countdown(l.time_left(now)),
                 l.status.value] for l in self._c.loans.taken_loans()]
        self._say(table(["Id", "Item", "Borrower", "Owner", "Taken", "Return by",
                         "Time left", "Status"], rows))
        upcoming = self._c.loans.upcoming_loans()
        if upcoming:
            self._say(heading("Confirmed bookings waiting for handover"))
            self._say(table(["Loan", "Item", "Borrower", "From", "Until"],
                            [[l.id, l.item.title, l.borrower.full_name, when(l.start_at),
                              when(l.due_at)] for l in upcoming]))

    def show_conflicts(self) -> None:
        self._say(heading("Booking conflicts"))
        conflicts = self._c.loans.conflicts()
        self._say(table(["Severity", "Loans", "Details"],
                        [[c.severity, f"{c.first.id} / {c.second.id}", c.describe()]
                         for c in conflicts]))
        if conflicts:
            self._say("\n  COMPETING: two requests want the same slot; the owner accepts one "
                      "and the other is declined automatically.")

    def show_overdue(self) -> None:
        now = self._c.clock.now()
        self._say(heading("Overdue items"))
        self._say(table(["Loan", "Item", "Borrower", "Owner", "Was due", "Late by"],
                        [[l.id, l.item.title, l.borrower.full_name, l.lender.full_name,
                          when(l.due_at), countdown(l.time_left(now))]
                         for l in self._c.loans.overdue_loans()]))

    def search(self) -> None:
        term = self._ask("Search for: ")
        self._say(heading(f"Results for '{term}'"))
        self._item_table(self._c.inventory.search(term))

    def show_notifications(self) -> None:
        self._say(heading("Notifications"))
        inbox = self._c.notifier.inbox(self._user)
        if not inbox:
            self._say("  No notifications.")
        for moment, message in inbox:
            self._say(f"  [{when(moment)}] {message}")
        self._c.notifier.clear(self._user)

    def my_loans(self) -> None:
        user = self._user
        self._say(heading("My profile"))
        self._say(f"  {user}\n  Reliability {user.reliability}/5, "
                  f"{user.completed_loans} completed, {user.late_returns} late, "
                  f"can borrow up to {user.max_value_tier().name} value items, "
                  f"{user.max_active_loans()} at a time.")
        self._say(heading("My loans"))
        self._loan_table(self._c.loans.loans_of(user))
        self._say(heading("My items"))
        self._item_table(self._c.inventory.items_of(user))

    def show_disputes(self) -> None:
        self._say(heading("Disputed loans"))
        self._say(table(["Loan", "Item", "Borrower", "Owner", "Reason"],
                        [[l.id, l.item.title, l.borrower.full_name, l.lender.full_name,
                          l.dispute_reason] for l in self._c.loans.disputes()]))

    # --- actions -----------------------------------------------------------
    def request_item(self) -> None:
        item = self._c.inventory.get(self._ask("Item id: "))
        self._say(f"  {item.title}: {item.details()}. Max {item.max_hours} hours.")
        hours = int(self._ask("For how many hours? "))
        start_text = self._ask("Start time as DD/MM HH:MM (Enter for now): ").strip()
        start = self._parse_time(start_text) if start_text else None
        loan = self._c.loans.request(self._user, item.id, hours, start)
        self._say(f"  Request sent: {loan}. {item.owner.full_name} has been notified.")

    def review_requests(self) -> None:
        pending = self._c.loans.pending_for(self._user)
        self._say(heading("Requests for your items"))
        self._loan_table(pending)
        if not pending:
            return
        loan_id = self._ask("Loan id to answer (Enter to go back): ").strip()
        if not loan_id:
            return
        if self._ask("Accept? (y/n): ").strip().lower().startswith("y"):
            loan = self._c.loans.accept(self._user, loan_id)
            self._say(f"  Accepted. {loan.borrower.full_name} will collect it "
                      f"{when(loan.start_at)}. Overlapping requests were declined.")
        else:
            self._c.loans.decline(self._user, loan_id)
            self._say("  Declined.")

    def hand_over(self) -> None:
        loan = self._c.loans.hand_over(self._user, self._ask("Loan id: "))
        self._say(f"  Handed over to {loan.borrower.full_name}. Due back {when(loan.due_at)}.")

    def confirm_return(self) -> None:
        loan_id = self._ask("Loan id: ")
        condition = self._pick_condition()
        loan = self._c.loans.confirm_return(self._user, loan_id, condition)
        late = loan.returned_at > loan.due_at
        self._say(f"  '{loan.item.title}' is back ({'late' if late else 'on time'}) "
                  f"and available again.")

    def cancel(self) -> None:
        loan = self._c.loans.cancel(self._user, self._ask("Loan id: "))
        self._say(f"  Loan {loan.id} cancelled.")

    def dispute(self) -> None:
        loan_id = self._ask("Loan id: ")
        reason = self._ask("What went wrong? ")
        self._c.loans.raise_dispute(self._user, loan_id, reason)
        self._say("  Reported. A moderator will review it.")

    def list_item(self) -> None:
        kind = self._ask(f"Category ({' / '.join(ItemFactory.kinds())}): ")
        title = self._ask("Item name: ")
        condition = self._pick_condition()
        item = self._c.inventory.list_new(kind, title, self._user, condition)
        self._say(f"  Listed: {item}")

    def toggle_pause(self) -> None:
        item = self._c.inventory.get(self._ask("Item id: "))
        if item.owner is not self._user:
            self._say("  ! You can only pause your own items.")
            return
        if item.status == ItemStatus.PAUSED:
            item.resume()
            self._say(f"  '{item.title}' is available again.")
        else:
            item.pause()
            self._say(f"  '{item.title}' is paused.")

    def toggle_suspension(self) -> None:
        person = self._c.people.get(self._ask("User id: "))
        if person.is_suspended:
            person.restore()
            self._say(f"  {person.full_name} restored.")
        else:
            person.suspend()
            self._say(f"  {person.full_name} suspended.")

    def advance_clock(self) -> None:
        hours = float(self._ask("Hours to move forward: "))
        now = self._c.clock.advance(hours=hours)  # type: ignore[attr-defined]
        flagged = self._c.loans.refresh_overdue()
        self._say(f"  Time is now {when(now)}. {len(flagged)} loan(s) became overdue.")

    # --- helpers -------------------------------------------------------------
    def _item_table(self, items: List[Item]) -> None:
        rows = []
        for item in items:
            holder = ""
            if item.status == ItemStatus.ON_LOAN:
                loan = next((l for l in self._c.loans.taken_loans() if l.item is item), None)
                if loan:
                    holder = f"{loan.borrower.full_name}, back {when(loan.due_at)}"
            rows.append([item.id, item.title, item.category(), item.status.value,
                         item.owner.full_name, item.owner.hostel, holder])
        self._say(table(["Id", "Item", "Type", "Status", "Owner", "Hostel", "With"], rows))

    def _loan_table(self, loans) -> None:
        self._say(table(["Loan", "Item", "Borrower", "Owner", "From", "Until", "Status"],
                        [[l.id, l.item.title, l.borrower.full_name, l.lender.full_name,
                          when(l.start_at), when(l.due_at), l.status.value] for l in loans]))

    def _next_booking(self, item: Item) -> Optional[datetime]:
        times = [l.start_at for l in self._c.loans.upcoming_loans() if l.item is item]
        return min(times) if times else None

    def _pick_condition(self) -> Condition:
        options = list(Condition)
        labels = ", ".join(f"{i}={c.value}" for i, c in enumerate(options, start=1))
        choice = self._ask(f"Condition ({labels}): ").strip()
        return options[int(choice) - 1] if choice else Condition.GOOD

    def _parse_time(self, text: str) -> datetime:
        now = self._c.clock.now()
        try:
            parsed = datetime.strptime(text, "%d/%m %H:%M")
        except ValueError:
            raise ValidationError("Use the format DD/MM HH:MM, e.g. 05/11 14:30") from None
        return parsed.replace(year=now.year)
