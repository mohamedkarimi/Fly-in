"""Domain models for the Fly-in project."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ZoneType(Enum):
    """Supported zone types defined by the subject."""

    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"


@dataclass(slots=True)
class Zone:
    """Represent a zone in the drone network."""

    name: str
    x: int
    y: int
    zone_type: ZoneType
    color: str | None
    max_drones: int | None
    is_start: bool
    is_end: bool

    def movement_cost(self) -> int:
        """Return the number of turns required to enter this zone."""
        if self.zone_type is ZoneType.RESTRICTED:
            return 2
        return 1

    def is_accessible(self) -> bool:
        """Return whether drones may enter this zone."""
        return self.zone_type is not ZoneType.BLOCKED


@dataclass(slots=True)
class Connection:
    """Represent a bidirectional connection between two zones."""

    zone_a: str
    zone_b: str
    max_link_capacity: int
    name: str


@dataclass(slots=True)
class Drone:
    """Represent one drone and its current simulation state."""

    drone_id: int
    current_zone: str | None
    in_transit: bool
    transit_connection: str | None
    transit_destination: str | None
    remaining_turns: int
    delivered: bool

    def start_transit(
        self,
        connection_name: str,
        destination: str,
        turns: int,
    ) -> None:
        """Put the drone into restricted-zone transit."""
        self.current_zone = None
        self.in_transit = True
        self.transit_connection = connection_name
        self.transit_destination = destination
        self.remaining_turns = turns

    def advance_transit(self) -> bool:
        """Advance restricted transit and report whether arrival is due now."""
        if not self.in_transit:
            raise ValueError(
                "Cannot advance transit for a drone that is not in transit."
            )
        if self.remaining_turns <= 0:
            raise ValueError(
                "Drone transit state is invalid: no turns remaining."
            )
        self.remaining_turns -= 1
        return self.remaining_turns == 0

    def arrive(self) -> str:
        """Complete restricted transit and return the destination zone name."""
        if not self.in_transit or self.transit_destination is None:
            raise ValueError(
                "Cannot complete arrival for a drone that is not in transit."
            )
        if self.remaining_turns != 0:
            raise ValueError(
                "Cannot complete arrival before transit is finished."
            )

        destination = self.transit_destination
        self.current_zone = destination
        self.in_transit = False
        self.transit_connection = None
        self.transit_destination = None
        self.remaining_turns = 0
        return destination

    def move_to(self, zone_name: str) -> None:
        """Move the drone directly to a zone in one turn."""
        self.current_zone = zone_name
        self.in_transit = False
        self.transit_connection = None
        self.transit_destination = None
        self.remaining_turns = 0

    def mark_delivered(self) -> None:
        """Mark the drone as delivered to the end zone."""
        self.delivered = True

    def label(self) -> str:
        """Return the printable drone identifier."""
        return f"D{self.drone_id}"


@dataclass(slots=True, frozen=True)
class SimulationMove:
    """Represent one rendered movement token for a simulation turn."""

    drone_label: str
    target: str
    destination_zone: str | None = None

    def token(self) -> str:
        """Return the plain-text movement token."""
        return f"{self.drone_label}-{self.target}"
