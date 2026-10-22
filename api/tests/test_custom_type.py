"""Risk type "Outro": resident-described risks, reclassification and new official types."""

import pytest
from sqlalchemy import select

from app.models import Notification, Occurrence, OccurrenceType
from app.services.alerts import check_area_alert
from app.services.notifications import build_new_occurrence_email
from app.services.occurrences import clean_custom_label
from tests.conftest import MC, auth_header, jpeg_with_exif, make_occurrence, offset_m

# --- pure ------------------------------------------------------------------------------


def test_custom_label_is_normalized():
    assert clean_custom_label("  caixa   de isopor\n com água ") == "Caixa de isopor com água"


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "ab",
        "x" * 61,
        "ligue 38 99999-1234",
        "fale comigo@exemplo.com",
        "veja http://exemplo.com",
        "www.exemplo.com",
    ],
)
def test_custom_label_rejects_empty_long_or_contact_data(raw):
    with pytest.raises(ValueError):
        clean_custom_label(raw)


# --- database --------------------------------------------------------------------------


def other_type(db) -> OccurrenceType:
    return db.scalar(select(OccurrenceType).where(OccurrenceType.is_other))


def type_id(db, code: str) -> int:
    return db.scalar(select(OccurrenceType.id).where(OccurrenceType.code == code))


def post(client, type_id: int, label: str | None, headers=None):
    data = {"type_id": str(type_id), "latitude": str(MC[0]), "longitude": str(MC[1])}
    if label is not None:
        data["custom_type_label"] = label
    files = [("photos", ("foto.jpg", jpeg_with_exif(), "image/jpeg"))]
    return client.post("/api/occurrences", data=data, files=files, headers=headers or {})


def make_other(db, label: str, point=MC):
    occurrence = make_occurrence(db, type_code="other", point=point)
    occurrence.custom_type_label = label
    db.flush()
    return occurrence


@pytest.mark.db
def test_seed_has_one_other_type_listed_last(client, db):
    other = other_type(db)
    assert other.code == "other" and other.prevention_tips
    types = client.get("/api/occurrence-types").json()
    assert types[-1]["is_other"] is True
    assert sum(t["is_other"] for t in types) == 1


@pytest.mark.db
def test_other_requires_a_description(client, db):
    response = post(client, other_type(db).id, None)
    assert response.status_code == 422
    assert "poucas palavras" in response.json()["detail"]
    assert post(client, other_type(db).id, "tel 38999991234").status_code == 422


@pytest.mark.db
def test_label_is_private_and_ignored_for_regular_types(client, db, users):
    created = post(client, other_type(db).id, "  caixa de isopor com água ")
    assert created.status_code == 201, created.text
    body = created.json()
    occurrence = db.get(Occurrence, body["id"])
    assert occurrence.custom_type_label == "Caixa de isopor com água"

    public = client.get("/api/occurrences/public").json()["items"]
    item = next(i for i in public if i["protocol"] == body["protocol"])
    assert item["type_name"] == "Outro risco"  # the free text never reaches the public map

    staff = auth_header(client, "agente@teste.test")
    items = client.get("/api/occurrences", headers=staff).json()["items"]
    item = next(i for i in items if i["protocol"] == body["protocol"])
    assert item["type_name"] == "Outro risco: Caixa de isopor com água"

    owner = {"X-Tracking-Token": body["tracking_token"]}
    tracked = client.get(f"/api/tracking/{body['protocol']}", headers=owner).json()
    assert tracked["type_name"] == "Outro risco: Caixa de isopor com água"
    assert client.get(f"/api/tracking/{body['protocol']}").json()["type_name"] == "Outro risco"

    regular = post(client, type_id(db, "standing_water"), "texto que deve ser ignorado")
    assert db.get(Occurrence, regular.json()["id"]).custom_type_label is None


@pytest.mark.db
def test_prefecture_email_names_the_described_risk(db, settings):
    occurrence = make_other(db, "Bebedouro de animais sujo")
    msg = build_new_occurrence_email(occurrence, "vigilancia@teste.test", settings)
    assert "Outro risco: Bebedouro de animais sujo" in msg["Subject"]
    assert "Outro risco: Bebedouro de animais sujo" in msg.get_body().get_content()


