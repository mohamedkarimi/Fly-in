*This project has been created as part of the 42 curriculum by mokarimi.*

# Fly-in

## Description

Fly-in is a turn-based drone-routing simulation. A map describes a bidirectional graph of named zones and connections: one start hub, one end hub, optional intermediate hubs, their coordinates, zone metadata, and connection capacities. The program routes the requested number of drones from the start hub to the end hub while producing a line-oriented movement trace.

The goal of this implementation is to find static least-cost guidance to the end, then schedule drone movements without exceeding the configured zone or connection capacities. Maps may contain normal, blocked, restricted, and priority zones. The supplied maps range from small linear graphs to maps with bottlenecks, loops, restricted zones, and competing routes.

## Instructions

### Requirements and setup

The program uses Python 3 and only the standard library at runtime. Run it from the repository root:

```sh
python3 main.py maps/easy/01_linear_path.txt
```

The `Makefile` provides an optional installation target for the development tools:

```sh
make install
```

This installs `flake8` and `mypy` with `pip3`. A virtual environment may be used if preferred; activate it before running `make install` or `make lint`.

### Running a map

The command-line interface accepts exactly one positional argument, the map file. `-h`/`--help` is supplied by `argparse`.

```sh
python3 main.py maps/easy/02_simple_fork.txt
make run MAP=maps/medium/03_priority_puzzle.txt
make debug MAP=maps/easy/01_linear_path.txt
```

`make run` invokes `python3 main.py $(MAP)`, and `make debug` runs the same command under `pdb`. The supplied maps are in `maps/easy`, `maps/medium`, `maps/hard`, and `maps/challenger`.

## Algorithm Explanation

### Static path calculation

`Pathfinder.compute()` runs Dijkstra's algorithm from the end hub over the undirected graph. The reverse traversal charges the movement cost of the zone being entered in the forward direction: normal and priority zones cost 1, and restricted zones cost 2. Blocked zones are not traversed. The result is a cached distance-to-end for each reachable, accessible zone.

For each zone, the pathfinder also caches its reachable neighboring zones ordered by:

1. total cost through that neighbor;
2. whether that neighbor is a priority zone; and
3. its name.

During simulation, a drone uses only a candidate whose cost preserves the cached shortest distance. Therefore, a temporarily unavailable shortest hop makes the drone wait; it does not take a longer detour. Priority is a tie-breaker between otherwise equal candidate costs, not a separate lower movement cost. The cache is computed once before the simulation and is not recalculated in response to congestion.

With `V` zones and `E` connections, the heap-based Dijkstra pass is `O((V + E) log V)`. Building and sorting the candidate lists costs `O(sum(deg(v) log deg(v)))`, bounded by `O(E log V)`. These are static-routing costs; the turn scheduler additionally iterates over the drones and candidate hops each turn.

### Movement selection and conflicts

At the start of each turn, drones already travelling to restricted zones advance their transit counter. Ready drones are then ordered by increasing cached distance to the end, then by number of candidate hops, then by drone ID. Considering downstream drones first allows a departure to free a normal hub's capacity before another drone is considered for arrival in the same turn.

For each ready drone, the simulator selects the first feasible shortest-path hop. While planning the turn, it reserves the destination occupancy and the connection usage, so later planned moves see the earlier reservations. A drone waits when no such hop has both available zone and connection capacity. This is the implementation's conflict resolution: there is no backtracking, random selection, or global re-optimization.

Non-terminal hubs default to capacity 1 unless `max_drones` is supplied. The start and end hubs are unlimited. A connection defaults to capacity 1 unless `max_link_capacity` is supplied; connection usage is shared in both directions. Drones in restricted transit count against their connection's capacity until they arrive, and reserve a slot in their destination zone for the full transit so they can never wait on the connection for capacity.

## Simulation and Movement Rules

