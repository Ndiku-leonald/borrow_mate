"""Tests for loan extensions and ratings."""

import unittest
from datetime import timedelta

from borrowmate.cli import BorrowMateCLI
from borrowmate.exceptions import (BookingConflictError, InvalidTransitionError,
                                   NotEligibleError, PermissionDeniedError, ValidationError)
from borrowmate.models import Condition, LoanStatus
from borrowmate.models.feedback import ExtensionStatus
from borrowmate.plugins.extensions_ratings import ExtensionsAndRatingsPlugin
from borrowmate.seed import build_demo_community
from borrowmate.services.feedback_service import ExtensionManager, RatingBook
from tests.helpers import START, make_community


def loan_in_progress(hours=2):
    c, clock, lender, borrower, other, admin = make_community()
    item = c.inventory.list_new("household", "Umbrella", lender)
    loan = c.loans.request(borrower, item.id, hours=hours)
    c.loans.accept(lender, loan.id)
    c.loans.hand_over(lender, loan.id)
    return c, clock, lender, borrower, other, item, loan


class ExtensionTests(unittest.TestCase):
    def test_approved_extension_moves_due_time(self):
        c, _, lender, borrower, _, _, loan = loan_in_progress()
        manager = ExtensionManager(c)
        request = manager.request(borrower, loan.id, 2, "exam ran late")
        manager.approve(lender, request.id)
        self.assertEqual(loan.due_at, START + timedelta(hours=4))
        self.assertEqual(request.status, ExtensionStatus.APPROVED)

    def test_extension_clears_overdue(self):
        c, clock, lender, borrower, _, _, loan = loan_in_progress()
        clock.advance(hours=3)
        c.loans.refresh_overdue()
        self.assertEqual(loan.status, LoanStatus.OVERDUE)
        manager = ExtensionManager(c)
        manager.approve(lender, manager.request(borrower, loan.id, 3).id)
        self.assertEqual(loan.status, LoanStatus.HANDED_OVER)
        self.assertEqual(c.loans.overdue_loans(), [])

    def test_cannot_extend_into_next_booking(self):
        c, _, lender, borrower, other, item, loan = loan_in_progress()
        next_booking = c.loans.request(other, item.id, 1, START + timedelta(hours=3))
        c.loans.accept(lender, next_booking.id)
        with self.assertRaises(BookingConflictError):
            ExtensionManager(c).request(borrower, loan.id, 2)

    def test_rules(self):
        c, _, lender, borrower, other, _, loan = loan_in_progress()
        manager = ExtensionManager(c)
        with self.assertRaises(PermissionDeniedError):
            manager.request(other, loan.id, 1)
        with self.assertRaises(ValidationError):
            manager.request(borrower, loan.id, 0)
        request = manager.request(borrower, loan.id, 1)
        with self.assertRaises(NotEligibleError):
            manager.request(borrower, loan.id, 1)          # one pending at a time
        with self.assertRaises(PermissionDeniedError):
            manager.approve(borrower, request.id)          # borrower can't approve
        manager.decline(lender, request.id)
        with self.assertRaises(InvalidTransitionError):
            manager.approve(lender, request.id)            # already answered


class RatingTests(unittest.TestCase):
    def test_both_sides_rate_once(self):
        c, _, lender, borrower, _, _, loan = loan_in_progress()
        book = RatingBook(c)
        with self.assertRaises(NotEligibleError):
            book.rate(borrower, loan.id, 5)                # not returned yet
        c.loans.confirm_return(lender, loan.id, Condition.GOOD)
        book.rate(borrower, loan.id, 5, "Very helpful")
        book.rate(lender, loan.id, 4)
        self.assertEqual(book.average_for(lender), 5.0)
        self.assertEqual(book.average_for(borrower), 4.0)
        with self.assertRaises(NotEligibleError):
            book.rate(borrower, loan.id, 1)
        self.assertEqual(book.unrated_loans(borrower), [])

    def test_score_range_and_outsiders(self):
        c, _, lender, borrower, other, _, loan = loan_in_progress()
        c.loans.confirm_return(lender, loan.id)
        book = RatingBook(c)
        with self.assertRaises(ValidationError):
            book.rate(borrower, loan.id, 6)
        with self.assertRaises(PermissionDeniedError):
            book.rate(other, loan.id, 3)


class ExtensionsCliTests(unittest.TestCase):
    def test_overdue_borrower_gets_more_time_through_menu(self):
        community = build_demo_community()
        plugin = ExtensionsAndRatingsPlugin(community)
        inputs = iter([
            "U001", "16", "L002", "2", "Still ironing",   # Leo asks for 2h more on the iron
            "22", "U002",                                 # switch user to Keitha
            "17", "E001", "y",                            # Keitha approves
            "0",
        ])
        output = []
        BorrowMateCLI(community, input_fn=lambda _: next(inputs), output_fn=output.append,
                      plugins=[plugin]).run()
        self.assertIn("Approved", "\n".join(output))
        self.assertEqual(community.loans.get("L002").status, LoanStatus.HANDED_OVER)


if __name__ == "__main__":
    unittest.main()
