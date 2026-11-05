"""Menu options for loan extensions and ratings (loaded automatically)."""

from typing import List

from borrowmate.cli.display import heading, table, when
from borrowmate.cli.plugin import MenuEntry, MenuPlugin
from borrowmate.models.person import Student
from borrowmate.services.community import Community
from borrowmate.services.feedback_service import ExtensionManager, RatingBook


class ExtensionsAndRatingsPlugin(MenuPlugin):
    order = 10

    def __init__(self, community: Community):
        super().__init__(community)
        self.extensions = ExtensionManager(community)
        self.ratings = RatingBook(community)

    def menu_entries(self, cli) -> List[MenuEntry]:
        if not isinstance(cli.user, Student):
            return [("Ratings for a user", lambda: self.show_ratings(cli))]
        return [
            ("Ask for more time on a loan", lambda: self.ask_extension(cli)),
            ("Extension requests for my items", lambda: self.answer_extensions(cli)),
            ("Rate a finished loan", lambda: self.rate_loan(cli)),
            ("Ratings for a user", lambda: self.show_ratings(cli)),
        ]

    def ask_extension(self, cli) -> None:
        loan_id = cli.ask("Loan id: ")
        hours = int(cli.ask("How many extra hours? "))
        reason = cli.ask("Reason (optional): ")
        request = self.extensions.request(cli.user, loan_id, hours, reason)
        cli.say(f"  Sent {request.id}. New return time if approved: "
                f"{when(request.proposed_due)}.")

    def answer_extensions(self, cli) -> None:
        pending = self.extensions.pending_for_lender(cli.user)
        cli.say(heading("Extension requests for your items"))
        cli.say(table(["Request", "Item", "Borrower", "Due now", "Asked until", "Reason"],
                      [[r.id, r.loan.item.title, r.loan.borrower.full_name, when(r.loan.due_at),
                        when(r.proposed_due), r.reason or "-"] for r in pending]))
        if not pending:
            return
        request_id = cli.ask("Request id to answer (Enter to go back): ").strip()
        if not request_id:
            return
        if cli.ask("Approve? (y/n): ").strip().lower().startswith("y"):
            request = self.extensions.approve(cli.user, request_id)
            cli.say(f"  Approved. New return time: {when(request.loan.due_at)}.")
        else:
            self.extensions.decline(cli.user, request_id)
            cli.say("  Declined.")

    def rate_loan(self, cli) -> None:
        unrated = self.ratings.unrated_loans(cli.user)
        cli.say(heading("Finished loans you can rate"))
        cli.say(table(["Loan", "Item", "Borrower", "Owner", "Returned"],
                      [[l.id, l.item.title, l.borrower.full_name, l.lender.full_name,
                        when(l.returned_at)] for l in unrated]))
        if not unrated:
            return
        loan_id = cli.ask("Loan id: ")
        score = int(cli.ask("Stars (1-5): "))
        comment = cli.ask("Comment (optional): ")
        rating = self.ratings.rate(cli.user, loan_id, score, comment)
        cli.say(f"  You rated {rating.ratee.full_name} {rating.stars()}.")

    def show_ratings(self, cli) -> None:
        person = cli.community.people.get(cli.ask("User id: "))
        average = self.ratings.average_for(person)
        cli.say(heading(f"Ratings for {person.full_name}"))
        cli.say(f"  Average: {average if average is not None else 'no ratings yet'}")
        cli.say(table(["Stars", "From", "Item", "Comment"],
                      [[r.stars(), r.rater.full_name, r.loan.item.title, r.comment or "-"]
                       for r in self.ratings.ratings_for(person)]))
