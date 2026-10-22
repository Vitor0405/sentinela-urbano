"""Pure tests for phase 4: route planning and messaging (no database, no network)."""

import io
import json
import urllib.error
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.services import messaging
from app.services.privacy import distance_m
from app.services.route import Stop, plan_route
from tests.conftest import MC, offset_m

# --- route ------------------------------------------------------------------------------


def stop(i, north=0.0, east=0.0):
    lat, lon = offset_m(*MC, north_m=north, east_m=east)
    return Stop(i, lat, lon)


def test_route_starts_at_the_nearest_stop_and_visits_all():
    stops = [stop(1, north=900), stop(2, north=100), stop(3, north=500)]
    plan = plan_route(MC, stops)
    assert plan.order == [2, 3, 1]
    assert plan.legs_m[0] == pytest.approx(100, abs=1)
    assert plan.total_m == pytest.approx(900, abs=2)


def test_two_opt_removes_crossings():
    # Nearest neighbour from the start zig-zags between two lines; the optimised open path
    # must be no longer than walking each line once.
    stops = [
        stop(1, north=100, east=0),
        stop(2, north=100, east=600),
        stop(3, north=200, east=0),
        stop(4, north=200, east=600),
    ]
    plan = plan_route(MC, stops)
    assert sorted(plan.order) == [1, 2, 3, 4]
    assert plan.total_m <= 100 + 100 + 600 + 100 + 1


def test_route_total_is_the_sum_of_legs_and_matches_geometry():
    stops = [stop(i, north=150 * i, east=(-1) ** i * 80) for i in range(1, 7)]
    plan = plan_route(MC, stops)
    assert plan.total_m == pytest.approx(sum(plan.legs_m), abs=0.5)
    by_id = {s.id: s for s in stops}
    here, total = MC, 0.0
    for sid in plan.order:
        total += distance_m(*here, by_id[sid].lat, by_id[sid].lon)
        here = (by_id[sid].lat, by_id[sid].lon)
    assert plan.total_m == pytest.approx(total, abs=1)


def test_route_edge_cases():
    assert plan_route(MC, []).order == []
    single = plan_route(MC, [stop(7, east=50)])
    assert single.order == [7] and single.total_m == pytest.approx(50, abs=1)


# --- messaging texts --------------------------------------------------------------------

SETTINGS = Settings(public_web_url="https://sentinela.test", timezone="America/Sao_Paulo")


def fake_occurrence(i, name="Água parada"):
    return SimpleNamespace(
        id=i,
        protocol=f"SU-2026-{i:06d}",
        type=SimpleNamespace(name=name, department="Endemias", messaging_chat_id=None),
        type_label=name,
        latitude=MC[0],
        longitude=MC[1],
        created_at=datetime(2026, 10, 21, 12, tzinfo=UTC),
    )


def test_urgent_text_explains_why_and_links_to_the_panel():
    text = messaging.text_urgent_occurrence(
        fake_occurrence(5), 7.5, ["a 120 m de Escola X"], SETTINGS
    )
    assert "SU-2026-000005" in text and "7.5" in text and "Escola X" in text
    assert "https://sentinela.test/ocorrencias/5" in text
    assert "21/10/2026 09:00" in text  # local time (UTC-3)


def test_digest_counts_by_type_and_truncates_long_lists():
    occs = [fake_occurrence(i, "Água parada" if i % 2 else "Lixo e entulho") for i in range(1, 31)]
    text = messaging.text_digest(occs, SETTINGS)
    assert "30 nova(s)" in text
    assert "Água parada: 15" in text and "Lixo e entulho: 15" in text
    assert "e mais 5" in text
    assert text.count("• SU-") == messaging.DIGEST_MAX_LINES


# --- messaging delivery -----------------------------------------------------------------


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def telegram_settings(**kw):
    return Settings(
        messaging_provider="telegram",
        telegram_bot_token="123:SECRET",
        telegram_api_base="https://api.telegram.test",
        **kw,
    )


def test_telegram_posts_chat_and_text(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["body"] = json.loads(request.data)
        return FakeResponse(b'{"ok": true}')

    monkeypatch.setattr(messaging.urllib.request, "urlopen", fake_urlopen)
    messaging.send_message("Olá grupo", "-100200", telegram_settings())
    assert seen["url"] == "https://api.telegram.test/bot123:SECRET/sendMessage"
    assert seen["body"]["chat_id"] == "-100200" and seen["body"]["text"] == "Olá grupo"


def test_telegram_errors_never_leak_the_token(monkeypatch):
    def http_error(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(messaging.urllib.request, "urlopen", http_error)
    with pytest.raises(messaging.MessagingError) as error:
        messaging.send_message("x", "1", telegram_settings())
    assert "401" in str(error.value) and "SECRET" not in str(error.value)

    monkeypatch.setattr(
        messaging.urllib.request,
        "urlopen",
        lambda r, timeout: FakeResponse(b'{"ok": false, "description": "chat not found"}'),
    )
    with pytest.raises(messaging.MessagingError, match="chat not found"):
        messaging.send_message("x", "1", telegram_settings())


def test_missing_token_or_disabled_provider_fail_clearly():
    with pytest.raises(messaging.MessagingError, match="TELEGRAM_BOT_TOKEN"):
        messaging.send_message("x", "1", Settings(messaging_provider="telegram"))
    with pytest.raises(messaging.MessagingError, match="desativado"):
        messaging.send_message("x", "1", Settings(messaging_provider="none"))


def test_email_provider_simulates_the_group(monkeypatch):
    sent = []
    monkeypatch.setattr(messaging, "send_email", lambda msg, s: sent.append(msg))
    messaging.send_message("🔴 Linha 1\nLinha 2", "grupo-x", Settings(messaging_provider="email"))
    assert sent[0]["To"] == "grupo-mensagens@prefeitura.test"
    assert sent[0]["Subject"] == "[Grupo grupo-x] 🔴 Linha 1"


def test_enabled_requires_notifications_and_a_provider():
    assert messaging.enabled(Settings(messaging_provider="email")) is True
    assert messaging.enabled(Settings(messaging_provider="none")) is False
    assert (
        messaging.enabled(Settings(messaging_provider="email", notifications_enabled=False))
        is False
    )
