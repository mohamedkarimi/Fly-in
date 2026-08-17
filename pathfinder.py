"""Pathfinding logic for the Fly-in project."""

from __future__ import annotations

from dataclasses import dataclass, field
from heapq import heappop, heappush

from graph import Graph
from models import ZoneType


@dataclass(slots=True)
class Pathfinder:
    """Compute static shortest-path guidance toward the end zone."""

    graph: Graph
    distances_to_end: dict[str, int] = field(default_factory=dict)
    next_hops: dict[str, list[str]] = field(default_factory=dict)

    def compute(self) -> None:
        """Run Dijkstra from the end zone and cache routing guidance."""
        self.distances_to_end = {}
        self.next_hops = {}

        if self.graph.end_zone is None:
            return

        end_zone_name = self.graph.end_zone
        end_zone = self.graph.get_zone(end_zone_name)
        if not end_zone.is_accessible():
            return

        heap: list[tuple[int, str]] = [(0, end_zone_name)]
        self.distances_to_end[end_zone_name] = 0

        while heap:
            current_distance, current_name = heappop(heap)
            known_distance = self.distances_to_end.get(current_name)
            if known_distance is None or current_distance != known_distance:
                continue

            current_zone = self.graph.get_zone(current_name)
            for neighbor in self.graph.neighbors(current_name):
                if neighbor.zone_type is ZoneType.BLOCKED:
                    continue

                candidate_distance = (
                    current_distance + current_zone.movement_cost()
                )
                previous_distance = self.distances_to_end.get(neighbor.name)
                if (
                    previous_distance is None
                    or candidate_distance < previous_distance
                ):
                    self.distances_to_end[neighbor.name] = candidate_distance
                    heappush(heap, (candidate_distance, neighbor.name))

        for zone_name, zone in self.graph.zones.items():
            if zone.zone_type is ZoneType.BLOCKED:
                self.next_hops[zone_name] = []
                continue

            candidates: list[tuple[int, int, str]] = []
            for neighbor in self.graph.neighbors(zone_name):
                if neighbor.zone_type is ZoneType.BLOCKED:
                    continue

                neighbor_distance = self.distances_to_end.get(neighbor.name)
                if neighbor_distance is None:
                    continue

                total_distance = neighbor.movement_cost() + neighbor_distance
                priority_rank = (
                    0 if neighbor.zone_type is ZoneType.PRIORITY else 1
                )
                candidates.append(
                    (total_distance, priority_rank, neighbor.name)
                )

            candidates.sort()
            self.next_hops[zone_name] = [
                neighbor_name for _, _, neighbor_name in candidates
            ]

    def best_next_hops(self, zone_name: str) -> list[str]:
        """Return ordered candidate next hops toward the end zone."""
        return list(self.next_hops.get(zone_name, []))

    # def distance_from(self, zone_name: str) -> int | None:
    #     """Return the shortest distance from the zone to the end zone."""
    #     return self.distances_to_end.get(zone_name)

    # def is_reachable_from(self, zone_name: str) -> bool:
    #     """Return whether the end zone is reachable from the given zone."""
    #     return zone_name in self.distances_to_end
