"""API tests against PostgreSQL/PostGIS (skipped when the test database is unreachable)."""

import io
import math

import pytest
from PIL import Image
from sqlalchemy import select

from app.models import Notification, Occurrence, OccurrenceType, UserRole
from app.services.notifications import build_new_occurrence_email, queue_new_occurrence_email
from app.services.occurrences import make_point
from app.services.photos import resolve_photo_path
from app.services.privacy import grid_steps, obfuscate_coordinate
from tests.conftest import PASSWORD, auth_header, jpeg_with_exif

pytestmark = pytest.mark.db

# A point deliberately away from its grid cell centre.
EXACT = (-16.72031, -43.86577)  # Montes Claros, perto da Praça Dr. Chaves


def water_type_id(db) -> int:
    return db.scalar(select(OccurrenceType.id).where(OccurrenceType.code == "standing_water"))


def post_occurrence(client, db, *, lat=EXACT[0], lon=EXACT[1], headers=None, photos=1, **form):
    data = {
        "type_id": str(water_type_id(db)),
        "latitude": str(lat),
        "longitude": str(lon),
        "description": "Pneus acumulando água na calçada",
        **form,
    }
    files = [("photos", (f"foto{i}.jpg", jpeg_with_exif(), "image/jpeg")) for i in range(photos)]
    return client.post("/api/occurrences", data=data, files=files, headers=headers or {})


def snapped(settings, lat, lon):
    return obfuscate_coordinate(
        lat, lon, cell_m=settings.privacy_grid_meters, ref_lat=settings.privacy_grid_ref_lat
    )


# --- registration -------------------------------------------------------------------------


def test_visitor_can_register_without_account_and_gets_protocol(client, db, settings):
    response = post_occurrence(client, db, reporter_name="Ana", reporter_contact="ana@x.test")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["protocol"].startswith("SU-") and body["protocol"].endswith(f"{body['id']:06d}")
    assert body["status"] == "aberta"
    assert body["department"].startswith("Vigilância em Saúde")
    assert len(body["tracking_token"]) >= 24

    occurrence = db.get(Occurrence, body["id"])
    assert occurrence.author_id is None
    assert occurrence.reporter_name == "Ana"
    assert occurrence.tracking_token_hash != body["tracking_token"]
    assert math.isclose(occurrence.latitude, EXACT[0], abs_tol=1e-9)
    assert [h.to_status for h in occurrence.history] == ["aberta"]


def test_anonymous_report_discards_name_and_contact(client, db, settings):
    response = post_occurrence(
        client, db, is_anonymous="true", reporter_name="Ana", reporter_contact="ana@x.test"
    )
    occurrence = db.get(Occurrence, response.json()["id"])
    assert occurrence.is_anonymous
    assert occurrence.reporter_name is None and occurrence.reporter_contact is None


def test_logged_in_resident_becomes_the_author(client, db, settings, users):
    headers = auth_header(client, users[UserRole.RESIDENT].email)
    response = post_occurrence(client, db, headers=headers)
    occurrence = db.get(Occurrence, response.json()["id"])
    assert occurrence.author_id == users[UserRole.RESIDENT].id
    mine = client.get("/api/occurrences/mine", headers=headers).json()["items"]
    assert [i["protocol"] for i in mine] == [occurrence.protocol]


def test_stored_photo_has_no_exif(client, db, settings):
    response = post_occurrence(client, db)
    occurrence = db.get(Occurrence, response.json()["id"])
    path = resolve_photo_path(settings.upload_dir, occurrence.photos[0].storage_key)
    raw = path.read_bytes()
    with Image.open(io.BytesIO(raw)) as img:
        assert len(img.getexif()) == 0
    assert b"FabricanteTeste" not in raw


@pytest.mark.parametrize("photos, message", [(0, "pelo menos uma foto"), (4, "no máximo 3")])
def test_photo_count_is_enforced(client, db, settings, photos, message):
    response = post_occurrence(client, db, photos=photos)
    assert response.status_code == 422
    if photos:  # with zero files FastAPI rejects the missing field before our check
        assert message in response.json()["detail"]


def test_rejects_invalid_type_and_out_of_range_coordinates(client, db, settings):
    assert post_occurrence(client, db, type_id="999999").status_code == 422
    assert post_occurrence(client, db, lat=-95).status_code == 422


