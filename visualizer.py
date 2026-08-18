"""Formatting utilities for simulator output."""

from __future__ import annotations

import os
import sys

from graph import Graph
from models import SimulationMove


ANSI_RESET = "\033[0m"
ANSI_COLORS: dict[str, str] = {
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "bright_black": "\033[90m",
    "bright_red": "\033[91m",
    "bright_green": "\033[92m",
    "bright_yellow": "\033[93m",
    "bright_blue": "\033[94m",
    "bright_magenta": "\033[95m",
    "bright_cyan": "\033[96m",
    "bright_white": "\033[97m",
    "gray": "\033[90m",
    "grey": "\033[90m",
    "orange": "\033[38;5;208m",
    "purple": "\033[38;5;129m",
    "pink": "\033[38;5;213m",
    "brown": "\033[38;5;94m",
}


class Visualizer:
    """Convert simulation history into printable text."""

    def __init__(self, graph: Graph, use_color: bool | None = None) -> None:
        """Initialize the formatter with graph metadata."""
        self.graph = graph
        self.use_color = (
            self._stdout_supports_color()
            if use_color is None
            else use_color
        )

    def format(self, history: list[list[SimulationMove]]) -> str:
        """Return the formatted turn-by-turn output string."""
        lines = [
            " ".join(self._format_move(move) for move in turn_moves)
            for turn_moves in history
            if turn_moves
        ]
        return "\n".join(lines)

    def _format_move(self, move: SimulationMove) -> str:
        """Return one movement token, colored when metadata is available."""
        token = move.token()
        if not self.use_color or move.destination_zone is None:
            return token

        zone = self.graph.zones.get(move.destination_zone)
        if zone is None or zone.color is None:
            return token

        color_code = ANSI_COLORS.get(zone.color.lower())
        if color_code is None:
            return token

        prefix = f"{move.drone_label}-"
        return f"{prefix}{color_code}{move.target}{ANSI_RESET}"

    def _stdout_supports_color(self) -> bool:
        """Return whether ANSI colors should be emitted."""
        term = os.environ.get("TERM", "")
        return sys.stdout.isatty() and term != "dumb"
