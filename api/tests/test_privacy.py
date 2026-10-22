"""Coordinate obfuscation for the public map (~100 m grid)."""

import math
import random

import pytest

from app.services.occurrences import in_bbox, parse_bbox
from app.services.privacy import distance_m, grid_steps, obfuscate_coordinate

CELL = 100.0
REF_LAT = -16.72  # Montes Claros (MG)
PRACA_DR_CHAVES = (-16.7207, -43.8660)
# Half the diagonal of a 100 m cell, plus slack for the curvature approximation.
MAX_DISPLACEMENT_M = CELL * math.sqrt(2) / 2 + 2


def snap(lat: float, lon: float) -> tuple[float, float]:
    return obfuscate_coordinate(lat, lon, cell_m=CELL, ref_lat=REF_LAT)


def test_snapped_point_never_equals_exact_point():
    lat, lon = PRACA_DR_CHAVES
    assert snap(lat, lon) != (lat, lon)


def test_points_in_the_same_cell_share_the_same_public_coordinate():
    lat_step, lon_step = grid_steps(CELL, REF_LAT)
    base_lat = (math.floor(PRACA_DR_CHAVES[0] / lat_step) + 0.1) * lat_step
    base_lon = (math.floor(PRACA_DR_CHAVES[1] / lon_step) + 0.1) * lon_step
    neighbour = (base_lat + 0.7 * lat_step, base_lon + 0.7 * lon_step)
    assert snap(base_lat, base_lon) == snap(*neighbour)


def test_is_deterministic_so_repeated_reports_cannot_be_averaged():
    lat, lon = PRACA_DR_CHAVES
    assert len({snap(lat, lon) for _ in range(50)}) == 1


def test_snapping_is_idempotent():
    once = snap(*PRACA_DR_CHAVES)
    assert snap(*once) == once


def test_displacement_is_bounded_by_half_cell_diagonal():
    rng = random.Random(7)
    for _ in range(2000):
        lat = PRACA_DR_CHAVES[0] + rng.uniform(-0.05, 0.05)
        lon = PRACA_DR_CHAVES[1] + rng.uniform(-0.05, 0.05)
        assert distance_m(lat, lon, *snap(lat, lon)) <= MAX_DISPLACEMENT_M


def test_neighbouring_cells_are_about_one_cell_apart():
    lat_step, lon_step = grid_steps(CELL, REF_LAT)
    a = snap(*PRACA_DR_CHAVES)
    north = snap(PRACA_DR_CHAVES[0] + lat_step, PRACA_DR_CHAVES[1])
    east = snap(PRACA_DR_CHAVES[0], PRACA_DR_CHAVES[1] + lon_step)
    assert distance_m(*a, *north) == pytest.approx(CELL, rel=0.01)
    assert distance_m(*a, *east) == pytest.approx(CELL, rel=0.01)


def test_points_150_m_apart_get_different_public_coordinates():
    lat, lon = PRACA_DR_CHAVES
    other = (lat + 150 / 111_320.0, lon)
    assert snap(lat, lon) != snap(*other)


@pytest.mark.parametrize(
    "lat, lon",
    [(-16.7207, -43.8660), (0.00001, -0.00001), (-0.00001, 0.00001), (40.4168, -3.7038)],
)
def test_works_across_hemispheres_and_the_equator(lat, lon):
    s_lat, s_lon = snap(lat, lon)
    lat_step, lon_step = grid_steps(CELL, REF_LAT)
    assert abs(s_lat - lat) <= lat_step / 2 + 1e-6
    assert abs(s_lon - lon) <= lon_step / 2 + 1e-6


def test_output_has_at_most_six_decimals():
    s_lat, s_lon = snap(*PRACA_DR_CHAVES)
    assert round(s_lat, 6) == s_lat and round(s_lon, 6) == s_lon


@pytest.mark.parametrize("cell, ref", [(0, REF_LAT), (-5, REF_LAT), (100, 89.9)])
def test_rejects_invalid_parameters(cell, ref):
    with pytest.raises(ValueError):
        grid_steps(cell, ref)


def test_bbox_parsing_and_membership():
    box = parse_bbox("-43.9,-16.8,-43.8,-16.7")
    assert box == (-43.9, -16.8, -43.8, -16.7)
    assert in_bbox(-16.72, -43.86, box)
    assert not in_bbox(-16.65, -43.86, box)
    assert parse_bbox(None) is None
    with pytest.raises(ValueError):
        parse_bbox("-43.8,-16.7,-43.9,-16.8")  # min > max
    with pytest.raises(ValueError):
        parse_bbox("1,2,3")
