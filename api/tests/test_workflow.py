"""Agent queue, closure with photo, the resident's answer, 'eu também vi', heat and stats."""

import pytest
from sqlalchemy import select

from app.models import (
    Notification,
    Occurrence,
    OccurrenceStatus,
    OccurrenceType,
    PhotoKind,
    UserRole,
)
from app.services import notifications
from app.services.privacy import obfuscate_coordinate
from tests.conftest import (
    MC,
    auth_header,
    jpeg_with_exif,
    make_occurrence,
    make_resident,
    offset_m,
)

pytestmark = pytest.mark.db

S = OccurrenceStatus


@pytest.fixture(autouse=True)
def no_background_email(monkeypatch):
    """Background tasks would open their own session; e-mail content is tested apart."""
    monkeypatch.setattr(notifications, "deliver_by_id", lambda _id: None)


def report(client, db, **form):
    type_id = db.scalar(select(OccurrenceType.id).where(OccurrenceType.code == "standing_water"))
    data = {"type_id": str(type_id), "latitude": str(MC[0]), "longitude": str(MC[1]), **form}
    files = [("photos", ("f.jpg", jpeg_with_exif(), "image/jpeg"))]
    response = client.post("/api/occurrences", data=data, files=files)
    assert response.status_code == 201, response.text
    return response.json()


def resolve(client, occurrence_id, headers, photos=1):
    files = [("photos", (f"r{i}.jpg", jpeg_with_exif(), "image/jpeg")) for i in range(photos)]
    return client.post(
        f"/api/occurrences/{occurrence_id}/resolve",
        data={"note": "Recipientes removidos."},
        files=files,
        headers=headers,
    )


@pytest.fixture
def agent(client, users):
    return auth_header(client, users[UserRole.AGENT].email)


# --- agent actions ------------------------------------------------------------------------


def test_only_staff_can_start_service(client, db, settings, users, agent):
    created = report(client, db)
    url = f"/api/occurrences/{created['id']}/start"
    assert client.post(url, json={}).status_code == 401
    resident = auth_header(client, users[UserRole.RESIDENT].email)
    assert client.post(url, json={}, headers=resident).status_code == 403

    body = client.post(url, json={"note": "A caminho"}, headers=agent).json()
    assert body["status"] == "em_atendimento"
    assert body["first_response_at"] is not None
    assert body["history"][-1]["to_status"] == "em_atendimento"
    # starting twice is not a valid transition
    assert client.post(url, json={}, headers=agent).status_code == 409


def test_closing_requires_a_photo(client, db, settings, agent):
    created = report(client, db)
    response = resolve(client, created["id"], agent, photos=0)
    assert response.status_code == 422
    assert db.get(Occurrence, created["id"]).status == S.OPEN


def test_closing_with_photo_awaits_the_resident(client, db, settings, agent):
    created = report(client, db)
    body = resolve(client, created["id"], agent).json()
    assert body["status"] == "resolvida_pelo_agente"
    kinds = [p["kind"] for p in body["photos"]]
    assert kinds == ["registro", "resolucao"]
    assert body["first_response_at"] is not None


def test_closure_emails_the_question_to_an_identified_visitor(
    client, db, settings, agent, monkeypatch
):
    monkeypatch.setattr(settings, "notifications_enabled", True)
    created = report(client, db, reporter_name="Ana", reporter_contact="ana@exemplo.test")
    resolve(client, created["id"], agent)

    sent = db.scalar(
        select(Notification).where(
            Notification.occurrence_id == created["id"],
            Notification.kind == "pedido_confirmacao",
        )
    )
    assert sent.recipient == "ana@exemplo.test"
    assert f"/acompanhar/{created['protocol']}#t=" in sent.link
    # The e-mailed token works like the original link.
    token = sent.link.split("#t=")[1]
    data = client.get(
        f"/api/tracking/{created['protocol']}", headers={"X-Tracking-Token": token}
    ).json()
    assert data["is_owner"] is True and data["can_answer"] is True

    msg = notifications.build_message(sent, settings)
    assert "foi resolvido" in msg["Subject"]
    assert sent.link in msg.get_content()