@pytest.mark.db
def test_staff_reclassifies_and_the_label_goes_away(client, db, users):
    occurrence = make_other(db, "Caixa de isopor com água")
    url = f"/api/occurrences/{occurrence.id}/type"
    water = type_id(db, "standing_water")

    resident = auth_header(client, "morador@teste.test")
    assert client.put(url, json={"type_id": water}, headers=resident).status_code == 403

    agent = auth_header(client, "agente@teste.test")
    response = client.put(url, json={"type_id": water}, headers=agent)
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["type"]["code"] == "standing_water"
    assert detail["custom_type_label"] is None
    assert detail["risk"]["type_weight"] == 5  # the risk follows the new weight at once

    # Without a resident's description, "Outro" is not a valid target.
    back = client.put(url, json={"type_id": other_type(db).id}, headers=agent)
    assert back.status_code == 422


@pytest.mark.db
def test_manager_turns_a_recurring_description_into_a_type(client, db, users):
    make_other(db, "Caixa de isopor com água")
    make_other(db, "caixa  de ISOPOR com água", point=offset_m(*MC, 900, 0))
    make_other(db, "Bebedouro de animais sujo", point=offset_m(*MC, 0, 900))
    manager = auth_header(client, "gestor@teste.test")

    agent = auth_header(client, "agente@teste.test")
    assert client.get("/api/settings/custom-labels", headers=agent).status_code == 403

    labels = client.get("/api/settings/custom-labels", headers=manager).json()
    assert [(row["count"], row["active"]) for row in labels] == [(2, 2), (1, 1)]
    assert labels[0]["label"].lower() == "caixa de isopor com água"

    response = client.post(
        "/api/settings/types",
        headers=manager,
        json={
            "name": "caixa de isopor",
            "description": "Caixa de isopor ou recipiente plástico acumulando água.",
            "weight": 4,
            "department": "Vigilância em Saúde – Controle de Endemias",
            "is_breeding_site": True,
            "from_label": labels[0]["label"],
        },
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["reclassified"] == 2
    names = [t["name"] for t in created["settings"]["types"]]
    assert "Caixa de isopor" in names
    assert names[-1] == "Outro risco"  # "Outro" stays last in the form

    new_type = db.get(OccurrenceType, created["type_id"])
    assert new_type.code == "custom_caixa_de_isopor" and new_type.is_breeding_site
    remaining = client.get("/api/settings/custom-labels", headers=manager).json()
    assert [row["label"] for row in remaining] == ["Bebedouro de animais sujo"]

    duplicate = client.post(
        "/api/settings/types",
        headers=manager,
        json={"name": "CAIXA DE ISOPOR", "weight": 1, "department": "Outro"},
    )
    assert duplicate.status_code == 409

    # A typo in the name can be fixed, and a type created by mistake can be turned off.
    fix = {"weight": 4, "department": "Vigilância em Saúde – Controle de Endemias"}
    url = f"/api/settings/types/{new_type.id}"
    renamed = client.put(url, headers=manager, json={**fix, "name": "Caixa de isopor ou plástico"})
    assert renamed.status_code == 200, renamed.text
    clash = client.put(url, headers=manager, json={**fix, "name": "água PARADA"})
    assert clash.status_code == 409
    assert client.put(url, headers=manager, json={**fix, "is_active": False}).status_code == 200
    names = [t["name"] for t in client.get("/api/occurrence-types").json()]
    assert "Caixa de isopor ou plástico" not in names  # off the form
    other_url = f"/api/settings/types/{other_type(db).id}"
    keep_other = client.put(other_url, headers=manager, json={**fix, "is_active": False})
    assert keep_other.status_code == 422


@pytest.mark.db
def test_other_reports_nearby_do_not_raise_an_area_alert(db):
    for north in (0, 20, 40):
        occurrence = make_other(db, f"Coisa diferente {north}", point=offset_m(*MC, north, 0))
    assert check_area_alert(db, occurrence) is None
    assert db.scalar(select(Notification.id)) is None
