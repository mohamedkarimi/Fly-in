"""Standalone module to render the drone simulator using pygame.

This module is designed for debugging purposes only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import sys
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from simulator import Simulator
    from models import Drone
    from graph import Graph

# Allowed global variables for Pygame resources
_window: pygame.Surface | None = None
_clock: pygame.time.Clock | None = None
_font: pygame.font.Font | None = None


class Mode(Enum):
    """Supported visualizer modes."""

    STEP = "STEP"
    TURN = "TURN"
    AUTO = "AUTO"


@dataclass(slots=True)
class DroneSnapshot:
    """Snapshot of a drone state for replay history."""

    drone_id: int
    current_zone: str | None
    in_transit: bool
    transit_connection: str | None
    transit_destination: str | None
    remaining_turns: int
    delivered: bool


@dataclass
class TurnSnapshot:
    """Snapshot of a simulation turn's visual state."""

    turn_number: int
    drones: list[DroneSnapshot]
    prev_positions: dict[int, tuple[float, float]]
    target_positions: dict[int, tuple[float, float]]
    is_finished: bool


class Visualizer:
    """Stores visualizer state across render calls.

    Does not use global variables.
    """

    prev_positions: dict[int, tuple[float, float]] = {}
    scaled_coords: dict[str, tuple[float, float]] = {}
    paused: bool = False

    # Debug modes state
    mode: Mode = Mode.STEP
    history: list[TurnSnapshot] = []
    replay_index: int | None = None


def make_drone_snapshot(drone: Drone) -> DroneSnapshot:
    """Create a snapshot of a drone's state."""
    return DroneSnapshot(
        drone_id=drone.drone_id,
        current_zone=drone.current_zone,
        in_transit=drone.in_transit,
        transit_connection=drone.transit_connection,
        transit_destination=drone.transit_destination,
        remaining_turns=drone.remaining_turns,
        delivered=drone.delivered,
    )


def _get_scaled_coords(graph: Graph) -> dict[str, tuple[float, float]]:
    """Scale and center coordinates to fit 80% of the 800x600 window.

    Ensures minimum spacing of 100px and 50px margins.
    """
    width, height = 800.0, 600.0
    target_w = width * 0.8  # 640.0
    target_h = height * 0.8  # 480.0

    coords: dict[str, tuple[float, float]] = {}
    if not graph.zones:
        return coords

    # If there is only one zone
    if len(graph.zones) == 1:
        zone_name = list(graph.zones.keys())[0]
        coords[zone_name] = (400.0, 300.0)
        return coords

    xs = [float(z.x) for z in graph.zones.values()]
    ys = [float(z.y) for z in graph.zones.values()]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    dx = max_x - min_x
    dy = max_y - min_y

    # Check for tiny/zero spans
    if dx < 1e-5:
        dx = 0.0
    if dy < 1e-5:
        dy = 0.0

    # Case 1: All nodes share identical raw coordinates
    if dx == 0.0 and dy == 0.0:
        n = len(graph.zones)
        spacing = 100.0
        total_w = (n - 1) * spacing
        if total_w > target_w:
            spacing = target_w / (n - 1) if n > 1 else 100.0
            total_w = target_w
        start_x = 400.0 - total_w / 2.0
        for i, zone_name in enumerate(sorted(graph.zones.keys())):
            coords[zone_name] = (start_x + i * spacing, 300.0)
        return coords

    # Case 2: All nodes share the same Y coordinate (horizontal line)
    if dy == 0.0:
        scale = target_w / dx
        raw_cx = min_x + dx / 2.0
        for zone_name, zone in graph.zones.items():
            px = 400.0 + (float(zone.x) - raw_cx) * scale
            coords[zone_name] = (px, 300.0)
        return coords

    # Case 3: All nodes share the same X coordinate (vertical line)
    if dx == 0.0:
        scale = target_h / dy
        raw_cy = min_y + dy / 2.0
        for zone_name, zone in graph.zones.items():
            py = 300.0 - (float(zone.y) - raw_cy) * scale
            coords[zone_name] = (400.0, py)
        return coords

    # Case 4: General 2D graph - scale to fit 80% while preserving aspect ratio
    scale_x = target_w / dx
    scale_y = target_h / dy
    scale = min(scale_x, scale_y)

    raw_cx = min_x + dx / 2.0
    raw_cy = min_y + dy / 2.0

    for zone_name, zone in graph.zones.items():
        px = 400.0 + (float(zone.x) - raw_cx) * scale
        py = 300.0 - (float(zone.y) - raw_cy) * scale
        coords[zone_name] = (px, py)

    return coords


