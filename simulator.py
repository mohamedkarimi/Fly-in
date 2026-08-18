"""Simulation skeleton for the Fly-in project."""

from __future__ import annotations

from graph import Graph
from models import Drone, SimulationMove, ZoneType
from pathfinder import Pathfinder


class Simulator:
    """Own drones and drive the high-level simulation loop."""

    def __init__(self, graph: Graph, pathfinder: Pathfinder) -> None:
        """Initialize the simulator with the static graph and pathfinder."""
        self.graph = graph
        self.pathfinder = pathfinder
        self.drones: list[Drone] = []
        self.turn_number = 0
        self._connection_capacities: dict[str, int] = {}
        self._last_turn_made_progress = False

    def initialize_drones(self, drone_count: int) -> None:
        """Create all drones at the start zone."""
        if self.graph.start_zone is None:
            raise ValueError("Cannot initialize drones without a start zone.")

        self.drones = [
            Drone(
                drone_id=drone_id,
                current_zone=self.graph.start_zone,
                in_transit=False,
                transit_connection=None,
                transit_destination=None,
                remaining_turns=0,
                delivered=False,
            )
            for drone_id in range(1, drone_count + 1)
        ]
        self.turn_number = 0
        self._last_turn_made_progress = False

    def is_finished(self) -> bool:
        """Return whether all drones have reached the end zone."""
        return all(drone.delivered for drone in self.drones)

    def _choose_next_zone(
        self,
        drone: Drone,
        occupancy: dict[str, int],
        link_usage: dict[str, int],
    ) -> str | None:
        """Return the best feasible next hop for the given drone.

        If the current best route is temporarily blocked, prefer waiting over
        taking a detour that is strictly worse than the shortest-known route.
        This keeps drones from cycling through loops when they should simply
        hold position for the optimal path to reopen.
        """
        source = drone.current_zone
        if source is None:
            return None

        source_distance = self.pathfinder.distance_from(source)
        for destination in self.pathfinder.best_next_hops(source):
            destination_distance = self.pathfinder.distance_from(destination)
            destination_zone = self.graph.get_zone(destination)
            if (
                source_distance is not None
                and destination_distance is not None
                and destination_zone.movement_cost() + destination_distance
                > source_distance
            ):
                continue

            if not self._can_enter_zone(destination, occupancy):
                continue

            connection = self.graph.get_connection(source, destination)
            if not self._can_use_connection(connection.name, link_usage):
                continue

            return destination

        return None

    def _iter_ready_drones(self) -> list[Drone]:
        """Return drones ready to move in downstream-first order.

        Scheduling zones that are closer to the end first lets drones vacate
        narrow hubs before upstream drones are considered, which matches the
        subject rule that departures free capacity for arrivals in the same
        turn.
        """
        ready_drones = [
            drone
            for drone in self.drones
            if not drone.delivered
            and not drone.in_transit
            and drone.current_zone is not None
        ]
        if not ready_drones:
            return []

        def sort_key(drone: Drone) -> tuple[int, int, int]:
            assert drone.current_zone is not None
            distance = self.pathfinder.distance_from(drone.current_zone)
            candidate_count = len(
                self.pathfinder.best_next_hops(drone.current_zone)
            )
            return (
                distance if distance is not None else 10**9,
                candidate_count,
                drone.drone_id,
            )

        return sorted(ready_drones, key=sort_key)

    def _plan_moves(
        self,
        occupancy: dict[str, int],
        link_usage: dict[str, int],
    ) -> list[tuple[Drone, str]]:
        """Build a movement plan while reserving zone and link capacity."""
        planned_moves: list[tuple[Drone, str]] = []

        for drone in self._iter_ready_drones():
            source = drone.current_zone
            if source is None:
                continue

            next_zone = self._choose_next_zone(drone, occupancy, link_usage)
            if next_zone is None:
                continue

            connection = self.graph.get_connection(source, next_zone)
            occupancy[source] = occupancy.get(source, 0) - 1
            occupancy[next_zone] = occupancy.get(next_zone, 0) + 1
            conn_name = connection.name
            link_usage[conn_name] = link_usage.get(conn_name, 0) + 1
            planned_moves.append((drone, next_zone))

        return planned_moves

    def _can_enter_zone(
        self,
        destination: str,
        occupancy: dict[str, int],
    ) -> bool:
        """Return whether the destination zone has capacity for entry."""
        zone = self.graph.get_zone(destination)
        if zone.is_start or zone.is_end:
            return True

        max_drones = zone.max_drones
        current_occupancy = occupancy.get(destination, 0)
        if max_drones is None:
            return current_occupancy < 1

        return current_occupancy < max_drones

    def _get_connection_capacity(self, connection_name: str) -> int | None:
        """Return the configured capacity for the named connection."""
        capacity = self._connection_capacities.get(connection_name)
        if capacity is not None:
            return capacity

        for connection in self.graph.connections.values():
            self._connection_capacities[connection.name] = (
                connection.max_link_capacity
            )

        return self._connection_capacities.get(connection_name)

    def _build_link_usage(self) -> dict[str, int]:
        """Count drones currently using each connection while in transit."""
        usage: dict[str, int] = {}

        for drone in self.drones:
            if not drone.in_transit or drone.transit_connection is None:
                continue

            connection_name = drone.transit_connection
            usage[connection_name] = usage.get(connection_name, 0) + 1

        return usage

    def _can_use_connection(
        self, connection_name: str, usage: dict[str, int]
    ) -> bool:
        """Return whether another drone may start using the connection."""
        capacity = self._get_connection_capacity(connection_name)
        if capacity is None:
            return False

        return usage.get(connection_name, 0) < capacity

    def _apply_moves(
        self,
        plan: list[tuple[Drone, str]],
        turn_moves: list[SimulationMove],
    ) -> None:
        """Apply an already validated movement plan."""
        for drone, destination in plan:
            source = drone.current_zone
            if source is None:
                continue

            destination_zone = self.graph.get_zone(destination)
            if destination_zone.zone_type is ZoneType.RESTRICTED:
                connection = self.graph.get_connection(source, destination)
                drone.start_transit(
                    connection.name,
                    destination,
                    destination_zone.movement_cost(),
                )
                turn_moves.append(
                    SimulationMove(
                        drone_label=drone.label(),
                        target=connection.name,
                        destination_zone=destination,
                    )
                )
                continue

            drone.move_to(destination)
            if destination == self.graph.end_zone:
                drone.mark_delivered()
            turn_moves.append(
                SimulationMove(
                    drone_label=drone.label(),
                    target=destination,
                    destination_zone=destination,
                )
            )

    def _build_occupancy(self) -> dict[str, int]:
        """Count drones currently present in each zone."""
        occupancy: dict[str, int] = {}

        for drone in self.drones:
            if (
                drone.delivered
                or drone.in_transit
                or drone.current_zone is None
            ):
                continue

            zone_name = drone.current_zone
            occupancy[zone_name] = occupancy.get(zone_name, 0) + 1

        return occupancy

    def _advance_transit_drones(self) -> bool:
        """Advance in-flight drones and report if transit progressed."""
        progressed = False

        for drone in self.drones:
            if not drone.in_transit:
                continue

            progressed = True
            if not drone.advance_transit():
                continue

            destination = drone.arrive()
            if destination == self.graph.end_zone:
                drone.mark_delivered()

        return progressed

    def run_turn(self) -> list[SimulationMove]:
        """Execute one simulation turn and return its movement tokens."""
        self.turn_number += 1
        turn_moves: list[SimulationMove] = []
        progressed_in_transit = self._advance_transit_drones()
        occupancy = self._build_occupancy()
        link_usage = self._build_link_usage()
        planned_moves = self._plan_moves(occupancy, link_usage)
        self._apply_moves(planned_moves, turn_moves)
        self._last_turn_made_progress = (
            progressed_in_transit or bool(turn_moves)
        )

        return turn_moves

    def run(self) -> list[list[SimulationMove]]:
        """Run the simulation loop skeleton and return recorded turn output."""
        history: list[list[SimulationMove]] = []

        while not self.is_finished():
            turn_moves = self.run_turn()
            history.append(turn_moves)

            if not self._last_turn_made_progress:
                raise RuntimeError(
                    "Simulation stalled before all drones "
                    "reached the end zone."
                )

        return history
