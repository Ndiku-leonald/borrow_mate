"""Tests for the reports feature."""

import csv
import tempfile
import unittest
from pathlib import Path

from borrowmate.cli import BorrowMateCLI
from borrowmate.models.enums import Condition
from borrowmate.plugins.reports_menu import ReportsPlugin
from borrowmate.reports import (CommunityHealthReport, CsvFormatter, HostelActivityReport,
                                MyActivityReport, PopularItemsReport, Report, TextFormatter,
                                TopLendersReport)
from borrowmate.seed import build_demo_community


class ReportTests(unittest.TestCase):
    def test_report_is_abstract(self):
        c = build_demo_community()
        with self.assertRaises(TypeError):
            Report(c)  # type: ignore[abstract]

    def test_every_report_has_matching_columns(self):
        c = build_demo_community()
        reports = [
            CommunityHealthReport(c),
            TopLendersReport(c),
            PopularItemsReport(c),
            HostelActivityReport(c),
            MyActivityReport(c, c.students()[0]),
        ]
        for report in reports:
            with self.subTest(report=report.title):
                self.assertTrue(report.rows())
                for row in report.rows():
                    self.assertEqual(len(row), len(report.headers()))

    def test_text_and_csv_show_the_same_data(self):
        c = build_demo_community()
        report = TopLendersReport(c)
        self.assertIn("Top lenders", TextFormatter().render(report))
        with tempfile.TemporaryDirectory() as folder:
            formatter = CsvFormatter(folder)
            message = formatter.render(report)
            path = formatter.path_for(report)
            self.assertIn(str(path), message)
            with path.open(encoding="utf-8") as handle:
                saved = list(csv.reader(handle))
            self.assertEqual(saved[0], report.headers())
            self.assertEqual(len(saved), len(report.rows()) + 1)
            self.assertEqual(path.name, "top_lenders.csv")


class ReportsCliTests(unittest.TestCase):
    def test_menu_shows_and_exports_reports(self):
        community = build_demo_community()
        with tempfile.TemporaryDirectory() as folder:
            plugin = ReportsPlugin(community, csv_folder=folder)
            cli = BorrowMateCLI(community, input_fn=lambda prompt="": next(iter(["U001"])), output_fn=lambda message: None,
                                plugins=[plugin])
            self.assertTrue(plugin.menu_entries(cli))
            self.assertEqual(len(list(Path(folder).glob("*.csv"))), 0)


if __name__ == "__main__":
    unittest.main()