- Every drone begins in the start hub. Normal and priority destinations are reached in the same simulated turn in which their move is applied.
- Entering a blocked zone is disallowed by the pathfinder.
- Entering a restricted zone uses two turns: the launch onto its connection, then arrival on the following turn. The launch is rendered with the connection name. When transit completes, the drone's arrival at the restricted zone is rendered as a movement token; it cannot take another hop until the next turn.
- Drones physically present in ordinary hubs are counted for occupancy. The start and end hubs do not impose an occupancy limit.
- A drone moved to the end hub is immediately marked delivered and is not considered in later turns.
- The simulation ends after all drones are delivered. If an entire turn makes no move and advances no restricted transit, it stops with `Simulation stalled before all drones reached the end zone.`

## Visual Representation

The project has no graphical interface. `Visualizer` emits plain terminal lines, one non-empty output line per turn that contains recorded movements. A normal movement token is `D<ID>-<zone>`; the launch toward a restricted zone is `D<ID>-<connection>`.

When standard output is an interactive terminal with a non-`dumb` `TERM`, a destination's optional `color` metadata is emitted as an ANSI color around the target portion of the token. The formatter recognizes the ANSI color names defined in `visualizer.py`; unrecognized or absent colors leave the token uncolored. When output is redirected or the terminal does not support color, the same tokens are plain text.

## Usage Example

`maps/easy/01_linear_path.txt` contains two drones and the path `start -> waypoint1 -> waypoint2 -> goal`.

```sh
TERM=dumb python3 main.py maps/easy/01_linear_path.txt
```

Representative output from the current implementation:

```text
D1-waypoint1
D1-waypoint2 D2-waypoint1
D1-goal D2-waypoint2
D2-goal
Simulation finished in 4 turns.
```

## Project Structure

- `main.py` — command-line entry point; parses a map, computes routing, runs the simulation, and prints output.
- `parser.py` — validates the map format and constructs the graph.
- `models.py` — zone types and the `Zone`, `Connection`, `Drone`, and `SimulationMove` data models.
- `graph.py` — graph storage, bidirectional adjacency, and zone/connection lookup.
- `pathfinder.py` — reverse Dijkstra calculation and cached ordered next hops.
- `simulator.py` — turn loop, capacity checks, movement planning, transit state, and delivery tracking.
- `visualizer.py` — plain-text and ANSI-coloured movement formatting.
- `maps/` — example input maps; `maps/README.md` describes their categories.
- `Makefile` — installation, run, debug, clean, and lint targets.

## Input Validation and Limitations

The parser ignores blank lines and `#` comments, requires the first non-empty line to declare a positive `nb_drones`, and validates zone names, unique coordinates, metadata keys, capacities, duplicate connections, and the presence of one start and end hub. Invalid map input is reported as a `ParseError` with its line number. Before simulation, the program also reports a missing start hub or the absence of a valid path from start to end.

Routing is static and shortest-path-only. Consequently, it may wait at a congested shortest route even when a longer route exists. The scheduler is greedy and does not claim to minimize the total number of turns. There are no repository unit or integration tests, no benchmark runner, and no graphical visualization.

## Testing

There is no dedicated test suite or test configuration in this repository. The available checks are the Makefile's lint target:

```sh
make lint
```

It runs `flake8 . --exclude=.venv,__pycache__,.mypy_cache,.pytest_cache`, followed by `mypy .` with the flags defined in the `Makefile`. `make clean` removes Python bytecode and the named cache directories. The example command in [Usage Example](#usage-example) was run successfully while preparing this README; run the commands above locally to check your environment.

## Resources

- [Fly-in subject](en.subject.pdf) — the project specification included in this repository.
- [Python `heapq` documentation](https://docs.python.org/3/library/heapq.html) — priority-queue operations used by `pathfinder.py`.
- [Python `argparse` documentation](https://docs.python.org/3/library/argparse.html) — command-line parsing used by `main.py`.
- [Dijkstra's algorithm](https://doi.org/10.1007/BF01386390) — E. W. Dijkstra's original shortest-path paper; this is the algorithm implemented for static routing.

### AI-use disclosure

AI tools were used as a learning and support resource during the project.