def test_only_montes_claros_is_served_by_default(client, db, settings, monkeypatch):
    monkeypatch.setattr(settings, "service_area_bbox", "-44.2107,-17.1458,-43.6665,-16.0845")
    assert post_occurrence(client, db).status_code == 201
    response = post_occurrence(client, db, lat=-23.55, lon=-46.63)  # São Paulo
    assert response.status_code == 422
    assert "fora de Montes Claros (MG)" in response.json()["detail"]


def test_new_occurrence_queues_email_with_exact_coordinates(db, settings, monkeypatch):
    monkeypatch.setattr(settings, "notifications_enabled", True)
    occurrence = Occurrence(
        type=db.get(OccurrenceType, water_type_id(db)),
        location=make_point(-16.72031, -43.86577),
        description="teste",
        tracking_token_hash="x" * 64,
        protocol="SU-2026-999999",
    )
    db.add(occurrence)
    db.flush()
    notification = queue_new_occurrence_email(db, occurrence)
    db.flush()
    db.refresh(occurrence)
    assert notification.recipient == settings.prefecture_email
    assert db.scalar(select(Notification).where(Notification.occurrence_id == occurrence.id))
    msg = build_new_occurrence_email(occurrence, notification.recipient, settings)
    assert "SU-2026-999999" in msg["Subject"]
    assert "-16.720310, -43.865770" in msg.get_body().get_content()


# --- public map and privacy ---------------------------------------------------------------


def test_public_map_only_exposes_the_snapped_coordinate(client, db, settings):
    post_occurrence(client, db)
    items = client.get("/api/occurrences/public").json()["items"]
    assert len(items) == 1
    item = items[0]
    assert item["location_is_exact"] is False
    assert (item["latitude"], item["longitude"]) == snapped(settings, *EXACT)
    assert (item["latitude"], item["longitude"]) != EXACT
    assert item["id"] is None
    assert "description" not in item and "photos" not in item and "reporter" not in item


def test_tiny_bbox_around_the_exact_point_does_not_reveal_it(client, db, settings):
    """Filtering must use the snapped point, or small bboxes would locate the report."""
    post_occurrence(client, db)
    lat, lon = EXACT
    eps = 0.00002  # ~2 m
    tiny = f"{lon - eps},{lat - eps},{lon + eps},{lat + eps}"
    assert snapped(settings, lat, lon) != EXACT
    assert client.get("/api/occurrences/public", params={"bbox": tiny}).json()["items"] == []

    s_lat, s_lon = snapped(settings, lat, lon)
    around_cell = f"{s_lon - eps},{s_lat - eps},{s_lon + eps},{s_lat + eps}"
    found = client.get("/api/occurrences/public", params={"bbox": around_cell}).json()["items"]
    assert len(found) == 1


def test_bbox_query_finds_points_whose_cell_centre_is_inside(client, db, settings):
    """The SQL pre-filter is padded by a cell, so edge points are not lost."""
    lat_step, lon_step = grid_steps(settings.privacy_grid_meters, settings.privacy_grid_ref_lat)
    post_occurrence(client, db)
    s_lat, s_lon = snapped(settings, *EXACT)
    box = f"{s_lon - lon_step / 4},{s_lat - lat_step / 4},{s_lon + 1},{s_lat + 1}"
    assert len(client.get("/api/occurrences/public", params={"bbox": box}).json()["items"]) == 1


def test_public_map_filters_by_type_and_status(client, db, settings):
    post_occurrence(client, db)
    get = lambda **p: client.get("/api/occurrences/public", params=p).json()["items"]  # noqa: E731
    assert len(get(type="standing_water")) == 1
    assert get(type="dead_animal") == []
    assert len(get(status="aberta")) == 1
    assert get(status="confirmada") == []


# --- staff access -------------------------------------------------------------------------


def test_exact_coordinates_require_agent_or_manager(client, db, settings, users):
    post_occurrence(client, db)
    assert client.get("/api/occurrences").status_code == 401
    resident = auth_header(client, users[UserRole.RESIDENT].email)
    assert client.get("/api/occurrences", headers=resident).status_code == 403

    for role in (UserRole.AGENT, UserRole.MANAGER):
        headers = auth_header(client, users[role].email)
        items = client.get("/api/occurrences", headers=headers).json()["items"]
        assert items[0]["location_is_exact"] is True
        assert (items[0]["latitude"], items[0]["longitude"]) == pytest.approx(EXACT)


def test_detail_hides_reporter_of_anonymous_reports_from_staff(client, db, settings, users):
    occurrence_id = post_occurrence(client, db, is_anonymous="true").json()["id"]
    agent = auth_header(client, users[UserRole.AGENT].email)
    detail = client.get(f"/api/occurrences/{occurrence_id}", headers=agent).json()
    assert detail["reporter"] is None
    assert detail["latitude"] == pytest.approx(EXACT[0])


