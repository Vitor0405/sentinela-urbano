from datetime import datetime
from decimal import Decimal

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import get_settings
from app.models import OccurrenceStatus, PhotoKind, UserRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    # Already validated at registration; re-validating here would reject the dev `.test` users.
    email: str
    role: UserRole


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)
    accept_terms: bool
    terms_version: str

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        try:
            result = validate_email(
                value,
                check_deliverability=False,
                # Reserved `.test` domains are accepted only when explicitly enabled (dev/tests).
                test_environment=get_settings().allow_test_email_domains,
            )
        except EmailNotValidError as exc:
            raise ValueError("E-mail inválido.") from exc
        return result.normalized.lower()


class LoginIn(BaseModel):
    # No format check on login: an unknown address simply gets "e-mail ou senha incorretos".
    email: str = Field(max_length=254)
    password: str


class ForgotIn(BaseModel):
    email: str = Field(max_length=254)


class ResetIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=8, max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class DeleteAccountIn(BaseModel):
    password: str = Field(max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class OccurrenceTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str
    department: str
    weight: Decimal
    is_breeding_site: bool
    prevention_tips: str = ""
    is_other: bool = False


class OccurrenceCreatedOut(BaseModel):
    id: int
    protocol: str
    status: OccurrenceStatus
    department: str
    # Shown once to the reporter; only its hash is stored.
    tracking_token: str
    # True when this answers a re-sent offline report that had already been registered.
    replayed: bool = False


class MapItem(BaseModel):
    """One point on the map. `location_is_exact` is False on every public response."""

    protocol: str
    type_code: str
    type_name: str
    status: OccurrenceStatus
    latitude: float
    longitude: float
    location_is_exact: bool
    created_at: datetime
    confirmations: int = 0  # "eu também vi"
    # Public "X dias sem resposta" counter; None once the prefecture has responded.
    days_without_response: int | None = None
    response_overdue: bool = False
    id: int | None = None  # internal id, only for staff and authors


class MapItemsOut(BaseModel):
    items: list[MapItem]
    truncated: bool = False


class PhotoOut(BaseModel):
    id: int
    kind: PhotoKind
    width: int
    height: int
    url: str


class HistoryOut(BaseModel):
    from_status: OccurrenceStatus | None
    to_status: OccurrenceStatus
    created_at: datetime


class ReporterOut(BaseModel):
    name: str | None
    contact: str | None


class OccurrenceDetail(BaseModel):
    id: int
    protocol: str
    type: OccurrenceTypeOut
    status: OccurrenceStatus
    latitude: float
    longitude: float
    location_is_exact: bool
    description: str
    custom_type_label: str | None = None
    is_anonymous: bool
    reporter: ReporterOut | None
    is_chronic: bool
    notified_at: datetime | None
    first_response_at: datetime | None
    created_at: datetime
    updated_at: datetime
    photos: list[PhotoOut]
    history: list[HistoryOut]
    confirmations: int
    risk: "RiskOut | None" = None


class TrackingOut(BaseModel):
    protocol: str
    type_name: str
    department: str
    status: OccurrenceStatus
    created_at: datetime
    latitude: float
    longitude: float
    location_is_exact: bool
    history: list[HistoryOut]
    # Only with a valid tracking token (or for the logged-in author).
    is_owner: bool
    # True when the owner can answer "o problema foi realmente resolvido?" right now.
    can_answer: bool = False
    confirmations: int = 0
    deadline_days: int = 15
    days_without_response: int | None = None
    response_overdue: bool = False
    days_left: int | None = None
    responded_after_days: int | None = None
    # Owner, deadline missed and still no response: the ombudsman PDF is available.
    can_request_ouvidoria: bool = False
    description: str | None = None
    photos: list[PhotoOut] = []


class SensitiveNearby(BaseModel):
    name: str
    kind: str
    distance_m: float


class RiskOut(BaseModel):
    """Risk and every factor behind it, so the agent can see why an item is on top."""

    risk: float
    raw_risk: float
    capped: bool  # held at unconfirmed_risk_cap until another resident confirms
    type_weight: float
    days_open: int
    recurrence_count: int
    recurrence_factor: float
    proximity_factor: float
    nearest_sensitive: SensitiveNearby | None
    confirmations: int
    recommendation: str  # nova_visita | notificar_proprietario


class QueueItem(BaseModel):
    id: int
    protocol: str
    type_code: str
    type_name: str
    department: str
    status: OccurrenceStatus
    latitude: float
    longitude: float
    created_at: datetime
    is_chronic: bool
    risk: RiskOut
    distance_m: float | None = None  # from the agent, when a position is given


class QueueOut(BaseModel):
    items: list[QueueItem]


class ReclassifyIn(BaseModel):
    type_id: int


class StartIn(BaseModel):
    note: str = Field(default="", max_length=500)


class FeedbackIn(BaseModel):
    resolved: bool


class ConfirmationOut(BaseModel):
    confirmations: int


class HeatmapOut(BaseModel):
    # [lat, lon, summed risk] per public grid cell.
    points: list[tuple[float, float, float]]


class ResolutionStats(BaseModel):
    closures: int  # times an agent closed an occurrence
    confirmed: int  # resident answered yes
    contested: int  # resident answered no
    awaiting: int  # closed and still waiting for the resident
    confirmed_rate: float | None  # confirmed / closures
    contested_rate: float | None  # contested / closures


class RouteStop(BaseModel):
    position: int
    leg_m: float  # straight-line distance from the previous stop (or from the start)
    item: QueueItem


class RouteOut(BaseModel):
    start_latitude: float
    start_longitude: float
    stops: list[RouteStop]
    total_m: float
    straight_line: bool  # distances are straight lines, not street routes


class ScopeOut(BaseModel):
    user_id: int
    sector_ids: list[int]
    type_ids: list[int]


class ScopeIn(BaseModel):
    sector_ids: list[int] = Field(default_factory=list, max_length=500)
    type_ids: list[int] = Field(default_factory=list, max_length=50)


class StaffMemberOut(BaseModel):
    id: int
    name: str
    email: str
    role: UserRole
    is_active: bool = True
    sector_ids: list[int]
    type_ids: list[int]


class AreaAlertOut(BaseModel):
    id: int
    type_code: str
    type_name: str
    latitude: float
    longitude: float
    radius_m: int
    occurrence_count: int
    occurrence_ids: list[int]
    window_start: datetime
    window_end: datetime
    created_at: datetime


OccurrenceDetail.model_rebuild()
