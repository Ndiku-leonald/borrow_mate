"""Menu options for reports and statistics."""

from typing import List

from borrowmate.cli.plugin import MenuEntry, MenuPlugin
from borrowmate.models.person import Student
from borrowmate.reports import (CommunityHealthReport, CsvFormatter, HostelActivityReport,
                                MyActivityReport, PopularItemsReport, Report, TextFormatter,
                                TopLendersReport)


class ReportsPlugin(MenuPlugin):
    order = 30

    def __init__(self, community, csv_folder: str = "reports"):
        super().__init__(community)
        self.text = TextFormatter()
        self.csv = CsvFormatter(csv_folder)

    def community_reports(self) -> List[Report]:
        return [
            CommunityHealthReport(self.community),
            TopLendersReport(self.community),
            PopularItemsReport(self.community),
            HostelActivityReport(self.community),
        ]

    def menu_entries(self, cli) -> List[MenuEntry]:
        entries = [("Community reports", lambda: self.show_community(cli))]
        if isinstance(getattr(cli, "_user", None), Student):
            entries.append(("My activity report", lambda: self.show_mine(cli)))
        entries.append(("Export reports to CSV", lambda: self.export(cli)))
        return entries

    def show_community(self, cli) -> None:
        for report in self.community_reports():
            writer = getattr(cli, "say", None) or getattr(cli, "_say")
            writer(self.text.render(report))

    def show_mine(self, cli) -> None:
        writer = getattr(cli, "say", None) or getattr(cli, "_say")
        writer(self.text.render(MyActivityReport(self.community, cli._user)))

    def export(self, cli) -> None:
        reports = self.community_reports()
        if isinstance(getattr(cli, "_user", None), Student):
            reports.append(MyActivityReport(self.community, cli._user))
        for report in reports:
            writer = getattr(cli, "say", None) or getattr(cli, "_say")
            writer(self.csv.render(report))
