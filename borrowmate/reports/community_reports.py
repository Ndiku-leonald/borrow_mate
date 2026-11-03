"""The BorrowMate reports."""

from collections import Counter
from typing import Dict, List

from borrowmate.models.enums import LoanStatus
from borrowmate.models.loan import Loan
from borrowmate.models.person import Student
from borrowmate.reports.base import Report, Row, percent


def _returned(loans: List[Loan]) -> List[Loan]:
    return [loan for loan in loans if loan.status == LoanStatus.RETURNED]


def _on_time(loan: Loan) -> bool:
    return loan.returned_at is not None and loan.returned_at <= loan.due_at


def _went_out(loan: Loan) -> bool:
    return loan.handed_over_at is not None


class CommunityHealthReport(Report):
    """Headline numbers about the whole community."""

    @property
    def title(self) -> str:
        return "Community health"

    def headers(self) -> List[str]:
        return ["Measure", "Value"]

    def rows(self) -> List[Row]:
        c = self._community
        loans = c.loans.all_loans()
        accepted = [loan for loan in loans if loan.status.is_active or
                    loan.status in (LoanStatus.RETURNED, LoanStatus.DISPUTED)]
        declined = [loan for loan in loans if loan.status == LoanStatus.DECLINED]
        decided = accepted + declined
        returned = _returned(loans)
        on_time = [loan for loan in returned if _on_time(loan)]
        hours = [(loan.returned_at - loan.handed_over_at).total_seconds() / 3600
                 for loan in returned if loan.handed_over_at is not None and loan.returned_at is not None]
        lenders = {loan.lender for loan in loans if _went_out(loan)}
        return [
            ["Students registered", len(c.students())],
            ["Items listed", len(c.inventory.all_items())],
            ["Items available now", len(c.inventory.available())],
            ["Borrow requests made", len(loans)],
            ["Requests accepted", f"{len(accepted)} of {len(decided)} ({percent(len(accepted), len(decided))})"],
            ["Items out right now", len(c.loans.taken_loans())],
            ["Loans completed", len(returned)],
            ["Returned on time", f"{len(on_time)} of {len(returned)} ({percent(len(on_time), len(returned))})"],
            ["Overdue right now", len(c.loans.overdue_loans())],
            ["Open disputes", len(c.loans.disputes())],
            ["Average loan length", f"{sum(hours) / len(hours):.1f} h" if hours else "-"],
            ["Students who have lent", f"{len(lenders)} of {len(c.students())}"],
        ]


class TopLendersReport(Report):
    """Who shares the most and how trusted they are."""

    def __init__(self, community, limit: int = 10):
        super().__init__(community)
        self._limit = limit

    @property
    def title(self) -> str:
        return "Top lenders"

    def headers(self) -> List[str]:
        return ["Rank", "Student", "Hostel", "Times lent", "Items listed", "Reliability"]

    def rows(self) -> List[Row]:
        c = self._community
        lent = Counter(loan.lender for loan in c.loans.all_loans() if _went_out(loan))
        listed = Counter(item.owner for item in c.inventory.all_items())
        ranked = sorted((student for student in c.students() if lent[student] or listed[student]),
                        key=lambda s: (-lent[s], -listed[s], s.full_name))
        return [[rank, student.full_name, student.hostel.name, lent[student], listed[student],
                 f"{student.reliability}/5"]
                for rank, student in enumerate(ranked[:self._limit], start=1)]


class PopularItemsReport(Report):
    """Which items are requested most often."""

    @property
    def title(self) -> str:
        return "Most requested items"

    def headers(self) -> List[str]:
        return ["Item", "Category", "Owner", "Requests", "Times lent", "Status"]

    def rows(self) -> List[Row]:
        loans = self._community.loans.all_loans()
        requests = Counter(loan.item for loan in loans)
        lent = Counter(loan.item for loan in loans if _went_out(loan))
        items = sorted(requests, key=lambda item: (-requests[item], -lent[item], item.title))
        return [[item.title, item.category(), item.owner.full_name, requests[item], lent[item], item.status.value]
                for item in items]


class HostelActivityReport(Report):
    """How busy each hostel is."""

    @property
    def title(self) -> str:
        return "Hostel activity"

    def headers(self) -> List[str]:
        return ["Hostel", "Students", "Items listed", "Lent out", "Borrowed", "On-time returns"]

    def rows(self) -> List[Row]:
        c = self._community
        stats: Dict[object, Dict[str, int]] = {
            hostel: {"students": 0, "items": 0, "lent": 0, "borrowed": 0, "returned": 0, "on_time": 0}
            for hostel in c.hostels.all()
        }
        for student in c.students():
            stats[student.hostel]["students"] += 1
        for item in c.inventory.all_items():
            stats[item.owner.hostel]["items"] += 1
        for loan in c.loans.all_loans():
            if _went_out(loan):
                stats[loan.lender.hostel]["lent"] += 1
                stats[loan.borrower.hostel]["borrowed"] += 1
            if loan.status == LoanStatus.RETURNED:
                stats[loan.borrower.hostel]["returned"] += 1
                stats[loan.borrower.hostel]["on_time"] += int(_on_time(loan))
        ordered = sorted(stats.items(), key=lambda kv: (-kv[1]["lent"], kv[0].name))
        return [[hostel.name, data["students"], data["items"], data["lent"], data["borrowed"],
                 percent(data["on_time"], data["returned"])]
                for hostel, data in ordered]


class MyActivityReport(Report):
    """One student's own lending and borrowing history."""

    def __init__(self, community, student: Student):
        super().__init__(community)
        self._student = student

    @property
    def title(self) -> str:
        return f"Activity for {self._student.full_name}"

    def headers(self) -> List[str]:
        return ["Loan", "Role", "Item", "Other person", "From", "Until", "Status"]

    def rows(self) -> List[Row]:
        rows: List[Row] = []
        for loan in sorted(self._community.loans.loans_of(self._student), key=lambda x: x.start_at):
            lending = loan.lender is self._student
            other = loan.borrower if lending else loan.lender
            rows.append([
                loan.id,
                "Lent" if lending else "Borrowed",
                loan.item.title,
                other.full_name,
                f"{loan.start_at:%d %b %H:%M}",
                f"{loan.due_at:%d %b %H:%M}",
                loan.status.value,
            ])
        return rows