def test_detail_is_not_found_for_the_public_and_other_residents(client, db, settings, users):
    occurrence_id = post_occurrence(client, db).json()["id"]
    assert client.get(f"/api/occurrences/{occurrence_id}").status_code == 404
    resident = auth_header(client, users[UserRole.RESIDENT].email)
    assert client.get(f"/api/occurrences/{occurrence_id}", headers=resident).status_code == 404


# --- tracking and photos ------------------------------------------------------------------


def test_tracking_by_protocol_without_token_shows_only_public_data(client, db, settings):
    body = post_occurrence(client, db).json()
    data = client.get(f"/api/tracking/{body['protocol']}").json()
    assert data["status"] == "aberta"
    assert data["is_owner"] is False
    assert data["location_is_exact"] is False
    assert data["description"] is None and data["photos"] == []
    assert [h["to_status"] for h in data["history"]] == ["aberta"]


def test_tracking_token_unlocks_exact_point_and_photos(client, db, settings):
    body = post_occurrence(client, db).json()
    headers = {"X-Tracking-Token": body["tracking_token"]}
    data = client.get(f"/api/tracking/{body['protocol']}", headers=headers).json()
    assert data["is_owner"] is True
    assert data["location_is_exact"] is True
    photo_url = data["photos"][0]["url"]

    assert client.get(photo_url).status_code == 404
    assert client.get(photo_url, headers={"X-Tracking-Token": "errado"}).status_code == 404
    photo = client.get(photo_url, headers=headers)
    assert photo.status_code == 200
    assert photo.headers["content-type"] == "image/jpeg"


def test_unknown_protocol_is_404(client, db, settings):
    assert client.get("/api/tracking/SU-2026-000000").status_code == 404


# --- auth ---------------------------------------------------------------------------------


def test_registration_requires_current_terms_and_creates_a_resident(client, db, settings):
    payload = {
        "name": "Maria",
        "email": "Maria@Exemplo.test",
        "password": "senha-forte-1",
        "accept_terms": False,
        "terms_version": settings.terms_version,
    }
    assert client.post("/api/auth/register", json=payload).status_code == 422
    assert (
        client.post(
            "/api/auth/register", json={**payload, "accept_terms": True, "terms_version": "velho"}
        ).status_code
        == 409
    )

    response = client.post("/api/auth/register", json={**payload, "accept_terms": True})
    assert response.status_code == 201
    assert response.json()["user"]["role"] == "morador"
    assert response.json()["user"]["email"] == "maria@exemplo.test"
    duplicate = client.post("/api/auth/register", json={**payload, "accept_terms": True})
    assert duplicate.status_code == 409


def test_login_rejects_wrong_password_and_bad_tokens(client, db, settings, users):
    email = users[UserRole.AGENT].email
    assert (
        client.post("/api/auth/login", json={"email": email, "password": "errada"}).status_code
        == 401
    )
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer lixo"}).status_code == 401
    me = client.get("/api/auth/me", headers=auth_header(client, email.upper()))
    assert me.json()["role"] == "agente"


def test_dev_users_on_reserved_test_domains_can_log_in(client, db, settings, users, monkeypatch):
    """Regression: e-mail format checks must not block login of the seeded @*.test users."""
    monkeypatch.setattr(settings, "allow_test_email_domains", False)
    response = client.post(
        "/api/auth/login", json={"email": users[UserRole.AGENT].email, "password": PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "agente@teste.test"


def test_registration_rejects_test_domains_unless_enabled(client, db, settings, monkeypatch):
    monkeypatch.setattr(settings, "allow_test_email_domains", False)
    payload = {
        "name": "Maria",
        "email": "maria@exemplo.test",
        "password": "senha-forte-1",
        "accept_terms": True,
        "terms_version": settings.terms_version,
    }
    assert client.post("/api/auth/register", json=payload).status_code == 422
    assert (
        client.post("/api/auth/register", json={**payload, "email": "nao-e-email"}).status_code
        == 422
    )


def test_meta_exposes_the_service_area_for_the_web_client(client, db, settings, monkeypatch):
    monkeypatch.setattr(settings, "service_area_bbox", "-44.2107,-17.1458,-43.6665,-16.0845")
    area = client.get("/api/meta").json()["service_area"]
    assert area["name"] == "Montes Claros (MG)"
    assert area["bbox"] == [-44.2107, -17.1458, -43.6665, -16.0845]
