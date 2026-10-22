"""Phase 5: accounts (password reset, invitations, LGPD), manager settings, hardening."""

import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.config import Settings, production_problems
from app.models import Occurrence, PasswordToken, User, UserRole
from app.ratelimit import WINDOW, SlidingWindow
from app.services import accounts
from tests.conftest import API_DIR, PASSWORD, auth_header, make_occurrence

# --- pure ------------------------------------------------------------------------------


def test_sliding_window_blocks_then_frees():
    w = SlidingWindow()
    assert all(w.hit("k", 3, 60, now=t) == 0 for t in (0, 1, 2))
    assert w.hit("k", 3, 60, now=3) == pytest.approx(57)
    assert w.hit("other", 3, 60, now=3) == 0  # keys are independent
    assert w.hit("k", 3, 60, now=60.5) == 0  # the first hit left the window


def test_production_settings_are_checked():
    unsafe = Settings()
    problems = " ".join(production_problems(unsafe))
    for word in ("JWT_SECRET", "https", "CORS", "PREFECTURE_EMAIL", "SMTP_HOST"):
        assert word in problems
    safe = Settings(
        jwt_secret="x" * 48,
        allow_test_email_domains=False,
        public_web_url="https://sentinela.exemplo.gov.br",
        cors_origins=["https://sentinela.exemplo.gov.br"],
        prefecture_email="vigilancia@montesclaros.mg.gov.br",
        smtp_host="smtp.montesclaros.mg.gov.br",
    )
    assert production_problems(safe) == []


def test_api_refuses_to_start_in_production_with_development_settings():
    env = {**os.environ, "APP_ENV": "production"}
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode != 0
    assert "Configuração insegura para produção" in result.stderr


def test_reset_demo_is_refused_in_production(monkeypatch, capsys):
    import argparse

    from app import cli

    monkeypatch.setattr(cli.get_settings(), "app_env", "production")
    assert cli.cmd_reset_demo(argparse.Namespace(yes=True, fake=0)) == 1
    assert "Recusado" in capsys.readouterr().err


# --- with database ---------------------------------------------------------------------

pytestmark_db = pytest.mark.db


@pytest.fixture
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(accounts, "send_email", lambda msg, s: sent.append(msg))
    return sent


def token_from(msg) -> str:
    body = msg.get_content()
    return body.split("#t=")[1].split("&")[0].split()[0]


@pytestmark_db
def test_security_headers(client, db, settings):
    response = client.get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Frame-Options"] == "DENY"


@pytestmark_db
def test_login_is_rate_limited(client, db, settings, users, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    WINDOW.clear()
    try:
        body = {"email": users[UserRole.RESIDENT].email, "password": "errada"}
        codes = [client.post("/api/auth/login", json=body).status_code for _ in range(11)]
        assert codes[:10] == [401] * 10 and codes[10] == 429
        blocked = client.post("/api/auth/login", json=body)
        assert "Muitas tentativas" in blocked.json()["detail"]
        assert int(blocked.headers["Retry-After"]) > 0
    finally:
        WINDOW.clear()


@pytestmark_db
def test_change_password_logs_out_other_sessions(client, db, settings, users):
    email = users[UserRole.RESIDENT].email
    old = auth_header(client, email)
    bad = client.post(
        "/api/auth/change-password",
        json={"current_password": "errada", "new_password": "nova-senha-123"},
        headers=old,
    )
    assert bad.status_code == 400
    ok = client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "nova-senha-123"},
        headers=old,
    )
    assert ok.status_code == 200
    new = {"Authorization": f"Bearer {ok.json()['access_token']}"}
    assert client.get("/api/auth/me", headers=old).status_code == 401
    assert client.get("/api/auth/me", headers=new).status_code == 200


@pytestmark_db
def test_forgot_password_does_not_reveal_accounts(client, db, settings, users, outbox):
    unknown = client.post("/api/auth/forgot", json={"email": "ninguem@teste.test"})
    known = client.post("/api/auth/forgot", json={"email": users[UserRole.RESIDENT].email})
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()
    assert len(outbox) == 1 and outbox[0]["To"] == users[UserRole.RESIDENT].email
    assert "/nova-senha#t=" in outbox[0].get_content()


@pytestmark_db
def test_reset_link_sets_the_password_once(client, db, settings, users, outbox):
    user = users[UserRole.RESIDENT]
    old_session = auth_header(client, user.email)
    client.post("/api/auth/forgot", json={"email": user.email})
    token = token_from(outbox[0])

    response = client.post("/api/auth/reset", json={"token": token, "password": "outra-senha-99"})
    assert response.status_code == 200 and response.json()["user"]["id"] == user.id
    login = client.post("/api/auth/login", json={"email": user.email, "password": "outra-senha-99"})
    assert login.status_code == 200
    assert client.get("/api/auth/me", headers=old_session).status_code == 401
    again = client.post("/api/auth/reset", json={"token": token, "password": "mais-uma-senha"})
    assert again.status_code == 400 and "inválido ou expirou" in again.json()["detail"]


@pytestmark_db
def test_expired_or_superseded_links_do_not_work(client, db, settings, users, outbox):
    user = users[UserRole.RESIDENT]
    client.post("/api/auth/forgot", json={"email": user.email})
    client.post("/api/auth/forgot", json={"email": user.email})
    first, second = token_from(outbox[0]), token_from(outbox[1])
    body = {"password": "nova-senha-123"}
    assert client.post("/api/auth/reset", json={"token": first, **body}).status_code == 400

    row = db.scalar(select(PasswordToken).where(PasswordToken.used_at.is_(None)))
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    assert client.post("/api/auth/reset", json={"token": second, **body}).status_code == 400


