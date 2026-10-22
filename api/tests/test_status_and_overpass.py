"""Pure tests: status flow and Overpass parsing (no database, no network)."""

import pytest

from app.domain.status import Actor, TransitionError, check_transition
from app.models import OccurrenceStatus as S
from app.services.sensitive_points import build_query, parse_overpass

# --- status flow --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "current, target",
    [
        (S.OPEN, S.IN_PROGRESS),
        (S.CONTESTED, S.IN_PROGRESS),
        (S.OPEN, S.RESOLVED_BY_AGENT),
        (S.IN_PROGRESS, S.RESOLVED_BY_AGENT),
        (S.CONTESTED, S.RESOLVED_BY_AGENT),
    ],
)
def test_staff_moves_the_queue(current, target):
    check_transition(current, target, Actor.STAFF)


@pytest.mark.parametrize("target", [S.CONFIRMED, S.CONTESTED])
def test_only_the_reporter_answers_after_closure(target):
    check_transition(S.RESOLVED_BY_AGENT, target, Actor.REPORTER)
    with pytest.raises(TransitionError, match="quem registrou"):
        check_transition(S.RESOLVED_BY_AGENT, target, Actor.STAFF)


@pytest.mark.parametrize(
    "current, target",
    [
        (S.OPEN, S.CONFIRMED),  # cannot confirm what the agent never closed
        (S.CONFIRMED, S.OPEN),  # confirmed is final
        (S.CONFIRMED, S.CONTESTED),  # the answer is given once
        (S.CONTESTED, S.CONFIRMED),
        (S.IN_PROGRESS, S.OPEN),
    ],
)
def test_rejects_transitions_outside_the_flow(current, target):
    for actor in Actor:
        with pytest.raises(TransitionError):
            check_transition(current, target, actor)


def test_reporter_cannot_close_or_take_the_occurrence():
    with pytest.raises(TransitionError, match="equipe de saúde"):
        check_transition(S.OPEN, S.RESOLVED_BY_AGENT, Actor.REPORTER)


# --- Overpass -----------------------------------------------------------------------------

PAYLOAD = {
    "elements": [
        {
            "type": "node",
            "id": 1,
            "lat": -16.72,
            "lon": -43.86,
            "tags": {"amenity": "school", "name": "Escola Estadual A"},
        },
        {
            "type": "way",
            "id": 2,
            "center": {"lat": -16.73, "lon": -43.87},
            "tags": {"amenity": "hospital", "name": "Hospital B"},
        },
        {"type": "node", "id": 3, "lat": -16.74, "lon": -43.88, "tags": {"healthcare": "centre"}},
        {
            "type": "relation",
            "id": 4,
            "center": {"lat": -16.75, "lon": -43.89},
            "tags": {"amenity": "kindergarten", "name": "  Creche C  "},
        },
        # ignored: not a sensitive amenity, way without center, duplicate of id 1
        {"type": "node", "id": 5, "lat": -16.7, "lon": -43.8, "tags": {"amenity": "bank"}},
        {"type": "way", "id": 6, "tags": {"amenity": "school"}},
        {"type": "node", "id": 1, "lat": -16.72, "lon": -43.86, "tags": {"amenity": "school"}},
    ]
}


def test_parses_nodes_and_way_or_relation_centres():
    points = {(p.osm_type, p.osm_id): p for p in parse_overpass(PAYLOAD)}
    assert set(points) == {("node", 1), ("way", 2), ("node", 3), ("relation", 4)}
    assert points[("way", 2)].lat == -16.73 and points[("way", 2)].kind == "hospital"
    assert points[("node", 3)].kind == "healthcare:centre"
    assert points[("node", 3)].name == "(sem nome)"
    assert points[("relation", 4)].name == "Creche C"


def test_parse_tolerates_empty_or_malformed_payloads():
    assert parse_overpass({}) == []
    assert parse_overpass({"elements": [{"type": "node"}]}) == []


def test_query_by_municipality_area_uses_the_overpass_area_id():
    query = build_query(osm_relation=314620)
    assert "area(3600314620)->.city;" in query
    assert 'nwr["amenity"="school"](area.city);' in query
    assert 'nwr["healthcare"](area.city);' in query


def test_query_needs_an_area_or_bbox():
    with pytest.raises(ValueError):
        build_query()


def test_query_covers_the_required_tags_inside_the_service_area():
    query = build_query((-44.2107, -17.1458, -43.6665, -16.0845))
    for amenity in ("school", "kindergarten", "hospital", "clinic", "doctors"):
        assert f'nwr["amenity"="{amenity}"]' in query
    assert 'nwr["healthcare"]' in query
    # Overpass expects (south, west, north, east)
    assert "(-17.1458,-44.2107,-16.0845,-43.6665)" in query
    assert "out center" in query
