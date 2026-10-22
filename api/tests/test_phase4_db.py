"""Phase 4 against PostGIS: offline idempotency, messaging, area alerts, scope and route."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import (
    AreaAlert,
    Notification,
    NotificationStatus,
    Occurrence,
    OccurrenceStatus,
    OccurrenceType,
    SensitivePoint,
    UserRole,
)
from app.services import messaging, notifications
from app.services.occurrences import make_point
from app.services.sectors import SectorData, import_sectors
from tests.conftest import MC, auth_header, jpeg_with_exif, make_occurrence, offset_m

pytestmark = pytest.mark.db

S = OccurrenceStatus


@pytest.fixture(autouse=True)
def no_background_delivery(monkeypatch):
    """Background tasks open their own session on the dev database: never in tests."""
    monkeypatch.setattr(notifications, "deliver_by_id", lambda _id: None)


@pytest.fixture
def messaging_on(settings, monkeypatch):
    monkeypatch.setattr(settings, "notifications_enabled", True)
    monkeypatch.setattr(settings, "messaging_provider", "email")
    monkeypatch.setattr(settings, "messaging_chat_id", "grupo-teste")
    return settings


def type_id(db, code="standing_water"):
    return db.scalar(select(OccurrenceType.id).where(OccurrenceType.code == code))


def post(client, db, point=MC, code="standing_water", headers=None, **form):
    data = {
        "type_id": str(type_id(db, code)),
        "latitude": str(point[0]),
        "longitude": str(point[1]),
        **form,
    }
    files = [("photos", ("f.jpg", jpeg_with_exif(), "image/jpeg"))]
    return client.post("/api/occurrences", data=data, files=files, headers=headers or {})


# --- offline submissions ----------------------------------------------------------------

CLIENT_ID = "3f6c1d2e-9a7b-4c5d-8e9f-0123456789ab"


def test_resending_an_offline_report_does_not_duplicate_it(client, db, settings):
    first = post(client, db, client_submission_id=CLIENT_ID)
    assert first.status_code == 201
    again = post(client, db, client_submission_id=CLIENT_ID)
    assert again.status_code == 201
    a, b = first.json(), again.json()
    assert b["protocol"] == a["protocol"] and b["replayed"] is True
    assert db.scalar(select(Occurrence.id).where(Occurrence.protocol == a["protocol"])) == a["id"]
    assert len(db.scalars(select(Occurrence.id)).all()) == 1

    # The rotated token works; the lost one no longer does.
    protocol = a["protocol"]
    new = client.get(f"/api/tracking/{protocol}", headers={"X-Tracking-Token": b["tracking_token"]})
    old = client.get(f"/api/tracking/{protocol}", headers={"X-Tracking-Token": a["tracking_token"]})
    assert new.json()["is_owner"] is True and old.json()["is_owner"] is False


def test_offline_report_keeps_when_it_was_observed(client, db, settings):
    seen = datetime.now(UTC) - timedelta(hours=30)
    body = post(client, db, client_submission_id=CLIENT_ID, observed_at=seen.isoformat()).json()
    stored = db.get(Occurrence, body["id"]).observed_at
    assert abs((stored - seen).total_seconds()) < 1


@pytest.mark.parametrize(
    "delta, message", [(timedelta(days=8), "mais de 7 dias"), (timedelta(days=-1), "no futuro")]
)
def test_stale_or_future_offline_reports_are_refused(client, db, settings, delta, message):
    when = (datetime.now(UTC) - delta).isoformat()
    response = post(client, db, observed_at=when)
    assert response.status_code == 422 and message in response.json()["detail"]


# --- messaging group --------------------------------------------------------------------


def test_critical_report_goes_to_the_group_immediately(client, db, messaging_on):
    lat, lon = offset_m(*MC, north_m=120)
    db.add(
        SensitivePoint(
            osm_type="node",
            osm_id=1,
            kind="school",
            name="Escola Teste",
            location=make_point(lat, lon),
        )
    )
    db.commit()
    body = post(client, db).json()  # água parada (5) × 1,5 near a school = 7,5
    message = db.scalar(
        select(Notification).where(
            Notification.occurrence_id == body["id"], Notification.channel == "mensagem"
        )
    )
    assert message.kind == "nova_ocorrencia_urgente" and message.recipient == "grupo-teste"
    assert "Escola Teste" in message.body and body["protocol"] in message.body
    assert db.get(Occurrence, body["id"]).messaged_at is not None


def test_ordinary_report_waits_for_the_daily_digest(client, db, messaging_on):
    first = post(client, db, code="dead_animal").json()
    second = post(client, db, point=offset_m(*MC, north_m=800), code="trash_rubble").json()
    assert not db.scalars(select(Notification).where(Notification.channel == "mensagem")).all()

    digest = messaging.queue_daily_digest(db, messaging_on)
    db.commit()
    assert digest.kind == "resumo_diario" and digest.occurrence_id is None
    assert first["protocol"] in digest.body and second["protocol"] in digest.body
    assert "2 nova(s)" in digest.body
    assert messaging.queue_daily_digest(db, messaging_on) is None  # nothing left


def test_group_message_delivery_and_failure_keep_the_outbox_consistent(
    client, db, messaging_on, monkeypatch
):
    post(client, db, code="dead_animal")
    digest = messaging.queue_daily_digest(db, messaging_on)
    db.commit()

    monkeypatch.setattr(
        messaging, "send_email", lambda msg, s: (_ for _ in ()).throw(OSError("off"))
    )
    assert notifications.deliver(db, digest) is False
    assert digest.status == NotificationStatus.FAILED and digest.body  # kept for the retry

    sent = []
    monkeypatch.setattr(messaging, "send_email", lambda msg, s: sent.append(msg))
    monkeypatch.setattr(notifications, "_send", lambda msg, s: sent.append(msg))
    # The retry resends the failed digest and the still-pending e-mail to the prefecture.
    assert notifications.retry_pending(db) == (2, 0)
    assert digest.status == NotificationStatus.SENT
    subjects = [m["Subject"] for m in sent]
    assert any(s.startswith("[Grupo grupo-teste] 📋 Resumo") for s in subjects)


def test_messaging_off_queues_nothing(client, db, settings, monkeypatch):
    monkeypatch.setattr(settings, "notifications_enabled", True)
    monkeypatch.setattr(settings, "messaging_provider", "none")
    post(client, db)
    assert messaging.queue_daily_digest(db, settings) is None
    assert not db.scalars(select(Notification).where(Notification.channel == "mensagem")).all()


# --- accumulation alerts ----------------------------------------------------------------


def test_third_report_in_the_area_alerts_the_managers(client, db, users, messaging_on):
    make_occurrence(db, point=offset_m(*MC, north_m=40), days_ago=2)
    make_occurrence(db, point=offset_m(*MC, east_m=-60), days_ago=1)
    db.commit()
    body = post(client, db).json()

    alert = db.scalar(select(AreaAlert))
    assert alert.occurrence_count == 3 and body["id"] in alert.occurrence_ids
    assert alert.radius_m == 150
    queued = db.scalars(select(Notification).where(Notification.area_alert_id == alert.id)).all()
    emails = {n.recipient for n in queued if n.channel == "email"}
    assert emails == {users[UserRole.MANAGER].email}
    assert any(n.channel == "mensagem" and "Alerta de acúmulo" in n.body for n in queued)

    msg = notifications.build_message(next(n for n in queued if n.channel == "email"), messaging_on)
    assert "3 registros de Água parada" in msg["Subject"]

    # A fourth report at the same spot does not alert again within the window.
    post(client, db, point=offset_m(*MC, north_m=10))
    assert len(db.scalars(select(AreaAlert)).all()) == 1


@pytest.mark.parametrize(
    "setup",
    [
        "other_type",  # same place, different type
        "too_old",  # outside the 7-day window
        "resolved",  # not active any more
        "too_far",  # beyond 150 m
    ],
)
def test_no_alert_without_a_real_cluster(client, db, settings, setup):
    kwargs = {
        "other_type": {"type_code": "trash_rubble"},
        "too_old": {"days_ago": 9},
        "resolved": {"status": S.CONFIRMED},
        "too_far": {"point": offset_m(*MC, north_m=400)},
    }[setup]
    for north in (20, -20):
        params = {"point": offset_m(*MC, north_m=north), **kwargs}
        if setup == "too_far":
            params["point"] = offset_m(*kwargs["point"], north_m=north)
        make_occurrence(db, **params)
    db.commit()
    post(client, db)
    assert db.scalar(select(AreaAlert)) is None


def test_alerts_endpoint_is_staff_only(client, db, users, settings):
    for north in (20, -20, 0):
        make_occurrence(db, point=offset_m(*MC, north_m=north))
    db.commit()
    post(client, db, point=offset_m(*MC, east_m=15))
    assert client.get("/api/alerts").status_code == 401
    agent = auth_header(client, users[UserRole.AGENT].email)
    alerts = client.get("/api/alerts", headers=agent).json()
    assert len(alerts) == 1 and alerts[0]["type_code"] == "standing_water"
    assert alerts[0]["occurrence_count"] == 4


# --- prevention -------------------------------------------------------------------------


def test_every_type_has_prevention_advice(client, db, settings):
    types = client.get("/api/occurrence-types").json()
    assert len(types) == 9  # the eight original types + "Outro risco"
    assert all(len(t["prevention_tips"]) > 40 for t in types)
    water = next(t for t in types if t["code"] == "standing_water")
    assert "10 minutos" in water["prevention_tips"]


# --- agent scope ------------------------------------------------------------------------


def square(center, half_m=300):
    s_lat, w_lon = offset_m(*center, north_m=-half_m, east_m=-half_m)
    n_lat, e_lon = offset_m(*center, north_m=half_m, east_m=half_m)
    return {
        "type": "Polygon",
        "coordinates": [
            [[w_lon, s_lat], [e_lon, s_lat], [e_lon, n_lat], [w_lon, n_lat], [w_lon, s_lat]]
        ],
    }


@pytest.fixture
def two_sectors(db):
    east = offset_m(*MC, east_m=2000)
    import_sectors(
        db,
        [
            SectorData("A", "Setor A", 1000, square(MC)),
            SectorData("B", "Setor B", 1000, square(east)),
        ],
        "teste",
    )
    db.commit()
    from app.models import Sector

    return {s.code: s for s in db.scalars(select(Sector))}, east


def queue_ids(client, headers):
    return {i["id"] for i in client.get("/api/queue", headers=headers).json()["items"]}


def test_manager_scopes_an_agent_by_sector_and_type(client, db, users, settings, two_sectors):
    sectors, east = two_sectors
    in_a_water = make_occurrence(db, point=MC)
    in_a_rubble = make_occurrence(db, "trash_rubble", point=offset_m(*MC, north_m=50))
    in_b_water = make_occurrence(db, point=east)
    db.commit()
    agent_user = users[UserRole.AGENT]
    agent = auth_header(client, agent_user.email)
    manager = auth_header(client, users[UserRole.MANAGER].email)

    assert queue_ids(client, agent) >= {in_a_water.id, in_a_rubble.id, in_b_water.id}

    url = f"/api/staff/{agent_user.id}/scope"
    payload = {"sector_ids": [sectors["A"].id], "type_ids": [type_id(db)]}
    assert client.put(url, json=payload, headers=agent).status_code == 403
    member = client.put(url, json=payload, headers=manager).json()
    assert member["sector_ids"] == [sectors["A"].id] and member["type_ids"] == [type_id(db)]

    assert queue_ids(client, agent) == {in_a_water.id}
    assert queue_ids(client, manager) >= {in_a_water.id, in_a_rubble.id, in_b_water.id}
    staff_map = client.get("/api/occurrences", headers=agent).json()["items"]
    assert {i["id"] for i in staff_map} == {in_a_water.id}
    assert client.get("/api/me/scope", headers=agent).json()["sector_ids"] == [sectors["A"].id]

    # Clearing the scope gives the whole municipality back.
    client.put(url, json={"sector_ids": [], "type_ids": []}, headers=manager)
    assert queue_ids(client, agent) >= {in_a_water.id, in_a_rubble.id, in_b_water.id}


def test_scope_rejects_unknown_ids_and_non_agents(client, db, users, settings):
    manager = auth_header(client, users[UserRole.MANAGER].email)
    agent_id = users[UserRole.AGENT].id
    bad = client.put(f"/api/staff/{agent_id}/scope", json={"sector_ids": [999999]}, headers=manager)
    assert bad.status_code == 422
    manager_id = users[UserRole.MANAGER].id
    assert client.put(f"/api/staff/{manager_id}/scope", json={}, headers=manager).status_code == 404
    staff = client.get("/api/staff", headers=manager).json()
    assert {s["role"] for s in staff} == {"agente", "gestor"}


# --- route ------------------------------------------------------------------------------


def test_route_orders_by_distance_and_honours_removals(client, db, users, settings):
    far = make_occurrence(db, point=offset_m(*MC, north_m=900), days_ago=3)
    near = make_occurrence(db, point=offset_m(*MC, north_m=100), days_ago=3)
    mid = make_occurrence(db, point=offset_m(*MC, north_m=500), days_ago=3)
    db.commit()
    agent = auth_header(client, users[UserRole.AGENT].email)

    route = client.get("/api/route", params={"lat": MC[0], "lon": MC[1]}, headers=agent).json()
    assert [s["item"]["id"] for s in route["stops"]] == [near.id, mid.id, far.id]
    assert route["stops"][0]["leg_m"] == pytest.approx(100, abs=2)
    assert route["total_m"] == pytest.approx(900, abs=5) and route["straight_line"] is True

    without_mid = client.get(
        "/api/route",
        params={"lat": MC[0], "lon": MC[1], "exclude": [mid.id]},
        headers=agent,
    ).json()
    assert [s["item"]["id"] for s in without_mid["stops"]] == [near.id, far.id]


def test_route_takes_the_riskiest_stops_first(client, db, users, settings):
    # With room for one stop, the higher-risk (older) one wins even if it is farther.
    risky_far = make_occurrence(db, point=offset_m(*MC, north_m=900), days_ago=2)
    mild_near = make_occurrence(db, "dead_animal", point=offset_m(*MC, north_m=50), days_ago=1)
    db.commit()
    agent = auth_header(client, users[UserRole.AGENT].email)
    route = client.get(
        "/api/route", params={"lat": MC[0], "lon": MC[1], "max_stops": 1}, headers=agent
    ).json()
    assert [s["item"]["id"] for s in route["stops"]] == [risky_far.id]
    assert mild_near.id != risky_far.id


def test_route_is_staff_only(client, db, users, settings):
    resident = auth_header(client, users[UserRole.RESIDENT].email)
    params = {"lat": MC[0], "lon": MC[1]}
    assert client.get("/api/route", params=params, headers=resident).status_code == 403
