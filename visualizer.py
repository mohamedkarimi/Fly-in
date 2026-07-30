"""Formatting utilities for simulator output."""

from __future__ import annotations


class Visualizer:
    """Convert simulation history into printable text."""

    def format(self, history: list[list[str]]) -> str:
        """Return the formatted turn-by-turn output string."""
        lines = [" ".join(turn_moves) for turn_moves in history if turn_moves]
        return "\n".join(lines)