def get_zone_offset(index: int, total: int) -> tuple[float, float]:
    """Calculate slot offsets to prevent drone overlapping inside zone."""
    if total <= 1:
        return (0.0, 0.0)
    elif total == 2:
        return [(-12.0, 0.0), (12.0, 0.0)][index]
    elif total == 3:
        return [(-10.0, 8.0), (10.0, 8.0), (0.0, -10.0)][index]
    elif total == 4:
        return [
            (-10.0, -10.0),
            (10.0, -10.0),
            (-10.0, 10.0),
            (10.0, 10.0),
        ][index]
    else:
        # Ring layout for 5+ drones
        angle = index * (2.0 * math.pi / total)
        r = 14.0
        return (r * math.cos(angle), r * math.sin(angle))


def get_drone_targets(simulator: Simulator) -> dict[int, tuple[float, float]]:
    """Compute target positions based on current simulator state."""
    graph = simulator.graph
    coords = Visualizer.scaled_coords

    # Group stationary drones by zone for slot layout offsets
    zone_drones: dict[str, list[Drone]] = {
        z_name: [] for z_name in graph.zones
    }
    for drone in simulator.drones:
        if not drone.in_transit and drone.current_zone:
            zone_drones[drone.current_zone].append(drone)

    for z_name in zone_drones:
        zone_drones[z_name].sort(key=lambda d: d.drone_id)

    targets: dict[int, tuple[float, float]] = {}

    for drone in simulator.drones:
        if not drone.in_transit:
            zone_name = drone.current_zone
            if zone_name:
                idx = zone_drones[zone_name].index(drone)
                total = len(zone_drones[zone_name])
                offset = get_zone_offset(idx, total)
                cx, cy = coords[zone_name]
                targets[drone.drone_id] = (cx + offset[0], cy + offset[1])
        else:
            dest = drone.transit_destination
            conn_name = drone.transit_connection

            conn = None
            if conn_name:
                for c in graph.connections.values():
                    if c.name == conn_name:
                        conn = c
                        break

            if dest and conn:
                source = conn.other_end(dest)
                p1 = coords[source]
                p2 = coords[dest]

                dest_zone = graph.get_zone(dest)
                total_turns = dest_zone.movement_cost()
                remaining = drone.remaining_turns

                fraction = (total_turns + 1 - remaining) / (total_turns + 1)

                tx = p1[0] + fraction * (p2[0] - p1[0])
                ty = p1[1] + fraction * (p2[1] - p1[1])
                targets[drone.drone_id] = (tx, ty)
            else:
                targets[drone.drone_id] = (0.0, 0.0)

    return targets


def draw_text(
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    center: tuple[int, int],
    outline_color: tuple[int, int, int] | None = (9, 9, 11),
) -> None:
    """Draw a centered text string with an optional outline for contrast."""
    if _window is None:
        return

    surf = font.render(text, True, color)
    rect = surf.get_rect(center=center)

    if outline_color is not None:
        offsets = [
            (-1, -1), (-1, 1), (1, -1), (1, 1),
            (0, -1), (0, 1), (-1, 0), (1, 0)
        ]
        for dx, dy in offsets:
            out_surf = font.render(text, True, outline_color)
            out_rect = out_surf.get_rect(
                center=(center[0] + dx, center[1] + dy)
            )
            _window.blit(out_surf, out_rect)

    _window.blit(surf, rect)


