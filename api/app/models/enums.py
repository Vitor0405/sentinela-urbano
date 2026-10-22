from enum import StrEnum

from sqlalchemy.dialects.postgresql import ENUM


class UserRole(StrEnum):
    RESIDENT = "morador"
    AGENT = "agente"
    MANAGER = "gestor"


class OccurrenceStatus(StrEnum):
    OPEN = "aberta"
    IN_PROGRESS = "em_atendimento"
    RESOLVED_BY_AGENT = "resolvida_pelo_agente"
    CONFIRMED = "confirmada"
    CONTESTED = "contestada"


class PhotoKind(StrEnum):
    REPORT = "registro"
    RESOLUTION = "resolucao"


class NotificationStatus(StrEnum):
    PENDING = "pendente"
    SENT = "enviada"
    FAILED = "falhou"


def pg_enum(enum_cls: type[StrEnum], name: str) -> ENUM:
    """Native PostgreSQL enum that stores the enum *values* (pt-BR), not the member names."""
    return ENUM(
        enum_cls,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        create_type=False,
    )


user_role_enum = pg_enum(UserRole, "user_role")
occurrence_status_enum = pg_enum(OccurrenceStatus, "occurrence_status")
photo_kind_enum = pg_enum(PhotoKind, "photo_kind")
notification_status_enum = pg_enum(NotificationStatus, "notification_status")