def test_closure_of_an_anonymous_report_sends_nothing(client, db, settings, agent, monkeypatch):
    monkeypatch.setattr(settings, "notifications_enabled", True)
    created = report(client, db, is_anonymous="true")
    resolve(client, created["id"], agent)
    kinds = db.scalars(
        select(Notification.kind).where(Notification.occurrence_id == created["id"])
    ).all()
    assert "pedido_confirmacao" not in kinds


# --- the resident's single answer ---------------------------------------------------------


def answer(client, created, resolved, token=None):
    headers = {"X-Tracking-Token": token or created["tracking_token"]}
    return client.post(
        f"/api/tracking/{created['protocol']}/feedback",
        json={"resolved": resolved},
        headers=headers,
    )


def test_yes_confirms_the_resolution(client, db, settings, agent):
    created = report(client, db)
    resolve(client, created["id"], agent)
    body = answer(client, created, True).json()
    assert body["status"] == "confirmada" and body["can_answer"] is False
    assert answer(client, created, False).status_code == 409  # answered once only


def test_no_contests_and_sends_it_back_to_the_queue(client, db, settings, agent):
    created = report(client, db)
    resolve(client, created["id"], agent)
    assert answer(client, created, False).json()["status"] == "contestada"

    queue = client.get("/api/queue", headers=agent).json()["items"]
    assert created["id"] in [i["id"] for i in queue]
    # the agent can take it again and close it again
    start = client.post(f"/api/occurrences/{created['id']}/start", json={}, headers=agent)
    assert start.json()["status"] == "em_atendimento"


def test_cannot_answer_before_the_agent_closes(client, db, settings):
    created = report(client, db)
    assert answer(client, created, True).status_code == 409


def test_strangers_cannot_answer(client, db, settings, agent):
    created = report(client, db)
    resolve(client, created["id"], agent)
    assert answer(client, created, True, token="token-errado").status_code == 404


def test_logged_in_author_answers_without_token(client, db, settings, users, agent):
    resident = auth_header(client, users[UserRole.RESIDENT].email)
    type_id = db.scalar(select(OccurrenceType.id).where(OccurrenceType.code == "standing_water"))
    created = client.post(
        "/api/occurrences",
        data={"type_id": str(type_id), "latitude": str(MC[0]), "longitude": str(MC[1])},
        files=[("photos", ("f.jpg", jpeg_with_exif(), "image/jpeg"))],
        headers=resident,
    ).json()
    resolve(client, created["id"], agent)
    response = client.post(
        f"/api/tracking/{created['protocol']}/feedback", json={"resolved": True}, headers=resident
    )
    assert response.json()["status"] == "confirmada"


# --- 'eu também vi' -----------------------------------------------------------------------


def test_confirmation_rules(client, db, settings, users):
    author = users[UserRole.RESIDENT]
    occ = make_occurrence(db, author=author)
    url = f"/api/tracking/{occ.protocol}/confirmations"

    assert client.post(url).status_code == 401  # needs an account
    own = client.post(url, headers=auth_header(client, author.email))
    assert own.status_code == 409 and "você mesmo" in own.json()["detail"]
    staff = client.post(url, headers=auth_header(client, users[UserRole.AGENT].email))
    assert staff.status_code == 409

    neighbour = make_resident(db, settings, "Vizinha")
    headers = auth_header(client, neighbour.email)
    assert client.post(url, headers=headers).json() == {"confirmations": 1}
    assert client.post(url, headers=headers).status_code == 409  # once per person

    public = client.get("/api/occurrences/public").json()["items"]
    assert [i["confirmations"] for i in public if i["protocol"] == occ.protocol] == [1]


def test_resolved_occurrences_cannot_be_confirmed(client, db, settings):
    occ = make_occurrence(db, status=S.CONFIRMED)
    neighbour = make_resident(db, settings, "Vizinho")
    response = client.post(
        f"/api/tracking/{occ.protocol}/confirmations", headers=auth_header(client, neighbour.email)
    )
    assert response.status_code == 409


# --- the queue ----------------------------------------------------------------------------


