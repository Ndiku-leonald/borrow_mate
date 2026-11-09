"""Menu options for 'I Need This' requests (loaded automatically)."""

from datetime import datetime
from typing import List

from borrowmate.cli.display import countdown, heading, table, when
from borrowmate.cli.plugin import MenuEntry, MenuPlugin
from borrowmate.models.person import Student
from borrowmate.services.community import Community
from borrowmate.services.inventory import ItemFactory
from borrowmate.services.need_board import NeedBoard


class NeedRequestsPlugin(MenuPlugin):
    order = 20

    def __init__(self, community: Community):
        super().__init__(community)
        self.board = NeedBoard(community)

    def on_tick(self, now: datetime) -> None:
        self.board.expire_old(now)

    def menu_entries(self, cli) -> List[MenuEntry]:
        if not isinstance(cli.user, Student):
            return [("All 'I Need This' requests", lambda: self.show_all(cli))]
        return [
            ("Post an 'I Need This' request", lambda: self.post(cli)),
            ("Requests near me I can help with", lambda: self.help_out(cli)),
            ("My requests and their offers", lambda: self.my_requests(cli)),
        ]

    def post(self, cli) -> None:
        title = cli.ask("What do you need? ")
        kind = cli.ask(f"Category ({' / '.join(ItemFactory.kinds())}): ")
        hours = int(cli.ask("For how many hours? "))
        radius_text = cli.ask("Ask people within how many metres? (Enter for 1000): ").strip()
        need = self.board.post(cli.user, title, kind, hours, int(radius_text or 1000))
        reached = len(self.board.students_in_range(need))
        cli.say(f"  Posted {need.id}. {reached} student(s) nearby were notified.")

    def help_out(self, cli) -> None:
        now = cli.community.clock.now()
        needs = self.board.open_needs_for(cli.user)
        cli.say(heading("Requests near you"))
        cli.say(table(["Request", "Needs", "For", "From", "Hostel", "Closes"],
                      [[n.id, n.title, f"{n.hours}h", n.requester.full_name,
                        n.requester.hostel, countdown(n.time_left(now))] for n in needs]))
        if not needs:
            return
        need_id = cli.ask("Request id to offer on (Enter to go back): ").strip()
        if not need_id:
            return
        offer = self.board.offer(cli.user, need_id, cli.ask("Message (optional): "))
        cli.say(f"  Offer {offer.id} sent.")

    def my_requests(self, cli) -> None:
        needs = self.board.needs_of(cli.user)
        cli.say(heading("Your requests"))
        cli.say(table(["Request", "Needs", "For", "Posted", "Status", "Offers"],
                      [[n.id, n.title, f"{n.hours}h", when(n.posted_at), n.status.value,
                        len(n.pending_offers())] for n in needs]))
        open_with_offers = [n for n in needs if n.is_open and n.pending_offers()]
        for need in open_with_offers:
            cli.say(heading(f"Offers for {need.id} ({need.title})"))
            cli.say(table(["Offer", "From", "Hostel", "Reliability", "Message"],
                          [[o.id, o.offerer.full_name, o.offerer.hostel, o.offerer.reliability,
                            o.message or "-"] for o in need.pending_offers()]))
        if not open_with_offers:
            return
        need_id = cli.ask("Request id to choose an offer for (Enter to go back): ").strip()
        if not need_id:
            return
        loan = self.board.accept_offer(cli.user, need_id, cli.ask("Offer id: "))
        cli.say(f"  Done! Loan {loan.id} confirmed with {loan.lender.full_name}. "
                f"Collect it from {loan.lender.hostel}; return by {when(loan.due_at)}.")

    def show_all(self, cli) -> None:
        cli.say(heading("All 'I Need This' requests"))
        cli.say(table(["Request", "Needs", "From", "Status", "Offers"],
                      [[n.id, n.title, n.requester.full_name, n.status.value, len(n.offers())]
                       for n in self.board.all_needs()]))
