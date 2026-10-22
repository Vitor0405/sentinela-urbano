"""Visit route suggestion for an agent (backlog story 13).

Two steps, so that proximity never overrides risk entirely:
1. *Which* stops: the top `max_stops` of the agent's risk-ordered queue.
2. *In which order*: shortest path from the agent's position through those stops
   (nearest-neighbour start, improved with 2-opt). The route is open: it does not return.

Distances are straight lines (haversine). A street-network router (e.g. OSRM) would give
real travel distances; that is a later improvement, not needed to order a dozen stops.
"""

from dataclasses import dataclass

from app.services.privacy import distance_m

Point = tuple[float, float]  # (lat, lon)


@dataclass(frozen=True)
class Stop:
    id: int
    lat: float
    lon: float


@dataclass(frozen=True)
class PlannedRoute:
    order: list[int]  # stop ids, in visiting order
    legs_m: list[float]  # distance of each leg: start→1st, 1st→2nd, …
    total_m: float


def _path_length(start: Point, stops: list[Stop]) -> float:
    total, here = 0.0, start
    for s in stops:
        total += distance_m(*here, s.lat, s.lon)
        here = (s.lat, s.lon)
    return total


def _nearest_neighbour(start: Point, stops: list[Stop]) -> list[Stop]:
    remaining, path, here = list(stops), [], start
    while remaining:
        nxt = min(remaining, key=lambda s: (distance_m(*here, s.lat, s.lon), s.id))
        remaining.remove(nxt)
        path.append(nxt)
        here = (nxt.lat, nxt.lon)
    return path


def _two_opt(start: Point, path: list[Stop]) -> list[Stop]:
    """Reverse segments while it shortens the open path (start fixed)."""
    best, best_len = path, _path_length(start, path)
    improved = True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                candidate = best[:i] + best[i : j + 1][::-1] + best[j + 1 :]
                length = _path_length(start, candidate)
                if length < best_len - 1e-6:
                    best, best_len, improved = candidate, length, True
    return best


def plan_route(start: Point, stops: list[Stop]) -> PlannedRoute:
    path = _two_opt(start, _nearest_neighbour(start, stops))
    legs, here = [], start
    for s in path:
        legs.append(round(distance_m(*here, s.lat, s.lon), 1))
        here = (s.lat, s.lon)
    return PlannedRoute(order=[s.id for s in path], legs_m=legs, total_m=round(sum(legs), 1))
