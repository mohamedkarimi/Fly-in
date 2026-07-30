"""Graph storage for the Fly-in project."""

from __future__ import annotations

from dataclasses import dataclass, field

from models import Connection, Zone


@dataclass(slots=True)
class Graph:
    """Store zones, connections, and adjacency information."""

    zones: dict[str, Zone] = field(default_factory=dict)
    connections: dict[frozenset[str], Connection] = field(default_factory=dict)
    adjacency: dict[str, list[str]] = field(default_factory=dict)
    start_zone: str | None = None
    end_zone: str | None = None

    def add_zone(self, zone: Zone) -> None:
        """Add a zone to the graph and register special endpoints."""
        self.zones[zone.name] = zone
        self.adjacency[zone.name] = []

        if zone.is_start:
            self.start_zone = zone.name
        if zone.is_end:
            self.end_zone = zone.name

    def add_connection(self, connection: Connection) -> None:
        """Add a bidirectional connection and update adjacency lists."""
        key = frozenset((connection.zone_a, connection.zone_b))
        self.connections[key] = connection
        self.adjacency[connection.zone_a].append(connection.zone_b)
        self.adjacency[connection.zone_b].append(connection.zone_a)

    def has_zone(self, name: str) -> bool:
        """Return whether a zone exists in the graph."""
        return name in self.zones

    def get_zone(self, name: str) -> Zone:
        """Return the zone with the given name."""
        return self.zones[name]

    def get_connection(self, zone_a: str, zone_b: str) -> Connection:
        """Return the connection linking the two given zones."""
        key = frozenset((zone_a, zone_b))
        return self.connections[key]

    def neighbors(self, zone_name: str) -> list[Zone]:
        """Return the neighboring zones of the given zone."""
        return [self.zones[name] for name in self.adjacency[zone_name]]
