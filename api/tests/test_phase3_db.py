"""Phase 3 against PostGIS: silence counter, ombudsman PDF, sectors, LIRAa and indicators."""

import io
from datetime import UTC, datetime, timedelta

import pytest
from pypdf import PdfReader

from app.models import OccurrenceStatus, UserRole
from app.services.sectors import SectorData, import_sectors
from tests.conftest import MC, auth_header, make_occurrence, offset_m

pytestmark = pytest.mark.db

S = OccurrenceStatus


def square(center, half_m=400):
    s_lat, w_lon = offset_m(*center, north_m=-half_m, east_m=-half_m)
    n_lat, e_lon = offset_m(*center, north_m=half_m, east_m=half_m)
    ring = [[w_lon, s_lat], [e_lon, s_lat], [e_lon, n_lat], [w_lon, n_lat], [w_lon, s_lat]]
    return {"type": "Polygon", "coordinates": [ring]}


@pytest.fixture
def sectors(db):
    """Three adjacent 800 m squares: A (small population), B (large), C."""
    centers = {
        "A": MC,
        "B": offset_m(*MC, east_m=1000),
        "C": offset_m(*MC, east_m=2000),
    }
    population = {"A": 1_000, "B": 10_000, "C": 5_000}
    import_sectors(
        db,
        [
            SectorData(code, f"Setor {code}", population[code], square(c))
            for code, c in centers.items()
        ],
        "teste",
    )
    # commit (inside the test savepoint) so an endpoint rollback does not drop them
    db.commit()
    return centers


def silent_for(db, days, **kwargs):
    occ = make_occurrence(db, days_ago=days, **kwargs)
    occ.notified_at = datetime.now(UTC) - timedelta(days=days, hours=1)
    db.flush()
    return occ


# --- the public silence counter -----------------------------------------------------------


def test_public_map_shows_days_without_response_and_overdue(client, db, settings):
    late = silent_for(db, 20)
    recent = silent_for(db, 3, point=offset_m(*MC, north_m=800))
    answered = silent_for(db, 30, point=offset_m(*MC, north_m=-800))
    answered.first_response_at = datetime.now(UTC) - timedelta(days=25)
    answered.status = S.IN_PROGRESS
    db.flush()

    items = {i["protocol"]: i for i in client.get("/api/occurrences/public").json()["items"]}
    assert items[late.protocol]["days_without_response"] == 20
    assert items[late.protocol]["response_overdue"] is True
    assert items[recent.protocol]["days_without_response"] == 3
    assert items[recent.protocol]["response_overdue"] is False
    assert items[answered.protocol]["days_without_response"] is None


# --- ombudsman PDF ------------------------------------------------------------------------


def owned(db, days, users):
    return silent_for(db, days, author=users[UserRole.RESIDENT])


def test_pdf_is_only_for_the_reporter(client, db, settings, users):
    occ = owned(db, 20, users)
    url = f"/api/tracking/{occ.protocol}/ouvidoria.pdf"
    assert client.get(url).status_code == 404
    agent = auth_header(client, users[UserRole.AGENT].email)
    assert client.get(url, headers=agent).status_code == 404


def test_pdf_waits_for_the_deadline(client, db, settings, users):
    occ = owned(db, 5, users)
    owner = auth_header(client, users[UserRole.RESIDENT].email)
    response = client.get(f"/api/tracking/{occ.protocol}/ouvidoria.pdf", headers=owner)
    assert response.status_code == 409 and "faltam 10" in response.json()["detail"]
    tracking = client.get(f"/api/tracking/{occ.protocol}", headers=owner).json()
    assert tracking["days_left"] == 10 and tracking["can_request_ouvidoria"] is False


def test_overdue_owner_gets_a_pdf_with_protocol_coordinates_and_history(
    client, db, settings, users
):
    occ = owned(db, 18, users)
    owner = auth_header(client, users[UserRole.RESIDENT].email)
    tracking = client.get(f"/api/tracking/{occ.protocol}", headers=owner).json()
    assert tracking["response_overdue"] is True and tracking["can_request_ouvidoria"] is True

    response = client.get(f"/api/tracking/{occ.protocol}/ouvidoria.pdf", headers=owner)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert f"ouvidoria-{occ.protocol}.pdf" in response.headers["content-disposition"]
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(response.content)).pages)
    assert occ.protocol in text
    assert "18 dias" in text
    assert f"{MC[0]:.6f}" in text and f"{MC[1]:.6f}" in text
    assert "Ouvidoria" in text and "Montes Claros" in text


def test_no_pdf_once_the_prefecture_responded(client, db, settings, users):
    occ = owned(db, 20, users)
    occ.first_response_at = datetime.now(UTC) - timedelta(days=2)
    db.flush()
    owner = auth_header(client, users[UserRole.RESIDENT].email)
    response = client.get(f"/api/tracking/{occ.protocol}/ouvidoria.pdf", headers=owner)
    assert response.status_code == 409 and "já respondeu" in response.json()["detail"]


# --- sectors, normalised by population ---------------------------------------------------


