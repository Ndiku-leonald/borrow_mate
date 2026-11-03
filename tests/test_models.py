"""Tests for the domain models and the OOP rules they enforce."""

import unittest
from datetime import timedelta

from borrowmate.exceptions import (InvalidTransitionError, ItemNotAvailableError,
                                   ValidationError)
from borrowmate.models import (Admin, Book, Condition, Electronics, HouseholdItem, Item,
                               ItemStatus, Loan, LoanStatus, Person, Student, ValueTier)
from tests.helpers import START, make_community, make_experienced


class AbstractionTests(unittest.TestCase):
    def test_person_and_item_are_abstract(self):
        _, _, lender, *_ = make_community()
        with self.assertRaises(TypeError):
            Person("X", "Name", "a@b.c", lender.hostel)  # type: ignore[abstract]
        with self.assertRaises(TypeError):
            Item("I", "Thing", lender)  # type: ignore[abstract]


class InheritanceAndPolymorphismTests(unittest.TestCase):
    def setUp(self):
        _, _, self.lender, _, _, self.admin = make_community()

    def test_subclasses_are_people(self):
        self.assertIsInstance(self.lender, Person)
        self.assertIsInstance(self.admin, Person)

    def test_roles_differ_by_class(self):
        self.assertEqual(self.lender.role(), "Student")
        self.assertEqual(self.admin.role(), "Admin")
        self.assertFalse(self.lender.can_moderate())
        self.assertTrue(self.admin.can_moderate())
        self.assertEqual(self.admin.max_active_loans(), 0)

    def test_items_answer_differently(self):
        items = [Electronics("I1", "Iron", self.lender),
                 Electronics("I2", "Laptop", self.lender, high_value=True),
                 Book("I3", "Algorithms", self.lender, author="Cormen"),
                 HouseholdItem("I4", "Bucket", self.lender)]
        self.assertEqual([i.category() for i in items],
                         ["Electronics", "Electronics", "Book", "Household"])
        self.assertEqual([i.value_tier() for i in items],
                         [ValueTier.MEDIUM, ValueTier.HIGH, ValueTier.LOW, ValueTier.LOW])
        self.assertEqual([i.max_hours for i in items], [24, 24, 72, 6])


class EncapsulationTests(unittest.TestCase):
    def setUp(self):
        _, _, self.lender, *_ = make_community()

    def test_reliability_is_clamped(self):
        for _ in range(20):
            self.lender.record_return(on_time=True)
        self.assertEqual(self.lender.reliability, 5.0)
        for _ in range(20):
            self.lender.record_return(on_time=False)
        self.assertEqual(self.lender.reliability, 0.0)

    def test_read_only_properties(self):
        with self.assertRaises(AttributeError):
            self.lender.full_name = "Someone else"  # type: ignore[misc]

    def test_cannot_pause_item_on_loan(self):
        item = HouseholdItem("I1", "Bucket", self.lender)
        item.mark_on_loan()
        with self.assertRaises(ItemNotAvailableError):
            item.pause()

    def test_validation(self):
        with self.assertRaises(ValidationError):
            HouseholdItem("I1", "  ", self.lender)
        with self.assertRaises(ValidationError):
            Student("U9", "Name", "not-an-email", self.lender.hostel)


class TrustLadderTests(unittest.TestCase):
    def test_tier_and_loan_limit_grow_with_history(self):
        _, _, lender, *_ = make_community()
        self.assertEqual(lender.max_value_tier(), ValueTier.LOW)
        self.assertEqual(lender.max_active_loans(), 1)
        make_experienced(lender, 2)
        self.assertEqual(lender.max_value_tier(), ValueTier.MEDIUM)
        self.assertEqual(lender.max_active_loans(), 3)
        make_experienced(lender, 3)
        self.assertEqual(lender.max_value_tier(), ValueTier.HIGH)


class LoanStateMachineTests(unittest.TestCase):
    def setUp(self):
        _, _, self.lender, self.borrower, *_ = make_community()
        self.item = HouseholdItem("I1", "Umbrella", self.lender)
        self.loan = Loan("L1", self.item, self.borrower, START, 2)

    def test_happy_path(self):
        self.loan.accept()
        self.loan.hand_over(START)
        self.assertEqual(self.item.status, ItemStatus.ON_LOAN)
        on_time = self.loan.complete_return(START + timedelta(hours=1), Condition.GOOD)
        self.assertTrue(on_time)
        self.assertEqual(self.loan.status, LoanStatus.RETURNED)
        self.assertEqual(self.item.status, ItemStatus.AVAILABLE)

    def test_late_return_is_detected(self):
        self.loan.accept()
        self.loan.hand_over(START)
        self.assertFalse(self.loan.complete_return(START + timedelta(hours=3), Condition.FAIR))
        self.assertEqual(self.item.condition, Condition.FAIR)

    def test_illegal_transitions(self):
        with self.assertRaises(InvalidTransitionError):
            self.loan.hand_over(START)          # not accepted yet
        self.loan.decline()
        with self.assertRaises(InvalidTransitionError):
            self.loan.accept()                  # closed loans stay closed

    def test_limits_on_creation(self):
        with self.assertRaises(ValidationError):
            Loan("L2", self.item, self.borrower, START, 7)      # umbrella max is 6h
        with self.assertRaises(ValidationError):
            Loan("L3", self.item, self.lender, START, 1)        # own item

    def test_overlap(self):
        later = Loan("L2", self.item, self.borrower, START + timedelta(hours=1), 2)
        after = Loan("L3", self.item, self.borrower, START + timedelta(hours=2), 2)
        self.assertTrue(self.loan.overlaps(later))
        self.assertFalse(self.loan.overlaps(after))   # touching windows do not overlap


if __name__ == "__main__":
    unittest.main()
