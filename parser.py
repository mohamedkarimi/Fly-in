"""Input parsing for the Fly-in project."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn

from graph import Graph
from models import Connection, Zone, ZoneType


class ParseError(Exception):
    """Raised when the input map file is invalid."""


@dataclass(slots=True)
class MapParser:
    """Parse a Fly-in map file and build the corresponding graph."""

    file_path: str
    line_number: int = 0

    def parse(self) -> tuple[int, Graph]:
        """Parse the map file and return the drone count and graph."""
        graph = Graph()
        drone_count: int | None = None

        with open(self.file_path, "r", encoding="utf-8") as file_obj:
            for current_line, raw_line in enumerate(file_obj, start=1):
                self.line_number = current_line
                stripped_line = self._strip_line(raw_line)
                if stripped_line is None:
                    continue

                if drone_count is None:
                    drone_count = self._parse_drone_count(stripped_line)
                    continue

                self._parse_entity_line(stripped_line, graph)

        if drone_count is None:
            self._error("Missing nb_drones declaration.")
        if graph.start_zone is None:
            self._error("Missing start_hub declaration.")
        if graph.end_zone is None:
            self._error("Missing end_hub declaration.")

        return drone_count, graph

    def _strip_line(self, raw_line: str) -> str | None:
        """Remove comments and surrounding whitespace from a line."""
        content = raw_line.split("#", maxsplit=1)[0].strip()
        return content or None

    def _parse_drone_count(self, line: str) -> int:
        """Parse and validate the required drone count declaration."""
        prefix = "nb_drones:"
        if not line.startswith(prefix):
            self._error("The first non-empty line must define nb_drones.")

        raw_value = line[len(prefix):].strip()
        if not raw_value:
            self._error("Missing drone count after nb_drones:.")
        if " " in raw_value:
            self._error("Invalid nb_drones syntax.")

        return self._parse_positive_int(
            raw_value,
            "Drone count must be a positive integer.",
        )

    def _parse_entity_line(self, line: str, graph: Graph) -> None:
        """Parse one zone or connection declaration."""
        if line.startswith("start_hub:"):
            zone = self._parse_zone(line[len("start_hub:"):].strip(), "start")
            if graph.start_zone is not None:
                self._error("Multiple start_hub declarations are not allowed.")
            if graph.has_zone(zone.name):
                self._error(f"Duplicate zone name: {zone.name}.")
            self._validate_unique_zone_coordinates(zone, graph)
            graph.add_zone(zone)
            return

        if line.startswith("end_hub:"):
            zone = self._parse_zone(line[len("end_hub:"):].strip(), "end")
            if graph.end_zone is not None:
                self._error("Multiple end_hub declarations are not allowed.")
            if graph.has_zone(zone.name):
                self._error(f"Duplicate zone name: {zone.name}.")
            self._validate_unique_zone_coordinates(zone, graph)
            graph.add_zone(zone)
            return

        if line.startswith("hub:"):
            zone = self._parse_zone(line[len("hub:"):].strip(), "hub")
            if graph.has_zone(zone.name):
                self._error(f"Duplicate zone name: {zone.name}.")
            self._validate_unique_zone_coordinates(zone, graph)
            graph.add_zone(zone)
            return

        if line.startswith("connection:"):
            connection = self._parse_connection(
                line[len("connection:"):].strip(),
                graph,
            )
            graph.add_connection(connection)
            return

        self._error("Unknown line type.")

    def _parse_zone(self, payload: str, zone_role: str) -> Zone:
        """Parse one zone declaration."""
        content, metadata = self._split_metadata(payload)
        parts = content.split()
        if len(parts) != 3:
            self._error("Invalid zone syntax.")

        name = parts[0]
        self._validate_zone_name(name)
        x = self._parse_int(parts[1], "Zone coordinates must be integers.")
        y = self._parse_int(parts[2], "Zone coordinates must be integers.")
        zone_metadata = self._parse_metadata(metadata)

        return self._build_zone(name, x, y, zone_role, zone_metadata)

    def _parse_connection(self, payload: str, graph: Graph) -> Connection:
        """Parse one connection declaration."""
        content, metadata = self._split_metadata(payload)
        if not content:
            self._error("Invalid connection syntax.")

        name_parts = content.split()
        if len(name_parts) != 1:
            self._error("Invalid connection syntax.")

        endpoints = name_parts[0].split("-")
        if len(endpoints) != 2:
            self._error("Connections must use the format zone1-zone2.")

        zone_a, zone_b = endpoints
        if not zone_a or not zone_b:
            self._error("Connections must use the format zone1-zone2.")
        if not graph.has_zone(zone_a) or not graph.has_zone(zone_b):
            self._error("Connections must reference previously defined zones.")

        key = frozenset((zone_a, zone_b))
        if key in graph.connections:
            self._error("Duplicate connection declaration.")

        connection_metadata = self._parse_metadata(metadata)
        return self._build_connection(zone_a, zone_b, connection_metadata)

    def _split_metadata(self, payload: str) -> tuple[str, str | None]:
        """Split a declaration payload into content and optional metadata."""
        payload = payload.strip()
        if not payload:
            self._error("Missing declaration content.")

        if "[" not in payload:
            return payload, None

        bracket_index = payload.find("[")
        if not payload.endswith("]"):
            self._error("Invalid metadata syntax.")

        content = payload[:bracket_index].strip()
        metadata = payload[bracket_index + 1:-1].strip()
        if "]" in metadata or "[" in metadata:
            self._error("Invalid metadata syntax.")
        if not content:
            self._error("Missing declaration content.")

        return content, metadata

    def _parse_metadata(self, raw_metadata: str | None) -> dict[str, str]:
        """Parse a metadata block into a key-value dictionary."""
        if raw_metadata is None:
            return {}
        if raw_metadata == "":
            return {}

        metadata: dict[str, str] = {}
        entries = raw_metadata.split()
        for entry in entries:
            if "=" not in entry:
                self._error("Metadata entries must use key=value syntax.")
            key, value = entry.split("=", maxsplit=1)
            if not key or not value:
                self._error("Metadata entries must use key=value syntax.")
            if key in metadata:
                self._error(f"Duplicate metadata key: {key}.")
            metadata[key] = value
        return metadata

    def _build_zone(
        self,
        name: str,
        x: int,
        y: int,
        zone_role: str,
        metadata: dict[str, str],
    ) -> Zone:
        """Create a validated Zone object."""
        zone_type = self._parse_zone_type(
            metadata.get("zone", ZoneType.NORMAL.value)
        )
        color = metadata.get("color")

        allowed_keys = {"zone", "color", "max_drones"}
        unknown_keys = set(metadata) - allowed_keys
        if unknown_keys:
            unknown_key = sorted(unknown_keys)[0]
            self._error(f"Unknown zone metadata key: {unknown_key}.")

        is_start = zone_role == "start"
        is_end = zone_role == "end"

        max_drones: int | None
        if is_start or is_end:
            max_drones = None
        else:
            raw_capacity = metadata.get("max_drones")
            if raw_capacity is None:
                max_drones = 1
            else:
                max_drones = self._parse_positive_int(
                    raw_capacity,
                    "Zone max_drones must be a positive integer.",
                )

        return Zone(
            name=name,
            x=x,
            y=y,
            zone_type=zone_type,
            color=color,
            max_drones=max_drones,
            is_start=is_start,
            is_end=is_end,
        )

    def _build_connection(
        self,
        zone_a: str,
        zone_b: str,
        metadata: dict[str, str],
    ) -> Connection:
        """Create a validated Connection object."""
        allowed_keys = {"max_link_capacity"}
        unknown_keys = set(metadata) - allowed_keys
        if unknown_keys:
            unknown_key = sorted(unknown_keys)[0]
            self._error(f"Unknown connection metadata key: {unknown_key}.")

        raw_capacity = metadata.get("max_link_capacity")
        if raw_capacity is None:
            max_link_capacity = 1
        else:
            max_link_capacity = self._parse_positive_int(
                raw_capacity,
                "Connection max_link_capacity must be a positive integer.",
            )

        return Connection(
            zone_a=zone_a,
            zone_b=zone_b,
            max_link_capacity=max_link_capacity,
            name=f"{zone_a}-{zone_b}",
        )

    def _validate_zone_name(self, name: str) -> None:
        """Validate zone naming rules and uniqueness assumptions."""
        if " " in name or "-" in name:
            self._error("Zone names may not contain spaces or dashes.")
        if not name:
            self._error("Zone name may not be empty.")

    def _validate_unique_zone_coordinates(self, zone: Zone, graph: Graph) -> None:
        """Reject zone declarations that reuse an existing coordinate pair."""
        for existing_zone in graph.zones.values():
            if (existing_zone.x, existing_zone.y) != (zone.x, zone.y):
                continue
            self._error(
                'Duplicate coordinates '
                f'({zone.x}, {zone.y}): zones "{existing_zone.name}" '
                f'and "{zone.name}".'
            )

    def _parse_zone_type(self, raw_value: str) -> ZoneType:
        """Parse and validate one zone type value."""
        try:
            return ZoneType(raw_value)
        except ValueError as error:
            raise ParseError(
                f"Line {self.line_number}: Invalid zone type: {raw_value}."
            ) from error

    def _parse_int(self, raw_value: str, error_message: str) -> int:
        """Parse a string as an integer or raise a parser error."""
        try:
            return int(raw_value)
        except ValueError as error:
            raise ParseError(
                f"Line {self.line_number}: {error_message}"
            ) from error

    def _parse_positive_int(self, raw_value: str, error_message: str) -> int:
        """Parse and validate a positive integer."""
        value = self._parse_int(raw_value, error_message)
        if value <= 0:
            self._error(error_message)
        return value

    def _error(self, message: str) -> NoReturn:
        """Raise a ParseError using the current line number."""
        raise ParseError(f"Line {self.line_number}: {message}")