def test_sector_index_is_normalised_by_population(client, db, settings, users, sectors):
    # A: 1 occurrence, 1,000 inhabitants. B: 3 occurrences, 10,000 inhabitants.
    make_occurrence(db, "standing_water", point=sectors["A"], days_ago=2)
    for north in (-100, 0, 100):
        make_occurrence(
            db, "standing_water", point=offset_m(*sectors["B"], north_m=north), days_ago=2
        )
    make_occurrence(db, point=sectors["C"], status=S.CONFIRMED)  # resolved: not active

    agent = auth_header(client, users[UserRole.AGENT].email)
    features = client.get("/api/sectors/current", headers=agent).json()["features"]
    by_code = {f["properties"]["code"]: f["properties"] for f in features}
    assert by_code["A"]["active_count"] == 1 and by_code["B"]["active_count"] == 3
    assert by_code["C"]["active_count"] == 0
    # More reports in B, but less risk per inhabitant than A.
    assert by_code["A"]["risk_per_1000"] > by_code["B"]["risk_per_1000"]
    assert by_code["A"]["active_per_1000"] == 1.0 and by_code["B"]["active_per_1000"] == 0.3
    assert features[0]["geometry"]["type"] == "MultiPolygon"


def test_sector_endpoints_are_staff_only(client, db, settings, users):
    resident = auth_header(client, users[UserRole.RESIDENT].email)
    assert client.get("/api/sectors/current", headers=resident).status_code == 403
    assert client.get("/api/indicators").status_code == 401


# --- LIRAa import and comparison ---------------------------------------------------------


def upload(client, headers, text):
    return client.post(
        "/api/liraa/import",
        files={"file": ("liraa.csv", text.encode("utf-8"), "text/csv")},
        headers=headers,
    )


def test_only_managers_import_and_bad_files_change_nothing(client, db, settings, users, sectors):
    good = "setor;periodo;data;iip\nA;2026-x;01/10/2026;3,0\n"
    agent = auth_header(client, users[UserRole.AGENT].email)
    assert upload(client, agent, good).status_code == 403

    manager = auth_header(client, users[UserRole.MANAGER].email)
    bad = "setor;periodo;data;iip\nA;2026-x;01/10/2026;3,0\nZZ;2026-x;01/10/2026;1\n"
    response = upload(client, manager, bad)
    assert response.status_code == 422
    assert "ZZ" in response.json()["detail"]["errors"][0]
    assert client.get("/api/liraa/periods", headers=manager).json() == []

    assert upload(client, manager, good).json() == {"inserted": 1, "updated": 0, "lines": 1}
    # same sector and period again: update, not duplicate
    again = "setor;periodo;data;iip\nA;2026-x;01/10/2026;3,5\n"
    assert upload(client, manager, again).json()["updated"] == 1


def test_comparison_counts_only_the_window_and_measures_agreement(
    client, db, settings, users, sectors
):
    survey = (datetime.now(UTC) - timedelta(days=5)).date()
    manager = auth_header(client, users[UserRole.MANAGER].email)
    csv_text = "setor;periodo;data;iip\n" + "".join(
        f"{code};ciclo-1;{survey:%d/%m/%Y};{iip}\n"
        for code, iip in (("A", "5,0"), ("B", "1,0"), ("C", "0,5"))
    )
    assert upload(client, manager, csv_text).status_code == 200

    # Inside the 60-day window before the survey: A gets the most per inhabitant.
    make_occurrence(db, "standing_water", point=sectors["A"], days_ago=20)  # 5 / 1,000
    make_occurrence(db, "standing_water", point=sectors["B"], days_ago=20)  # 5 / 10,000
    # Outside the window (too old, or after the survey): ignored.
    make_occurrence(db, "standing_water", point=sectors["C"], days_ago=90)
    make_occurrence(db, "standing_water", point=sectors["C"], days_ago=1)

    body = client.get("/api/liraa/comparison", headers=manager).json()
    meta = body["meta"]
    assert meta["period"] == "ciclo-1" and meta["window_days"] == 60
    props = {f["properties"]["code"]: f["properties"] for f in body["features"]}
    assert props["A"]["community_index"] == 5.0
    assert props["B"]["community_index"] == 0.5
    assert props["C"]["community_index"] == 0.0 and props["C"]["occurrences"] == 0
    assert props["A"]["liraa_class"] == "risco" and props["C"]["liraa_class"] == "satisfatorio"
    assert props["A"]["community_rank"] == 1 and props["A"]["liraa_rank"] == 1
    assert meta["paired_sectors"] == 3
    assert meta["spearman_rho"] == pytest.approx(1.0)


# --- management panel ---------------------------------------------------------------------


def test_indicators_overview_and_csv(client, db, settings, users, sectors):
    silent_for(db, 20, point=sectors["A"])
    answered = silent_for(db, 10, point=sectors["B"])
    answered.first_response_at = answered.notified_at + timedelta(days=2)
    answered.status = S.IN_PROGRESS
    db.flush()
    agent = auth_header(client, users[UserRole.AGENT].email)

    data = client.get("/api/indicators", headers=agent).json()
    assert data["registered"] == 2
    assert data["no_response"] == {"waiting": 1, "overdue": 1, "deadline_days": 15}
    assert data["time_to_first_response"]["median_days"] == 2.0
    assert {t["code"] for t in data["by_type"]} >= {"standing_water", "dead_animal"}
    assert data["sectors"][0]["code"] == "A"  # highest risk per 1,000

    narrow = client.get(
        "/api/indicators",
        params={"date_from": (datetime.now(UTC) - timedelta(days=12)).date().isoformat()},
        headers=agent,
    ).json()
    assert narrow["registered"] == 1

    csv_response = client.get("/api/indicators/sectors.csv", headers=agent)
    assert csv_response.headers["content-type"].startswith("text/csv")
    lines = csv_response.content.decode("utf-8-sig").splitlines()
    assert lines[0].startswith("codigo;setor;populacao")
    assert any(line.startswith("A;Setor A;1000;1;") for line in lines)
