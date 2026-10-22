"""Manager-editable coefficients and risk types (calibration during the pilot)."""

import re
import unicodedata
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import aggregate_order_by

from app.deps import DbSession, ManagerUser
from app.domain.status import QUEUE_STATUSES
from app.models import Occurrence, OccurrenceType, RiskSetting

router = APIRouter(prefix="/settings", tags=["configurações"])

# Accepted range per coefficient: protects the risk index from typos (e.g. 1500 m → 15000).
RANGES: dict[str, tuple[float, float]] = {
    "min_days_open": (1, 30),
    "recurrence_increment": (0, 5),
    "recurrence_radius_m": (5, 500),
    "chronic_radius_m": (5, 500),
    "chronic_owner_notice_threshold": (1, 20),
    "sensitive_proximity_factor": (1, 5),
    "sensitive_radius_m": (20, 2000),
    "unconfirmed_risk_cap": (1, 10000),
    "cluster_radius_m": (20, 2000),
    "cluster_min_count": (2, 50),
    "cluster_window_days": (1, 90),
    "messaging_immediate_risk": (0, 10000),
    "route_max_stops": (1, 30),
    "liraa_window_days": (7, 365),
    "response_deadline_days": (1, 180),
}
INTEGER_KEYS = {
    "min_days_open",
    "chronic_owner_notice_threshold",
    "cluster_min_count",
    "cluster_window_days",
    "route_max_stops",
    "liraa_window_days",
    "response_deadline_days",
}


class CoefficientOut(BaseModel):
    key: str
    value: float
    description: str
    min: float
    max: float
    integer: bool


class TypeSettingsOut(BaseModel):
    id: int
    code: str
    name: str
    description: str
    weight: float
    department: str
    is_breeding_site: bool
    is_other: bool
    is_active: bool
    notification_email: str | None
    prevention_tips: str


class SettingsOut(BaseModel):
    coefficients: list[CoefficientOut]
    types: list[TypeSettingsOut]


class CoefficientsIn(BaseModel):
    values: dict[str, float]


class TypeSettingsIn(BaseModel):
    # Optional so older clients keep working; sent by the settings screen.
    name: str | None = Field(default=None, min_length=3, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    is_active: bool | None = None
    weight: float = Field(gt=0, le=100)
    department: str = Field(min_length=2, max_length=120)
    notification_email: EmailStr | None = None
    prevention_tips: str = Field(default="", max_length=2000)


def _out(db) -> SettingsOut:
    rows = {r.key: r for r in db.scalars(select(RiskSetting))}
    coefficients = [
        CoefficientOut(
            key=key,
            value=float(rows[key].value),
            description=rows[key].description,
            min=lo,
            max=hi,
            integer=key in INTEGER_KEYS,
        )
        for key, (lo, hi) in RANGES.items()
        if key in rows
    ]
    types = [
        TypeSettingsOut(
            id=t.id,
            code=t.code,
            name=t.name,
            description=t.description,
            weight=float(t.weight),
            department=t.department,
            is_breeding_site=t.is_breeding_site,
            is_other=t.is_other,
            is_active=t.is_active,
            notification_email=t.notification_email,
            prevention_tips=t.prevention_tips,
        )
        for t in db.scalars(select(OccurrenceType).order_by(OccurrenceType.sort_order))
    ]
    return SettingsOut(coefficients=coefficients, types=types)


@router.get("", response_model=SettingsOut)
def get_settings_view(db: DbSession, _: ManagerUser) -> SettingsOut:
    return _out(db)


@router.put("/coefficients", response_model=SettingsOut)
def update_coefficients(data: CoefficientsIn, db: DbSession, _: ManagerUser) -> SettingsOut:
    errors = []
    for key, value in data.values.items():
        if key not in RANGES:
            errors.append(f"Coeficiente desconhecido: {key}.")
            continue
        lo, hi = RANGES[key]
        if not lo <= value <= hi:
            errors.append(f"{key}: use um valor entre {lo:g} e {hi:g}.")
        elif key in INTEGER_KEYS and value != int(value):
            errors.append(f"{key}: use um número inteiro.")
    if errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, " ".join(errors))
    for key, value in data.values.items():
        row = db.get(RiskSetting, key)
        if row is not None:
            row.value = Decimal(str(value))
    db.commit()
    return _out(db)


@router.put("/types/{type_id}", response_model=SettingsOut)
def update_type(type_id: int, data: TypeSettingsIn, db: DbSession, _: ManagerUser) -> SettingsOut:
    otype = db.get(OccurrenceType, type_id)
    if otype is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tipo de risco não encontrado.")
    if data.name is not None:
        name = " ".join(data.name.split())
        if _name_taken(db, name, but=otype.id):
            raise HTTPException(status.HTTP_409_CONFLICT, f'Já existe um tipo chamado "{name}".')
        otype.name = name[0].upper() + name[1:]
    if data.description is not None:
        otype.description = data.description.strip()
    if data.is_active is not None and data.is_active != otype.is_active:
        # "Outro" is the form's safety net; turning it off would leave residents stuck.
        if otype.is_other:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, '"Outro risco" não pode ser desativado.'
            )
        # Deactivated types leave the form; their reports keep the type and the risk.
        otype.is_active = data.is_active
    otype.weight = Decimal(str(data.weight))
    otype.department = data.department.strip()
    otype.notification_email = str(data.notification_email) if data.notification_email else None
    otype.prevention_tips = data.prevention_tips.strip()
    db.commit()
    return _out(db)


