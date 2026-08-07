"""Simulation skeleton for the Fly-in project."""

from __future__ import annotations

from graph import Graph
from models import Drone, ZoneType
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

    def is_finished(self) -> bool:
        """Return whether all drones have reached the end zone."""
        return all(drone.delivered for drone in self.drones)

    def _choose_next_zone(self, drone: Drone) -> str | None:
        """Return the first reachable next hop for the given drone."""
        if drone.current_zone is None:
            return None

        next_hops = self.pathfinder.best_next_hops(drone.current_zone)
        if not next_hops:
            return None

        return next_hops[0]

    def _plan_moves(self) -> list[tuple[Drone, str]]:
        """Build a movement plan without mutating drone state."""
        planned_moves: list[tuple[Drone, str]] = []

        for drone in self.drones:
            if drone.delivered or drone.in_transit:
                continue

            next_zone = self._choose_next_zone(drone)
            if next_zone is None:
                continue

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
        occupancy: dict[str, int],
        link_usage: dict[str, int],
        turn_moves: list[str],
    ) -> None:
        """Apply planned moves directly and record turn output tokens."""
        for drone, destination in plan:
            source = drone.current_zone
            if source is None:
                continue

            if not self._can_enter_zone(destination, occupancy):
                continue

            destination_zone = self.graph.get_zone(destination)
            if destination_zone.zone_type is ZoneType.RESTRICTED:
                connection = self.graph.get_connection(source, destination)
                if not self._can_use_connection(connection.name, link_usage):
                    continue

                drone.start_transit(
                    connection.name,
                    destination,
                    destination_zone.movement_cost(),
                )
                occupancy[source] = occupancy.get(source, 0) - 1
                occupancy[destination] = occupancy.get(destination, 0) + 1
                link_usage[connection.name] = (
                    link_usage.get(connection.name, 0) + 1
                )
                turn_moves.append(f"{drone.label()}-{connection.name}")
                continue

            drone.move_to(destination)
            occupancy[source] = occupancy.get(source, 0) - 1
            occupancy[destination] = occupancy.get(destination, 0) + 1
            if destination == self.graph.end_zone:
                drone.mark_delivered()
            turn_moves.append(f"{drone.label()}-{destination}")

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

    def _advance_transit_drones(self) -> None:
        """Advance in-flight drones and complete any finished transit."""
        for drone in self.drones:
            if not drone.in_transit:
                continue

            if not drone.advance_transit():
                continue

            destination = drone.arrive()
            if destination == self.graph.end_zone:
                drone.mark_delivered()

    def run_turn(self) -> list[str]:
        """Execute one simulation turn and return its movement tokens."""
        self.turn_number += 1
        turn_moves: list[str] = []
        self._advance_transit_drones()
        occupancy = self._build_occupancy()
        link_usage = self._build_link_usage()
        planned_moves = self._plan_moves()
        self._apply_moves(planned_moves, occupancy, link_usage, turn_moves)
        # DEBUG DISPLAY (temporary)
        # Uncomment this line during development.
        #import display
        #display.render(self)

        return turn_moves

    def run(self) -> list[list[str]]:
        """Run the simulation loop skeleton and return recorded turn output."""
        history: list[list[str]] = []

        while not self.is_finished():
            turn_moves = self.run_turn()
            history.append(turn_moves)

            if not turn_moves:
                raise RuntimeError(
                    "Simulation stalled before all drones "
                    "reached the end zone."
                )

        return history