def _draw_scene(
    graph: Graph,
    snapshot: TurnSnapshot,
    moving_drone_ids: list[int],
    step_index: int,
    animating: bool,
    alpha: float,
) -> None:
    """Render all elements (connections, zones, drones, texts)."""
    if _window is None or _font is None:
        return

    coords = Visualizer.scaled_coords

    # Clear screen (dark gray background)
    _window.fill((24, 24, 27))

    # 1. Compute connection usage
    link_usage: dict[str, int] = {
        conn.name: 0 for conn in graph.connections.values()
    }
    for drone in snapshot.drones:
        if drone.in_transit and drone.transit_connection:
            link_usage[drone.transit_connection] += 1

    # 2. Draw connections
    for conn in graph.connections.values():
        p1 = coords[conn.zone_a]
        p2 = coords[conn.zone_b]

        zone_a_res = (
            graph.get_zone(conn.zone_a).zone_type.value == "restricted"
        )
        zone_b_res = (
            graph.get_zone(conn.zone_b).zone_type.value == "restricted"
        )
        is_restricted = zone_a_res or zone_b_res

        color = (239, 68, 68) if is_restricted else (100, 116, 139)
        width = max(2, int(conn.max_link_capacity * 1.5))

        pygame.draw.line(_window, color, p1, p2, width)

        # Connection label: name (usage/capacity)
        usage = link_usage.get(conn.name, 0)
        label = f"{conn.name} ({usage}/{conn.max_link_capacity})"
        mx = (p1[0] + p2[0]) / 2.0
        my = (p1[1] + p2[1]) / 2.0

        # Offset perpendicular to avoid overlapping line
        dy = p2[1] - p1[1]
        dx = p2[0] - p1[0]
        length = math.hypot(dx, dy)
        if length > 0:
            mx += (-dy / length) * 12.0
            my += (dx / length) * 12.0

        draw_text(label, _font, (226, 232, 240), (int(mx), int(my)))

    # 3. Draw zones
    occupancies: dict[str, int] = {z_name: 0 for z_name in graph.zones}
    for drone in snapshot.drones:
        if not drone.in_transit and drone.current_zone:
            occupancies[drone.current_zone] += 1

    for zone_name, zone in graph.zones.items():
        pos = coords[zone_name]

        if zone.is_start:
            color = (46, 204, 113)
        elif zone.is_end:
            color = (30, 130, 76)
        else:
            t = zone.zone_type.value
            if t == "normal":
                color = (93, 173, 226)
            elif t == "priority":
                color = (26, 188, 156)
            elif t == "restricted":
                color = (231, 76, 60)
            elif t == "blocked":
                color = (230, 126, 34)
            else:
                color = (93, 173, 226)

        pygame.draw.circle(_window, color, (int(pos[0]), int(pos[1])), 30)
        pygame.draw.circle(
            _window, (255, 255, 255), (int(pos[0]), int(pos[1])), 30, 2
        )

        # Name above circle
        draw_text(
            zone.name, _font, (244, 244, 245), (int(pos[0]), int(pos[1] - 42))
        )

        # Occupancy inside circle
        occ = occupancies.get(zone_name, 0)
        cap = (
            "∞"
            if (zone.is_start or zone.is_end or zone.max_drones is None)
            else str(zone.max_drones)
        )
        txt = f"{occ}/{cap}"

        text_color = (
            (255, 255, 255)
            if color in [(30, 130, 76), (231, 76, 60)]
            else (9, 9, 11)
        )
        draw_text(
            txt,
            _font,
            text_color,
            (int(pos[0]), int(pos[1])),
            outline_color=None,
        )

    # 4. Draw drones
    for drone in snapshot.drones:
        d_id = drone.drone_id
        start_pos = snapshot.prev_positions.get(
            d_id, snapshot.target_positions.get(d_id, (400.0, 300.0))
        )
        target_pos = snapshot.target_positions.get(d_id, (400.0, 300.0))

        # Position determination based on current step/animation mode
        if d_id not in moving_drone_ids:
            px, py = target_pos
        else:
            if Visualizer.mode == Mode.STEP:
                idx = moving_drone_ids.index(d_id)
                if idx < step_index:
                    px, py = target_pos
                elif idx > step_index:
                    px, py = start_pos
                else:  # idx == step_index
                    px = start_pos[0] + alpha * (target_pos[0] - start_pos[0])
                    py = start_pos[1] + alpha * (target_pos[1] - start_pos[1])
            else:  # TURN or AUTO mode
                px = start_pos[0] + alpha * (target_pos[0] - start_pos[0])
                py = start_pos[1] + alpha * (target_pos[1] - start_pos[1])

        # Draw yellow drone circle
        pygame.draw.circle(_window, (253, 224, 71), (int(px), int(py)), 8)
        pygame.draw.circle(_window, (9, 9, 11), (int(px), int(py)), 8, 1)

        # Drone ID label
        draw_text(
            f"D{d_id}",
            _font,
            (253, 224, 71),
            (int(px) + 16, int(py) - 8),
        )

    # 5. Draw header title
    mode_str = Visualizer.mode.value
    if Visualizer.mode == Mode.AUTO and Visualizer.paused:
        mode_str += " - PAUSED"
    status = f"FINISHED | {mode_str}" if snapshot.is_finished else mode_str
    draw_text(
        f"Turn {snapshot.turn_number} [{status}]",
        _font,
        (255, 255, 255),
        (400, 25),
    )