@pytestmark_db
def test_manager_invites_an_agent_who_sets_their_password(client, db, settings, users, outbox):
    manager = auth_header(client, users[UserRole.MANAGER].email)
    agent = auth_header(client, users[UserRole.AGENT].email)
    payload = {"name": "Nova Agente", "email": "nova.agente@teste.test", "role": "agente"}
    assert client.post("/api/staff", json=payload, headers=agent).status_code == 403

    created = client.post("/api/staff", json=payload, headers=manager)
    assert created.status_code == 201 and created.json()["role"] == "agente"
    assert client.post("/api/staff", json=payload, headers=manager).status_code == 409
    assert outbox[0]["Subject"].endswith("Convite para a equipe")
    assert "tipo=convite" in outbox[0].get_content()

    token = token_from(outbox[0])
    set_pw = client.post("/api/auth/reset", json={"token": token, "password": "senha-da-agente"})
    assert set_pw.json()["user"]["role"] == "agente"
    login = client.post(
        "/api/auth/login",
        json={"email": "nova.agente@teste.test", "password": "senha-da-agente"},
    )
    assert login.status_code == 200


@pytestmark_db
def test_deactivated_staff_is_logged_out(client, db, settings, users):
    manager_user, agent_user = users[UserRole.MANAGER], users[UserRole.AGENT]
    manager = auth_header(client, manager_user.email)
    agent = auth_header(client, agent_user.email)
    off = client.patch(f"/api/staff/{agent_user.id}", json={"is_active": False}, headers=manager)
    assert off.json()["is_active"] is False
    assert client.get("/api/queue", headers=agent).status_code == 401
    login = client.post("/api/auth/login", json={"email": agent_user.email, "password": PASSWORD})
    assert login.status_code == 401
    self_off = client.patch(
        f"/api/staff/{manager_user.id}", json={"is_active": False}, headers=manager
    )
    assert self_off.status_code == 409
    client.patch(f"/api/staff/{agent_user.id}", json={"is_active": True}, headers=manager)
    assert (
        client.get("/api/queue", headers=auth_header(client, agent_user.email)).status_code == 200
    )


@pytestmark_db
def test_resident_downloads_their_data(client, db, settings, users):
    resident = users[UserRole.RESIDENT]
    make_occurrence(db, author=resident)
    db.commit()
    response = client.get("/api/me/data", headers=auth_header(client, resident.email))
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    data = response.json()
    assert data["conta"]["email"] == resident.email
    assert len(data["ocorrencias_registradas"]) == 1
    assert "password" not in response.text and "token" not in response.text


@pytestmark_db
def test_resident_deletes_account_and_reports_stay_anonymous(client, db, settings, users):
    resident = users[UserRole.RESIDENT]
    occ = make_occurrence(db, author=resident)
    db.commit()
    headers = auth_header(client, resident.email)
    assert (
        client.post("/api/me/delete", json={"password": "errada"}, headers=headers).status_code
        == 400
    )
    response = client.post("/api/me/delete", json={"password": PASSWORD}, headers=headers)
    assert response.json() == {"anonymised_occurrences": 1}
    db.expire_all()
    assert db.get(User, resident.id) is None
    kept = db.get(Occurrence, occ.id)
    assert kept.author_id is None and kept.is_anonymous is True
    login = client.post("/api/auth/login", json={"email": resident.email, "password": PASSWORD})
    assert login.status_code == 401


@pytestmark_db
def test_staff_accounts_are_not_self_deleted(client, db, settings, users):
    agent = users[UserRole.AGENT]
    response = client.post(
        "/api/me/delete", json={"password": PASSWORD}, headers=auth_header(client, agent.email)
    )
    assert response.status_code == 409 and "desativação" in response.json()["detail"]


@pytestmark_db
def test_manager_tunes_coefficients_and_weights(client, db, settings, users):
    manager = auth_header(client, users[UserRole.MANAGER].email)
    agent = auth_header(client, users[UserRole.AGENT].email)
    assert client.get("/api/settings", headers=agent).status_code == 403

    view = client.get("/api/settings", headers=manager).json()
    keys = {c["key"] for c in view["coefficients"]}
    assert {"unconfirmed_risk_cap", "response_deadline_days", "cluster_radius_m"} <= keys
    assert len(view["types"]) == 9

    bad = client.put(
        "/api/settings/coefficients",
        json={"values": {"sensitive_radius_m": 99999, "nao_existe": 1, "route_max_stops": 2.5}},
        headers=manager,
    )
    assert bad.status_code == 422
    detail = bad.json()["detail"]
    assert "sensitive_radius_m" in detail and "nao_existe" in detail and "inteiro" in detail

    ok = client.put(
        "/api/settings/coefficients",
        json={"values": {"response_deadline_days": 10}},
        headers=manager,
    ).json()
    deadline = next(c for c in ok["coefficients"] if c["key"] == "response_deadline_days")
    assert deadline["value"] == 10

    # A heavier weight changes the risk index immediately (it is computed at query time).
    occ = make_occurrence(db, "dead_animal", days_ago=2)
    db.commit()
    animal = next(t for t in view["types"] if t["code"] == "dead_animal")
    client.put(
        f"/api/settings/types/{animal['id']}",
        json={"weight": 4, "department": "Zoonoses", "prevention_tips": "Texto novo."},
        headers=manager,
    )
    detail = client.get(f"/api/occurrences/{occ.id}", headers=agent).json()
    assert detail["risk"]["type_weight"] == 4
    tips = {t["code"]: t["prevention_tips"] for t in client.get("/api/occurrence-types").json()}
    assert tips["dead_animal"] == "Texto novo."
