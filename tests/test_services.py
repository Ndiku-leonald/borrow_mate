"""Tests for borrowing rules, conflicts, overdue detection and search."""

import unittest
from datetime import timedelta

from borrowmate.exceptions import (BookingConflictError, NotEligibleError,
                                   PermissionDeniedError, ValidationError)
from borrowmate.models import Condition, ItemStatus, LoanStatus
from tests.helpers import START, make_community, make_experienced


class BorrowingFlowTests(unittest.TestCase):
    def setUp(self):
        (self.c, self.clock, self.lender, self.borrower,
         self.other, self.admin) = make_community()
        self.umbrella = self.c.inventory.list_new("household", "Umbrella", self.lender)

    def test_full_loan_and_notifications(self):
        loans = self.c.loans
        loan = loans.request(self.borrower, self.umbrella.id, hours=2)
        loans.accept(self.lender, loan.id)
        loans.hand_over(self.lender, loan.id)
        self.assertEqual(loans.taken_loans(), [loan])
        self.clock.advance(hours=1)
        loans.confirm_return(self.lender, loan.id, Condition.GOOD)
        self.assertEqual(loan.status, LoanStatus.RETURNED)
        self.assertEqual(self.borrower.completed_loans, 1)
        self.assertTrue(self.c.notifier.inbox(self.lender))
        self.assertTrue(self.c.notifier.inbox(self.borrower))

    def test_only_lender_can_confirm_return(self):
        loans = self.c.loans
        loan = loans.request(self.borrower, self.umbrella.id, hours=2)
        loans.accept(self.lender, loan.id)
        loans.hand_over(self.lender, loan.id)
        with self.assertRaises(PermissionDeniedError):
            loans.confirm_return(self.borrower, loan.id)

    def test_admin_cannot_borrow(self):
        with self.assertRaises(NotEligibleError):
            self.c.loans.request(self.admin, self.umbrella.id, hours=1)

    def test_paused_item_cannot_be_requested(self):
        self.umbrella.pause()
        with self.assertRaises(Exception):
            self.c.loans.request(self.borrower, self.umbrella.id, hours=1)

    def test_new_student_cannot_borrow_high_value(self):
        laptop = self.c.inventory.list_new("electronics", "Laptop charger", self.lender,
                                           high_value=True)
        with self.assertRaises(NotEligibleError):
            self.c.loans.request(self.borrower, laptop.id, hours=1)
        make_experienced(self.borrower, 5)
        self.c.loans.request(self.borrower, laptop.id, hours=1)  # now allowed

    def test_start_time_in_past_rejected(self):
        with self.assertRaises(NotEligibleError):
            self.c.loans.request(self.borrower, self.umbrella.id, hours=1,
                                 start_at=START - timedelta(hours=1))

    def test_duplicate_email_rejected(self):
        with self.assertRaises(ValidationError):
            self.c.register_student("Copy", "BEN@test.ug", self.lender.hostel)


class ConflictTests(unittest.TestCase):
    def setUp(self):
        (self.c, self.clock, self.lender, self.borrower,
         self.other, _) = make_community()
        self.item = self.c.inventory.list_new("household", "Bucket", self.lender)

    def test_competing_requests_are_reported(self):
        loans = self.c.loans
        loans.request(self.borrower, self.item.id, 3, START + timedelta(hours=1))
        loans.request(self.other, self.item.id, 2, START + timedelta(hours=2))
        conflicts = loans.conflicts()
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].severity, "COMPETING")

    def test_accepting_one_declines_the_rival(self):
        loans = self.c.loans
        first = loans.request(self.borrower, self.item.id, 3, START + timedelta(hours=1))
        rival = loans.request(self.other, self.item.id, 2, START + timedelta(hours=2))
        loans.accept(self.lender, first.id)
        self.assertEqual(rival.status, LoanStatus.DECLINED)
        self.assertEqual(loans.conflicts(), [])

    def test_request_over_confirmed_booking_is_blocked(self):
        loans = self.c.loans
        first = loans.request(self.borrower, self.item.id, 3)
        loans.accept(self.lender, first.id)
        with self.assertRaises(BookingConflictError):
            loans.request(self.other, self.item.id, 1, START + timedelta(hours=1))
        # a slot after the booking is fine
        later = loans.request(self.other, self.item.id, 1, START + timedelta(hours=3))
        self.assertEqual(later.status, LoanStatus.REQUESTED)


class OverdueTests(unittest.TestCase):
    def test_overdue_flagged_and_blocks_new_borrowing(self):
        c, clock, lender, borrower, _, _ = make_community()
        bucket = c.inventory.list_new("household", "Bucket", lender)
        mop = c.inventory.list_new("household", "Mop", lender)
        loan = c.loans.request(borrower, bucket.id, hours=1)
        c.loans.accept(lender, loan.id)
        c.loans.hand_over(lender, loan.id)
        clock.advance(hours=2)
        self.assertEqual(c.loans.refresh_overdue(), [loan])
        self.assertEqual(loan.status, LoanStatus.OVERDUE)
        with self.assertRaises(NotEligibleError):
            c.loans.request(borrower, mop.id, hours=1)
        c.loans.confirm_return(lender, loan.id)
        self.assertEqual(borrower.late_returns, 1)
        self.assertEqual(bucket.status, ItemStatus.AVAILABLE)


class InventoryTests(unittest.TestCase):
    def test_available_sorted_by_distance_and_radius(self):
        c, _, lender, borrower, _, _ = make_community()
        far = c.add_hostel("Seeta", 0.3622, 32.7110)
        grace = c.register_student("Grace", "grace@test.ug", far)
        near_item = c.inventory.list_new("household", "Bucket", lender)
        far_item = c.inventory.list_new("book", "Algorithms", grace)
        self.assertEqual(c.inventory.available(borrower.hostel), [near_item, far_item])
        self.assertEqual(c.inventory.available(borrower.hostel, radius_m=1000), [near_item])

    def test_search_and_unknown_category(self):
        c, _, lender, *_ = make_community()
        c.inventory.list_new("electronics", "Scientific calculator", lender)
        self.assertEqual(len(c.inventory.search("calc")), 1)
        self.assertEqual(len(c.inventory.search("electronics")), 1)
        with self.assertRaises(ValidationError):
            c.inventory.list_new("furniture", "Chair", lender)


if __name__ == "__main__":
    unittest.main()