def render(simulator: Simulator) -> None:
    """Perform lazy window setup and run debugging mode visualizer loop."""
    global _window, _clock, _font

    if _window is None:
        pygame.init()
        _window = pygame.display.set_mode((800, 600))
        pygame.display.set_caption("Fly-in Live Debug Visualization")
        _clock = pygame.time.Clock()
        _font = pygame.font.SysFont("Helvetica", 14)

        # Scale coordinates
        Visualizer.scaled_coords = _get_scaled_coords(simulator.graph)

    # Assert non-None values for type checker safety
    assert _clock is not None

    # Take snapshot of new turn if needed
    if (
        not Visualizer.history
        or Visualizer.history[-1].turn_number < simulator.turn_number
    ):
        target_positions = get_drone_targets(simulator)
        if not Visualizer.history:
            start_zone = simulator.graph.start_zone
            start_pos = (400.0, 300.0)
            if start_zone and start_zone in Visualizer.scaled_coords:
                start_pos = Visualizer.scaled_coords[start_zone]
            prev_positions = {d.drone_id: start_pos for d in simulator.drones}
        else:
            prev_positions = Visualizer.history[-1].target_positions.copy()

        drone_snapshots = [make_drone_snapshot(d) for d in simulator.drones]
        snapshot = TurnSnapshot(
            turn_number=simulator.turn_number,
            drones=drone_snapshots,
            prev_positions=prev_positions,
            target_positions=target_positions,
            is_finished=simulator.is_finished(),
        )
        Visualizer.history.append(snapshot)

    advance_simulator = False
    last_active_turn = -1

    step_index = 0
    alpha = 0.0
    animating = False

    while not advance_simulator:
        # Determine active snapshot
        if Visualizer.replay_index is not None:
            active_idx = Visualizer.replay_index
        else:
            active_idx = len(Visualizer.history) - 1

        snapshot = Visualizer.history[active_idx]

        # Reset animation state if active snapshot changed
        if snapshot.turn_number != last_active_turn:
            last_active_turn = snapshot.turn_number
            step_index = 0
            alpha = 0.0
            animating = False

        # Determine moving drones
        moving_drone_ids = [
            d.drone_id
            for d in snapshot.drones
            if snapshot.prev_positions.get(d.drone_id)
            != snapshot.target_positions.get(d.drone_id)
        ]
        moving_drone_ids.sort()

        # Determine turn completion state
        if Visualizer.mode == Mode.STEP:
            turn_complete = step_index == len(moving_drone_ids)
        else:
            turn_complete = alpha >= 1.0 or not moving_drone_ids

        # Handle auto-start of animation in AUTO mode
        if Visualizer.mode == Mode.AUTO and not Visualizer.paused:
            if not animating and not turn_complete:
                animating = True
                alpha = 0.0
            elif turn_complete:
                if Visualizer.replay_index is not None:
                    Visualizer.replay_index += 1
                    if Visualizer.replay_index >= len(Visualizer.history):
                        Visualizer.replay_index = None
                else:
                    if not snapshot.is_finished:
                        advance_simulator = True
                        break

        # Event polling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit(0)
                elif event.key == pygame.K_r:
                    # Restart from turn 0
                    Visualizer.replay_index = 0
                elif event.key == pygame.K_a:
                    Visualizer.mode = Mode.AUTO
                    Visualizer.paused = False
                elif event.key == pygame.K_SPACE:
                    if Visualizer.mode == Mode.AUTO:
                        Visualizer.paused = not Visualizer.paused
                    else:
                        Visualizer.mode = Mode.TURN
                        if not animating and not turn_complete:
                            animating = True
                            alpha = 0.0
                        elif turn_complete:
                            if Visualizer.replay_index is not None:
                                Visualizer.replay_index += 1
                                if (
                                    Visualizer.replay_index
                                    >= len(Visualizer.history)
                                ):
                                    Visualizer.replay_index = None
                            else:
                                if not snapshot.is_finished:
                                    advance_simulator = True
                elif (
                    event.key == pygame.K_RETURN
                    or event.key == pygame.K_KP_ENTER
                ):
                    Visualizer.mode = Mode.STEP
                    if not animating and step_index < len(moving_drone_ids):
                        animating = True
                        alpha = 0.0
                    elif turn_complete:
                        if Visualizer.replay_index is not None:
                            Visualizer.replay_index += 1
                            if (
                                Visualizer.replay_index
                                >= len(Visualizer.history)
                            ):
                                Visualizer.replay_index = None
                        else:
                            if not snapshot.is_finished:
                                advance_simulator = True

        # If advance_simulator was set in event loop
        if advance_simulator:
            break

        # Update animation progress
        if animating and not Visualizer.paused:
            dt = _clock.tick(60)
            alpha += dt / 1000.0
            if alpha >= 1.0:
                alpha = 1.0
                animating = False
                if Visualizer.mode == Mode.STEP:
                    step_index += 1
        else:
            _clock.tick(60)

        # Render scene
        _draw_scene(
            simulator.graph,
            snapshot,
            moving_drone_ids,
            step_index,
            animating,
            alpha,
        )
        pygame.display.flip()
