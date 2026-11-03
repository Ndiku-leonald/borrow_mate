"""Plain-text formatting helpers for the CLI (no external libraries)."""

from datetime import datetime, timedelta
from typing import List, Sequence


def table(headers: Sequence[str], rows: List[Sequence[object]]) -> str:
    """Render rows as an aligned text table."""
    if not rows:
        return "  (nothing to show)"
    cells = [[str(h) for h in headers]] + [[str(c) for c in row] for row in rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(headers))]

    def line(row: Sequence[str]) -> str:
        return "  " + " | ".join(value.ljust(width) for value, width in zip(row, widths))

    divider = "  " + "-+-".join("-" * w for w in widths)
    return "\n".join([line(cells[0]), divider] + [line(r) for r in cells[1:]])


def heading(title: str) -> str:
    return f"\n=== {title} ===\n"


def when(moment: datetime) -> str:
    return f"{moment:%a %d %b %H:%M}"


def countdown(delta: timedelta) -> str:
    """'in 2h 15m' or '1h 30m late'."""
    minutes = int(delta.total_seconds() // 60)
    late = minutes < 0
    minutes = abs(minutes)
    days, minutes = divmod(minutes, 24 * 60)
    hours, minutes = divmod(minutes, 60)
    parts = ([f"{days}d"] if days else []) + ([f"{hours}h"] if hours else []) + [f"{minutes}m"]
    text = " ".join(parts)
    return f"{text} LATE" if late else f"in {text}"


def distance(metres: float) -> str:
    return f"{metres:.0f} m" if metres < 1000 else f"{metres / 1000:.1f} km"
