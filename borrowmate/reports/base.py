"""Report building blocks."""

import csv
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from borrowmate.cli.display import table

Row = List[object]


class Report(ABC):
    """A titled table of calculated facts."""

    def __init__(self, community):
        self._community = community

    @property
    @abstractmethod
    def title(self) -> str:
        """Heading shown above the report."""

    @abstractmethod
    def headers(self) -> List[str]:
        """Column names."""

    @abstractmethod
    def rows(self) -> List[Row]:
        """The report data, one row per list."""

    def is_empty(self) -> bool:
        return not self.rows()


class ReportFormatter(ABC):
    """Turns any report into some output form."""

    @abstractmethod
    def render(self, report: Report) -> str:
        """Return the formatted content or a file message."""


class TextFormatter(ReportFormatter):
    """Aligned plain-text table for the terminal."""

    def render(self, report: Report) -> str:
        return f"\n=== {report.title} ===\n\n" + table(report.headers(), report.rows())


class CsvFormatter(ReportFormatter):
    """Save the report as a CSV file for spreadsheet use."""

    def __init__(self, folder: str = "reports"):
        self._folder = Path(folder)

    def path_for(self, report: Report) -> Path:
        slug = "".join(ch if ch.isalnum() else "_" for ch in report.title.lower()).strip("_")
        while "__" in slug:
            slug = slug.replace("__", "_")
        return self._folder / f"{slug}.csv"

    def render(self, report: Report) -> str:
        path = self.path_for(report)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(report.headers())
            writer.writerows(report.rows())
        return f"  Saved {report.title} to {path}"


def percent(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f}%" if whole else "-"