def test_queue_is_ordered_by_risk_not_by_date(client, db, settings, agent):
    neighbour = make_resident(db, settings, "Vizinho")
    old_low = make_occurrence(db, "dead_animal", point=offset_m(*MC, north_m=900), days_ago=9)
    new_high = make_occurrence(db, "standing_water", days_ago=4)
    from tests.test_risk import confirm

    confirm(db, new_high, neighbour)  # 5 × 4 = 20 > 1 × 9 = 9
    resolved = make_occurrence(db, point=offset_m(*MC, north_m=-900), status=S.CONFIRMED)

    items = client.get("/api/queue", headers=agent).json()["items"]
    ids = [i["id"] for i in items]
    assert ids.index(new_high.id) < ids.index(old_low.id)
    assert resolved.id not in ids
    top = items[0]
    assert top["risk"]["risk"] == 20 and top["risk"]["confirmations"] == 1
    assert top["latitude"] == pytest.approx(MC[0])  # exact for staff


def test_capped_reports_are_tie_broken_by_raw_risk(client, db, settings, agent):
    # Both stop at the cap (15); the older one must not win just for being older.
    mild = make_occurrence(db, "trash_rubble", point=offset_m(*MC, north_m=600), days_ago=10)
    severe = make_occurrence(db, "standing_water", days_ago=8)  # raw 5×8=40 vs mild 3×10=30
    items = client.get("/api/queue", headers=agent).json()["items"]
    by_id = {i["id"]: i for i in items}
    assert by_id[mild.id]["risk"]["risk"] == by_id[severe.id]["risk"]["risk"] == 15
    ids = [i["id"] for i in items]
    assert by_id[severe.id]["risk"]["raw_risk"] > by_id[mild.id]["risk"]["raw_risk"]
    assert ids.index(severe.id) < ids.index(mild.id)


def test_queue_by_distance_needs_and_uses_the_agent_position(client, db, settings, agent):
    near = make_occurrence(db, "dead_animal", point=offset_m(*MC, north_m=100))
    far = make_occurrence(db, "standing_water", point=offset_m(*MC, north_m=2000), days_ago=30)
    assert client.get("/api/queue?order=distance", headers=agent).status_code == 422
    items = client.get(
        "/api/queue", params={"order": "distance", "lat": MC[0], "lon": MC[1]}, headers=agent
    ).json()["items"]
    ids = [i["id"] for i in items]
    assert ids.index(near.id) < ids.index(far.id)
    assert items[0]["distance_m"] == pytest.approx(100, abs=2)


def test_queue_is_staff_only(client, db, settings, users):
    assert client.get("/api/queue").status_code == 401
    resident = auth_header(client, users[UserRole.RESIDENT].email)
    assert client.get("/api/queue", headers=resident).status_code == 403


def test_staff_detail_includes_the_risk_breakdown(client, db, settings, users, agent):
    occ = make_occurrence(db, days_ago=3)
    detail = client.get(f"/api/occurrences/{occ.id}", headers=agent).json()
    assert detail["risk"]["type_weight"] == 5 and detail["risk"]["days_open"] == 3


# --- heat map and indicators --------------------------------------------------------------


def test_public_heat_is_risk_weighted_and_snapped_to_the_grid(client, db, settings):
    a = make_occurrence(db, "standing_water", days_ago=2)  # 10
    b = make_occurrence(
        db, "dead_animal", point=offset_m(*MC, east_m=3), days_ago=2
    )  # 2, same cell
    make_occurrence(db, point=offset_m(*MC, north_m=-700), status=S.CONFIRMED)  # not active
    points = client.get("/api/heatmap/public").json()["points"]
    cell = obfuscate_coordinate(
        MC[0], MC[1], cell_m=settings.privacy_grid_meters, ref_lat=settings.privacy_grid_ref_lat
    )
    assert (
        obfuscate_coordinate(
            *offset_m(*MC, east_m=3),
            cell_m=settings.privacy_grid_meters,
            ref_lat=settings.privacy_grid_ref_lat,
        )
        == cell
    ), "test setup: both reports must share a cell"
    assert points == [[cell[0], cell[1], 12.0]]
    assert a.id and b.id


def test_resolution_rates(client, db, settings, agent):
    first, second = report(client, db), report(client, db)
    resolve(client, first["id"], agent)
    resolve(client, second["id"], agent)
    answer(client, first, True)
    answer(client, second, False)
    stats = client.get("/api/stats/resolution", headers=agent).json()
    assert stats["closures"] == 2 and stats["confirmed"] == 1 and stats["contested"] == 1
    assert stats["confirmed_rate"] == 0.5 and stats["contested_rate"] == 0.5
    assert stats["awaiting"] == 0
    assert db.get(Occurrence, first["id"]).photos[-1].kind == PhotoKind.RESOLUTION
