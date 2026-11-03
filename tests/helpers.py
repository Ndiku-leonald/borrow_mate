"""Shared fixtures for the test suite."""

from datetime import datetime

from borrowmate.services import Community, SimulatedClock

START = datetime(2026, 11, 3, 9, 0)


def make_community():
    """A small campus: two hostels, an experienced lender and a new borrower."""
    clock = SimulatedClock(START)
    c = Community(clock)
    hill = c.add_hostel("Hilltop", 0.3561, 32.7527)
    gate = c.add_hostel("Main Gate", 0.3540, 32.7551)
    lender = c.register_student("Lena Lender", "lena@test.ug", hill)
    borrower = c.register_student("Ben Borrower", "ben@test.ug", gate)
    other = c.register_student("Olga Other", "olga@test.ug", gate)
    admin = c.register_admin("Ada Admin", "ada@test.ug", hill)
    return c, clock, lender, borrower, other, admin


def make_experienced(student, loans=5):
    for _ in range(loans):
        student.record_return(on_time=True)
    return student
