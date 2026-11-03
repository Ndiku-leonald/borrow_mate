"""Demo data so the CLI has something to show straight away.

The scenario covers every view: available items, items currently taken
with their return times, an overdue item, competing requests (a conflict)
and a booking blocked by a confirmed loan.
"""

from datetime import datetime

from borrowmate.models.enums import Condition
from borrowmate.services.clock import SimulatedClock
from borrowmate.services.community import Community

DEMO_START = datetime(2026, 11, 3, 9, 0)


def build_demo_community() -> Community:
    clock = SimulatedClock(DEMO_START)
    c = Community(clock)

    # Hostels around UCU Mukono (approximate, fictional names).
    hill = c.add_hostel("Hilltop Hostel", 0.3561, 32.7527)
    gate = c.add_hostel("Main Gate Hostel", 0.3540, 32.7551)
    seeta = c.add_hostel("Seeta Road Hostel", 0.3622, 32.7110)

    leo = c.register_student("Leo Ndikuryayo", "leo@students.ucu.ac.ug", hill, reliability=4.4)
    keitha = c.register_student("Keitha", "keitha@students.ucu.ac.ug", hill, reliability=4.0)
    stacey = c.register_student("Stacey", "stacey@students.ucu.ac.ug", gate, reliability=3.6)
    brian = c.register_student("Brian Okello", "brian@students.ucu.ac.ug", gate)
    grace = c.register_student("Grace Namuli", "grace@students.ucu.ac.ug", seeta)
    c.register_admin("Hostel Moderator", "moderator@students.ucu.ac.ug", hill)

    # Give the senior students a track record so the trust ladder lets them
    # borrow medium/high value items.
    for student in (leo, keitha, stacey):
        for _ in range(5):
            student.record_return(on_time=True)

    inv = c.inventory
    calc = inv.list_new("electronics", "Scientific calculator", leo, brand="Casio fx-991",
                        needs_power=False)
    iron = inv.list_new("electronics", "Electric iron", keitha, brand="Philips")
    ext = inv.list_new("electronics", "Extension cable (4-way)", stacey)
    inv.list_new("electronics", "Laptop charger (HP)", brian, high_value=True)
    inv.list_new("book", "Introduction to Algorithms", grace, author="Cormen",
                 course_unit="Data Structures")
    umbrella = inv.list_new("household", "Umbrella", brian)
    inv.list_new("household", "Bucket", grace, condition=Condition.FAIR)
    paused = inv.list_new("household", "Screwdriver set", leo)
    paused.pause()

    loans = c.loans

    # 1. Taken item, due later today.
    l1 = loans.request(stacey, calc.id, hours=4)
    loans.accept(leo, l1.id)
    loans.hand_over(leo, l1.id)

    # 2. Taken item that will become overdue.
    l2 = loans.request(leo, iron.id, hours=1)
    loans.accept(keitha, l2.id)
    loans.hand_over(keitha, l2.id)

    # 3. Two pending requests for the same slot -> COMPETING conflict.
    loans.request(keitha, ext.id, hours=3, start_at=datetime(2026, 11, 3, 14, 0))
    loans.request(leo, ext.id, hours=2, start_at=datetime(2026, 11, 3, 15, 0))

    # 4. A confirmed future booking of the umbrella.
    l4 = loans.request(keitha, umbrella.id, hours=2, start_at=datetime(2026, 11, 3, 16, 0))
    loans.accept(brian, l4.id)

    # Move time on so the iron is overdue.
    clock.advance(hours=1, minutes=30)
    loans.refresh_overdue()
    return c
