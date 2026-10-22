"""Risk formula (occurrence_risk view) and chronic point detection, against PostGIS.

risk = type_weight × days_open × recurrence_factor × proximity_factor,
capped at unconfirmed_risk_cap until another resident confirms.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select, update

from app.models import (
    OccurrenceConfirmation,
    OccurrenceStatus,
    RiskSetting,
    SensitivePoint,
)
from app.services.occurrences import make_point
from app.services.risk import detect_chronic, risk_row
from tests.conftest import MC, make_occurrence, make_resident, offset_m

pytestmark = pytest.mark.db

S = OccurrenceStatus


def confirm(db, occurrence, *users):
    for user in users:
        db.add(OccurrenceConfirmation(occurrence_id=occurrence.id, user_id=user.id))
    db.flush()


def risk(db, occurrence):
    return risk_row(db, occurrence.id)


@pytest.fixture
def neighbour(db, settings):
    return make_resident(db, settings, "Vizinho")


# --- the formula --------------------------------------------------------------------------


def test_weight_times_days_when_nothing_else_applies(db, neighbour):
    occ = make_occurrence(db, "standing_water", days_ago=4)  # weight 5
    confirm(db, occ, neighbour)
    row = risk(db, occ)
    assert row.type_weight == 5 and row.days_open == 4
    assert row.recurrence_factor == 1 and row.proximity_factor == 1
    assert row.risk == Decimal("20.00")


def test_days_open_has_a_minimum_of_one(db, neighbour):
    occ = make_occurrence(db, "standing_water", days_ago=0)
    confirm(db, occ, neighbour)
    assert risk(db, occ).days_open == 1
    assert risk(db, occ).risk == Decimal("5.00")


def test_type_weight_orders_water_above_rubble(db, neighbour):
    water = make_occurrence(db, "standing_water", days_ago=2)
    rubble = make_occurrence(db, "trash_rubble", point=offset_m(*MC, north_m=500), days_ago=2)
    confirm(db, water, neighbour)
    confirm(db, rubble, neighbour)
    assert risk(db, water).risk > risk(db, rubble).risk


def test_recurrence_counts_only_resolved_occurrences_within_30_m(db, neighbour):
    occ = make_occurrence(db, "standing_water")
    make_occurrence(db, point=offset_m(*MC, north_m=10), status=S.CONFIRMED, days_ago=90)
    make_occurrence(db, point=offset_m(*MC, east_m=-25), status=S.RESOLVED_BY_AGENT, days_ago=60)
    # not counted: too far, contested, still open
    make_occurrence(db, point=offset_m(*MC, north_m=45), status=S.CONFIRMED, days_ago=30)
    make_occurrence(db, point=offset_m(*MC, east_m=8), status=S.CONTESTED, days_ago=20)
    make_occurrence(db, point=offset_m(*MC, east_m=5), status=S.OPEN, days_ago=10)
    confirm(db, occ, neighbour)

    row = risk(db, occ)
    assert row.recurrence_count == 2
    assert row.recurrence_factor == Decimal("2.0")  # 1 + 0.5 × 2
    assert row.risk == Decimal("10.00")  # 5 × 1 × 2 × 1


def test_sensitive_point_within_200_m_multiplies_by_1_5(db, neighbour):
    occ = make_occurrence(db, "standing_water", days_ago=2)
    confirm(db, occ, neighbour)
    lat, lon = offset_m(*MC, north_m=150)
    db.add(
        SensitivePoint(
            osm_type="node",
            osm_id=1,
            kind="school",
            name="Escola Teste",
            location=make_point(lat, lon),
        )
    )
    db.flush()
    row = risk(db, occ)
    assert row.proximity_factor == Decimal("1.5")
    assert row.nearest_sensitive_name == "Escola Teste"
    assert 140 < row.nearest_sensitive_distance_m < 160
    assert row.risk == Decimal("15.00")  # 5 × 2 × 1 × 1.5


def test_sensitive_point_beyond_200_m_is_ignored(db, neighbour):
    occ = make_occurrence(db, "standing_water", days_ago=2)
    confirm(db, occ, neighbour)
    lat, lon = offset_m(*MC, north_m=250)
    db.add(
        SensitivePoint(
            osm_type="node",
            osm_id=2,
            kind="hospital",
            name="Longe",
            location=make_point(lat, lon),
        )
    )
    db.flush()
    row = risk(db, occ)
    assert row.proximity_factor == 1 and row.nearest_sensitive_name is None


def test_all_factors_together(db, neighbour):
    occ = make_occurrence(db, "trash_rubble", days_ago=3)  # weight 3
    make_occurrence(db, point=offset_m(*MC, north_m=12), status=S.CONFIRMED, days_ago=40)
    lat, lon = offset_m(*MC, east_m=100)
    db.add(
        SensitivePoint(
            osm_type="way",
            osm_id=3,
            kind="kindergarten",
            name="Creche",
            location=make_point(lat, lon),
        )
    )
    confirm(db, occ, neighbour)
    # 3 × 3 × (1 + 0.5 × 1) × 1.5 = 20.25
    assert risk(db, occ).risk == Decimal("20.25")


# --- false-report mitigation ------------------------------------------------------------


def test_unconfirmed_risk_is_capped_until_another_resident_confirms(db, neighbour):
    occ = make_occurrence(db, "standing_water", days_ago=10)  # raw 50
    row = risk(db, occ)
    assert row.raw_risk == Decimal("50.00")
    assert row.risk == Decimal("15.00") and row.capped is True

    confirm(db, occ, neighbour)
    row = risk(db, occ)
    assert row.risk == Decimal("50.00") and row.capped is False
    assert row.confirmations == 1


def test_low_risk_below_the_cap_is_not_affected(db):
    occ = make_occurrence(db, "dead_animal", days_ago=2)  # 1 × 2 = 2
    row = risk(db, occ)
    assert row.risk == Decimal("2.00") and row.capped is False


# --- configurable coefficients ----------------------------------------------------------


def test_coefficients_come_from_the_database(db, neighbour):
    occ = make_occurrence(db, "standing_water")
    make_occurrence(db, point=offset_m(*MC, north_m=10), status=S.CONFIRMED, days_ago=30)
    make_occurrence(db, point=offset_m(*MC, north_m=-10), status=S.CONFIRMED, days_ago=30)
    confirm(db, occ, neighbour)
    assert risk(db, occ).recurrence_factor == Decimal("2.0")

    db.execute(update(RiskSetting).where(RiskSetting.key == "recurrence_increment").values(value=1))
    db.execute(update(RiskSetting).where(RiskSetting.key == "unconfirmed_risk_cap").values(value=2))
    row = risk(db, occ)
    assert row.recurrence_factor == Decimal("3")  # 1 + 1 × 2
    assert row.risk == Decimal("15.00")  # confirmed, so the (now tiny) cap does not apply


def test_type_weight_is_configurable(db, neighbour):
    from app.models import OccurrenceType

    occ = make_occurrence(db, "dead_animal", days_ago=2)
    confirm(db, occ, neighbour)
    db.execute(update(OccurrenceType).where(OccurrenceType.code == "dead_animal").values(weight=4))
    assert risk(db, occ).risk == Decimal("8.00")


# --- chronic points ---------------------------------------------------------------------


def test_three_recurrences_recommend_notifying_the_owner(db):
    occ = make_occurrence(db)
    for north in (5, -5, 15):
        make_occurrence(db, point=offset_m(*MC, north_m=north), status=S.CONFIRMED, days_ago=60)
    assert risk(db, occ).recommendation == "notificar_proprietario"


def test_two_recurrences_still_recommend_a_new_visit(db):
    occ = make_occurrence(db)
    for north in (5, -5):
        make_occurrence(db, point=offset_m(*MC, north_m=north), status=S.CONFIRMED, days_ago=60)
    assert risk(db, occ).recommendation == "nova_visita"


@pytest.mark.parametrize(
    "other_status, distance_m, expected",
    [
        (S.CONFIRMED, 20, True),
        (S.RESOLVED_BY_AGENT, 29, True),
        (S.CONFIRMED, 40, False),  # beyond 30 m
        (S.OPEN, 5, False),  # a nearby open report is a duplicate, not a recurrence
        (S.CONTESTED, 5, False),  # the resident said it was not solved
    ],
)
def test_chronic_detection(db, other_status, distance_m, expected):
    make_occurrence(db, point=offset_m(*MC, east_m=distance_m), status=other_status, days_ago=30)
    new = make_occurrence(db)
    assert detect_chronic(db, new) is expected


def test_new_report_through_the_api_is_flagged_chronic(client, db, settings):
    from app.models import Occurrence, OccurrenceType
    from tests.conftest import jpeg_with_exif

    make_occurrence(db, point=offset_m(*MC, north_m=15), status=S.CONFIRMED, days_ago=30)
    type_id = db.scalar(select(OccurrenceType.id).where(OccurrenceType.code == "standing_water"))
    response = client.post(
        "/api/occurrences",
        data={"type_id": str(type_id), "latitude": str(MC[0]), "longitude": str(MC[1])},
        files=[("photos", ("f.jpg", jpeg_with_exif(), "image/jpeg"))],
    )
    assert response.status_code == 201, response.text
    assert db.get(Occurrence, response.json()["id"]).is_chronic is True
