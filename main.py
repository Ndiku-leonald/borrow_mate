"""Start BorrowMate.

    python main.py          # demo data on a simulated clock (recommended)
    python main.py --empty  # empty campus on the real clock
"""

import sys

from borrowmate.cli import BorrowMateCLI
from borrowmate.seed import build_demo_community
from borrowmate.services import Community


def main() -> None:
    if "--empty" in sys.argv:
        community = Community()
        hostel = community.add_hostel("My Hostel", 0.3556, 32.7533)
        community.register_student("First Student", "student@example.com", hostel)
        community.register_admin("Moderator", "admin@example.com", hostel)
    else:
        community = build_demo_community()
    try:
        BorrowMateCLI(community).run()
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
