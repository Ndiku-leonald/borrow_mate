"""Tests for 'I Need This' requests and offers."""

import unittest

from borrowmate.cli import BorrowMateCLI
from borrowmate.exceptions import (InvalidTransitionError, NotEligibleError,
                                   PermissionDeniedError, ValidationError)
from borrowmate.models import ItemStatus, LoanStatus
from borrowmate.models.need import NeedStatus, OfferStatus
from borrowmate.plugins.need_requests import NeedRequestsPlugin
from borrowmate.seed import build_demo_community
from borrowmate.services.need_board import NeedBoard
from tests.helpers import make_community


class NeedBoardTests(unittest.TestCase):
    def setUp(self):
        (self.c, self.clock, self.lender, self.borrower,
         self.other, self.admin) = make_community()
        self.board = NeedBoard(self.c)

    def test_post_notifies_nearby_students_only(self):
        far_hostel = self.c.add_hostel("Far away", 0.40, 32.60)
        far = self.c.register_student("Far Student", "far@test.ug", far_hostel)
        need = self.board.post(self.borrower, "Bucket", "household", 2, radius_m=1000)
        reached = self.board.students_in_range(need)
        self.assertIn(self.lender, reached)
        self.assertNotIn(far, reached)
        self.assertTrue(self.c.notifier.inbox(self.lender))
        self.assertFalse(self.c.notifier.inbox(far))

    def test_accepting_offer_creates_confirmed_loan(self):
        need = self.board.post(self.borrower, "Bucket", "household", 2)
        chosen = self.board.offer(self.lender, need.id, "Mine is clean")
        rival = self.board.offer(self.other, need.id)
        loan = self.board.accept_offer(self.borrower, need.id, chosen.id)
        self.assertEqual(loan.status, LoanStatus.ACCEPTED)
        self.assertIs(loan.lender, self.lender)
        self.assertEqual(loan.item.status, ItemStatus.AVAILABLE)   # listed, ready for handover
        self.assertEqual(need.status, NeedStatus.FULFILLED)
        self.assertEqual(chosen.status, OfferStatus.ACCEPTED)
        self.assertEqual(rival.status, OfferStatus.DECLINED)

    def test_ineligible_borrower_leaves_nothing_behind(self):
        need = self.board.post(self.borrower, "Laptop", "electronics", 2)  # new student
        offer = self.board.offer(self.lender, need.id)
        items_before = len(self.c.inventory.all_items())
        with self.assertRaises(NotEligibleError):
            self.board.accept_offer(self.borrower, need.id, offer.id)
        self.assertEqual(len(self.c.inventory.all_items()), items_before)
        self.assertTrue(need.is_open)

    def test_rules(self):
        need = self.board.post(self.borrower, "Bucket", "household", 2)
        with self.assertRaises(ValidationError):
            self.board.offer(self.borrower, need.id)                 # own request
        with self.assertRaises(NotEligibleError):
            self.board.post(self.admin, "Bucket", "household", 1)     # admins can't post
        with self.assertRaises(ValidationError):
            self.board.post(self.borrower, "Chair", "furniture", 1)   # unknown category
        offer = self.board.offer(self.lender, need.id)
        with self.assertRaises(PermissionDeniedError):
            self.board.accept_offer(self.other, need.id, offer.id)    # not the requester
        self.board.cancel(self.borrower, need.id)
        self.assertEqual(offer.status, OfferStatus.DECLINED)
        with self.assertRaises(InvalidTransitionError):
            self.board.offer(self.other, need.id)                     # closed

    def test_requests_expire(self):
        need = self.board.post(self.borrower, "Bucket", "household", 2, valid_hours=3)
        self.clock.advance(hours=2)
        self.assertEqual(self.board.expire_old(self.clock.now()), [])
        self.clock.advance(hours=1)
        self.assertEqual(self.board.expire_old(self.clock.now()), [need])
        self.assertEqual(self.board.open_needs_for(self.lender), [])


class NeedRequestsCliTests(unittest.TestCase):
    def test_post_offer_accept_through_menu(self):
        community = build_demo_community()
        plugin = NeedRequestsPlugin(community)
        inputs = iter([
            "U004", "16", "Bucket", "household", "2", "",   # Brian posts N001
            "21", "U003",                                  # switch user to Stacey
            "17", "N001", "I have one",                    # Stacey offers O001
            "21", "U004",                                  # back to Brian
            "18", "N001", "O001",                          # Brian accepts
            "0",
        ])
        output = []
        BorrowMateCLI(community, input_fn=lambda _: next(inputs), output_fn=output.append,
                      plugins=[plugin]).run()
        text = "\n".join(output)
        self.assertIn("Done! Loan", text)
        self.assertEqual(plugin.board.all_needs()[0].status, NeedStatus.FULFILLED)


if __name__ == "__main__":
    unittest.main()
