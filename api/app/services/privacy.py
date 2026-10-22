"""Coordinate obfuscation for the public map.

The public map never receives the exact point. Each coordinate is snapped to the centre
of a cell in a fixed grid of ~`cell_m` metres. The snapping is deterministic on purpose:
random jitter would let anyone average several reports of the same spot and converge on
the real location, while a grid always reveals the same cell and nothing more.

The longitude step is computed at a fixed reference latitude (the city's), so the grid
never shifts and cells are close to square across the service area.
"""

import math

METERS_PER_DEGREE_LAT = 111_320.0


def grid_steps(cell_m: float, ref_lat: float) -> tuple[float, float]:
    """Return (lat_step, lon_step) in degrees for a cell of `cell_m` metres."""
    if cell_m <= 0:
        raise ValueError("cell_m must be positive")
    if not -85.0 <= ref_lat <= 85.0:
        raise ValueError("ref_lat must be within [-85, 85]")
    lat_step = cell_m / METERS_PER_DEGREE_LAT
    lon_step = cell_m / (METERS_PER_DEGREE_LAT * math.cos(math.radians(ref_lat)))
    return lat_step, lon_step


def obfuscate_coordinate(
    lat: float, lon: float, *, cell_m: float, ref_lat: float
) -> tuple[float, float]:
    """Snap (lat, lon) to the centre of its grid cell. Returns (lat, lon)."""
    lat_step, lon_step = grid_steps(cell_m, ref_lat)
    snapped_lat = (math.floor(lat / lat_step) + 0.5) * lat_step
    snapped_lon = (math.floor(lon / lon_step) + 0.5) * lon_step
    return round(snapped_lat, 6), round(snapped_lon, 6)


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres (haversine). Used by tests and sanity checks."""
    r = 6_371_008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
