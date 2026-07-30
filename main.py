"""Command-line entrypoint for the Fly-in simulator."""

from __future__ import annotations

import argparse
import sys

from parser import MapParser, ParseError
from pathfinder import Pathfinder
from simulator import Simulator
from visualizer import Visualizer


def main() -> int:
    """Run the Fly-in simulation from a map file path."""
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("map_file")
    args = argument_parser.parse_args()

    try:
        drone_count, graph = MapParser(args.map_file).parse()
    except ParseError as error:
        print(str(error), file=sys.stderr)
        return 1

    pathfinder = Pathfinder(graph)
    pathfinder.compute()

    simulator = Simulator(graph, pathfinder)
    simulator.initialize_drones(drone_count)
    history = simulator.run()

    output = Visualizer().format(history)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
