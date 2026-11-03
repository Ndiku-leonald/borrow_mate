"""Hostel: the location unit of BorrowMate.

Privacy decision: users are located by the hostel they belong to, never by
live GPS. Distances are always hostel-to-hostel.
"""

from math import asin, cos, radians, sin, sqrt

from borrowmate.exceptions import ValidationError

_EARTH_RADIUS_M = 6_371_000


class Hostel:
    """A hostel or residence with a fixed map point."""

    def __init__(self, hostel_id: str, name: str, latitude: float, longitude: float):
        if not name or not name.strip():
            raise ValidationError("Hostel name cannot be empty.")
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValidationError("Hostel coordinates are out of range.")
        self._id = hostel_id
        self._name = name.strip()
        self._latitude = latitude
        self._longitude = longitude

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    def distance_to(self, other: "Hostel") -> float:
        """Great-circle distance to another hostel in metres (haversine)."""
        lat1, lon1 = radians(self._latitude), radians(self._longitude)
        lat2, lon2 = radians(other._latitude), radians(other._longitude)
        a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
        return 2 * _EARTH_RADIUS_M * asin(sqrt(a))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Hostel) and other._id == self._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __str__(self) -> str:
        return self._name

    def __repr__(self) -> str:
        return f"Hostel({self._id!r}, {self._name!r})"
