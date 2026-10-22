from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "dev-secret-change-me-in-production-0123456789"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # development | demo (production-like stack with test data) | production
    app_env: str = "development"
    # Throttling of sensitive endpoints (login, registration, reports, password reset).
    rate_limit_enabled: bool = True

    database_url: str = "postgresql+psycopg://sentinela:sentinela@localhost:5432/sentinela"
    test_database_url: str = (
        "postgresql+psycopg://sentinela:sentinela@localhost:5432/sentinela_test"
    )

    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    # Bump when the terms of use text changes; registration must accept the current version.
    terms_version: str = "2026-10"

    upload_dir: Path = Path("/data/uploads")
    max_photo_bytes: int = 10 * 1024 * 1024
    max_photos_per_occurrence: int = 3
    photo_max_side_px: int = 1600

    # Public map privacy: occurrences are snapped to a grid of ~privacy_grid_meters.
    # The reference latitude must stay fixed so the grid is stable over time.
    privacy_grid_meters: float = 100.0
    privacy_grid_ref_lat: float = -16.72  # Montes Claros (MG)

    # Service area "min_lon,min_lat,max_lon,max_lat"; empty accepts any coordinate.
    # Default: bounding box of the Montes Claros (MG) municipality, OSM relation 314620,
    # rural districts included. Reports outside it are refused.
    service_area_bbox: str = "-44.2107,-17.1458,-43.6665,-16.0845"
    service_area_name: str = "Montes Claros (MG)"
    # OSM relation of the municipality: the sensitive-points import queries exactly its area.
    service_area_osm_relation: int | None = 314620

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = False
    mail_from: str = "Sentinela Urbano <nao-responda@sentinela.test>"
    prefecture_email: str = "vigilancia@prefeitura.test"
    notifications_enabled: bool = True

    # Messaging group of the department (see app/services/messaging.py).
    # none | telegram | email (dev stand-in: the text is e-mailed to MESSAGING_DEV_EMAIL)
    messaging_provider: str = "none"
    telegram_bot_token: str = ""
    telegram_api_base: str = "https://api.telegram.org"
    messaging_chat_id: str = ""
    messaging_dev_email: str = "grupo-mensagens@prefeitura.test"

    # Offline reports may be sent days later; older ones are refused as stale.
    offline_max_age_days: int = 7

    # Public Overpass instance; only used by the import-sensitive-points command.
    overpass_url: str = "https://overpass-api.de/api/interpreter"

    timezone: str = "America/Sao_Paulo"
    public_web_url: str = "http://localhost:5173"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # Accept reserved `.test` e-mail domains at registration (dev and tests only).
    allow_test_email_domains: bool = False

    seed_password: str = "sentinela123"
    # "lat,lon" around which `seed --fake` places fictitious occurrences
    # (Montes Claros, Praça Doutor Chaves).
    seed_center: str = "-16.7207,-43.8660"

    def service_area(self) -> tuple[float, float, float, float] | None:
        if not self.service_area_bbox.strip():
            return None
        parts = [float(p) for p in self.service_area_bbox.split(",")]
        if len(parts) != 4:
            raise ValueError(
                "SERVICE_AREA_BBOX deve ter 4 números: min_lon,min_lat,max_lon,max_lat"
            )
        return parts[0], parts[1], parts[2], parts[3]


def production_problems(settings: Settings) -> list[str]:
    """Settings that are acceptable for development but unsafe for real use."""
    problems = []
    if settings.jwt_secret == DEFAULT_JWT_SECRET or len(settings.jwt_secret) < 32:
        problems.append("JWT_SECRET padrão ou curto (use 32+ caracteres aleatórios)")
    if settings.allow_test_email_domains:
        problems.append("ALLOW_TEST_EMAIL_DOMAINS ligado (aceita e-mails .test)")
    if not settings.public_web_url.startswith("https://"):
        problems.append("PUBLIC_WEB_URL sem https://")
    if any("localhost" in origin for origin in settings.cors_origins):
        problems.append("CORS_ORIGINS ainda aponta para localhost")
    if settings.prefecture_email.endswith(".test"):
        problems.append("PREFECTURE_EMAIL de teste")
    if settings.smtp_host in ("localhost", "mailpit"):
        problems.append("SMTP_HOST de desenvolvimento (Mailpit)")
    return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()
