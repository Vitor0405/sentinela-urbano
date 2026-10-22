import io
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from PIL import Image, TiffImagePlugin
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import UserRole
from app.seeding import create_user, seed_reference_data

API_DIR = Path(__file__).resolve().parents[1]
PASSWORD = "senha-de-teste-123"


def jpeg_with_exif(size=(400, 300), orientation: int | None = None) -> bytes:
    """JPEG carrying camera make/model and a GPS position, like a phone photo."""
    img = Image.new("RGB", size, (200, 60, 60))
    img.paste((20, 20, 220), (0, 0, size[0] // 4, size[1] // 4))  # marks the top-left corner
    exif = img.getexif()
    exif[0x010F] = "FabricanteTeste"  # Make
    exif[0x0110] = "ModeloTeste"  # Model
    if orientation:
        exif[0x0112] = orientation
    gps = exif.get_ifd(0x8825)
    r = TiffImagePlugin.IFDRational
    gps[1] = "S"
    gps[2] = (r(16, 1), r(40, 1), r(47, 1))
    gps[3] = "W"
    gps[4] = (r(49, 1), r(15, 1), r(18, 1))
    out = io.BytesIO()
    img.save(out, format="JPEG", exif=exif)
    return out.getvalue()


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    url = get_settings().test_database_url
    engine = create_engine(url, connect_args={"connect_timeout": 3})
    try:
        with engine.connect():
            pass
    except OperationalError:
        pytest.skip(
            f"Banco de teste indisponível ({url.rsplit('@', 1)[-1]}); suba o docker compose"
        )

    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    cfg.attributes["database_url"] = url
    # Downgrade first so the session always starts from a clean schema (and the
    # downgrade path gets exercised too).
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db(db_engine: Engine) -> Iterator[Session]:
    """Session inside an outer transaction that is rolled back after each test."""
    connection = db_engine.connect()
    outer = connection.begin()
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    seed_reference_data(session)
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def settings(tmp_path, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "upload_dir", tmp_path / "uploads")
    monkeypatch.setattr(s, "notifications_enabled", False)
    monkeypatch.setattr(s, "allow_test_email_domains", True)
    monkeypatch.setattr(s, "rate_limit_enabled", False)
    return s


@pytest.fixture
def client(db: Session, settings) -> Iterator:
    from fastapi.testclient import TestClient

    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def users(db: Session, settings) -> dict:
    return {
        role: create_user(
            db,
            f"Teste {role.value}",
            f"{role.value}@teste.test",
            role,
            PASSWORD,
            settings.terms_version,
        )
        for role in UserRole
    }


def auth_header(client, email: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# --- factories for risk / chronic tests ---------------------------------------------------

MC = (-16.72031, -43.86577)  # Montes Claros, near Praça Doutor Chaves


def offset_m(lat: float, lon: float, north_m: float = 0.0, east_m: float = 0.0):
    """Point `north_m`/`east_m` metres away (flat approximation, fine at this scale)."""
    import math

    return (
        lat + north_m / 111_320.0,
        lon + east_m / (111_320.0 * math.cos(math.radians(lat))),
    )


def make_occurrence(
    db: Session,
    type_code: str = "standing_water",
    point: tuple[float, float] = MC,
    status=None,
    days_ago: int = 0,
    author=None,
):
    """Insert an occurrence directly (bypassing the API) at a given place and age."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.models import Occurrence, OccurrenceStatus, OccurrenceType
    from app.services.occurrences import make_point

    otype = db.scalar(select(OccurrenceType).where(OccurrenceType.code == type_code))
    # One extra hour keeps FLOOR(days) away from the day boundary.
    created = datetime.now(UTC) - timedelta(days=days_ago, hours=1 if days_ago else 0)
    occurrence = Occurrence(
        type=otype,
        location=make_point(*point),
        description="",
        status=status or OccurrenceStatus.OPEN,
        tracking_token_hash="0" * 64,
        author_id=author.id if author else None,
        created_at=created,
    )
    db.add(occurrence)
    db.flush()
    occurrence.protocol = f"SU-T-{occurrence.id:06d}"
    db.flush()
    return occurrence


def make_resident(db: Session, settings, name: str):
    return create_user(
        db, name, f"{name.lower()}@teste.test", UserRole.RESIDENT, PASSWORD, settings.terms_version
    )