class CustomLabelOut(BaseModel):
    """What residents described as "Outro", grouped (case and spacing ignored)."""

    label: str
    count: int  # reports still classified as "Outro" with this description
    active: int  # of those, still waiting for the team
    last_reported_at: datetime
    occurrence_ids: list[int]


class TypeCreateIn(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    description: str = Field(default="", max_length=300)
    weight: float = Field(gt=0, le=100)
    department: str = Field(min_length=2, max_length=120)
    is_breeding_site: bool = False
    prevention_tips: str = Field(default="", max_length=2000)
    # Also move the "Outro" reports with this description to the new type.
    from_label: str | None = Field(default=None, max_length=60)


class TypeCreatedOut(BaseModel):
    settings: SettingsOut
    type_id: int
    reclassified: int


def _label_key(column):
    return func.lower(func.regexp_replace(func.trim(column), r"\s+", " ", "g"))


@router.get("/custom-labels", response_model=list[CustomLabelOut])
def custom_labels(db: DbSession, _: ManagerUser) -> list[CustomLabelOut]:
    """Recurring descriptions are candidates for a new official type."""
    key = _label_key(Occurrence.custom_type_label)
    rows = db.execute(
        select(
            # The most recent wording represents the group.
            func.array_agg(
                aggregate_order_by(Occurrence.custom_type_label, Occurrence.created_at.desc())
            )[1].label("label"),
            func.count().label("count"),
            func.count().filter(Occurrence.status.in_(QUEUE_STATUSES)).label("active"),
            func.max(Occurrence.created_at).label("last_reported_at"),
            func.array_agg(Occurrence.id).label("ids"),
        )
        .join(OccurrenceType, OccurrenceType.id == Occurrence.type_id)
        .where(OccurrenceType.is_other, Occurrence.custom_type_label.is_not(None))
        .group_by(key)
        .order_by(func.count().desc(), func.max(Occurrence.created_at).desc())
    ).all()
    return [
        CustomLabelOut(
            label=_tidy(r.label),
            count=r.count,
            active=r.active,
            last_reported_at=r.last_reported_at,
            occurrence_ids=sorted(r.ids),
        )
        for r in rows
    ]


@router.post("/types", response_model=TypeCreatedOut, status_code=status.HTTP_201_CREATED)
def create_type(data: TypeCreateIn, db: DbSession, _: ManagerUser) -> TypeCreatedOut:
    """New official risk type, optionally absorbing the "Outro" reports that described it."""
    name = " ".join(data.name.split())
    if _name_taken(db, name):
        raise HTTPException(status.HTTP_409_CONFLICT, f'Já existe um tipo chamado "{name}".')
    regular = select(func.max(OccurrenceType.sort_order)).where(OccurrenceType.is_other.is_(False))
    otype = OccurrenceType(
        code=_new_code(db, name),
        name=name[0].upper() + name[1:],
        description=data.description.strip(),
        weight=Decimal(str(data.weight)),
        department=data.department.strip(),
        is_breeding_site=data.is_breeding_site,
        prevention_tips=data.prevention_tips.strip(),
        sort_order=(db.scalar(regular) or 0) + 1,
    )
    db.add(otype)
    db.flush()

    moved = 0
    if data.from_label:
        wanted = " ".join(data.from_label.split()).lower()
        to_move = db.scalars(
            select(Occurrence)
            .join(OccurrenceType, OccurrenceType.id == Occurrence.type_id)
            .where(OccurrenceType.is_other, _label_key(Occurrence.custom_type_label) == wanted)
        ).unique()
        for occurrence in to_move:
            occurrence.type_id = otype.id
            occurrence.custom_type_label = None
            moved += 1
    db.commit()
    return TypeCreatedOut(settings=_out(db), type_id=otype.id, reclassified=moved)


def _name_taken(db, name: str, but: int | None = None) -> bool:
    stmt = select(OccurrenceType.id).where(func.lower(OccurrenceType.name) == name.lower())
    if but is not None:
        stmt = stmt.where(OccurrenceType.id != but)
    return db.scalar(stmt) is not None


def _tidy(label: str) -> str:
    label = " ".join(label.split())
    return label[0].upper() + label[1:]


def _new_code(db, name: str) -> str:
    """Stable ASCII code from the name ("Caixa de isopor" → custom_caixa_de_isopor)."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    base = "custom_" + (re.sub(r"[^a-z0-9]+", "_", ascii_name.lower()).strip("_")[:30] or "tipo")
    code, n = base, 2
    while db.scalar(select(OccurrenceType.id).where(OccurrenceType.code == code)) is not None:
        code, n = f"{base}_{n}", n + 1
    return code
