import secrets
from datetime import UTC, datetime

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.config import get_settings
from app.deps import STAFF_ROLES, DbSession, ManagerUser
from app.models import OccurrenceType, Sector, User, UserRole
from app.schemas import ScopeIn, StaffMemberOut
from app.security import hash_password
from app.services.accounts import INVITE, issue_password_token, send_password_email
from app.services.scope import get_scope, set_scope


class InviteIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=254)
    role: UserRole = UserRole.AGENT


class ActiveIn(BaseModel):
    is_active: bool


router = APIRouter(tags=["equipe"])


def _member(db, user: User) -> StaffMemberOut:
    scope = get_scope(db, user)
    return StaffMemberOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        sector_ids=scope.sector_ids,
        type_ids=scope.type_ids,
    )


@router.get("/staff", response_model=list[StaffMemberOut])
def list_staff(db: DbSession, _: ManagerUser) -> list[StaffMemberOut]:
    users = db.scalars(
        select(User)
        .where(User.role.in_(STAFF_ROLES))
        .order_by(User.is_active.desc(), User.role, User.name)
    )
    return [_member(db, u) for u in users]


@router.put("/staff/{user_id}/scope", response_model=StaffMemberOut)
def update_scope(user_id: int, data: ScopeIn, db: DbSession, _: ManagerUser) -> StaffMemberOut:
    """Which sectors and risk types an agent handles. Empty lists mean no restriction."""
    user = db.get(User, user_id)
    if user is None or user.role != UserRole.AGENT:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agente não encontrado.")
    known_sectors = set(db.scalars(select(Sector.id).where(Sector.id.in_(data.sector_ids))))
    known_types = set(
        db.scalars(select(OccurrenceType.id).where(OccurrenceType.id.in_(data.type_ids)))
    )
    if known_sectors != set(data.sector_ids) or known_types != set(data.type_ids):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Setor ou tipo de risco inexistente."
        )
    set_scope(db, user, data.sector_ids, data.type_ids)
    db.commit()
    return _member(db, user)


@router.get("/sectors")
def list_sectors(db: DbSession, _: ManagerUser) -> list[dict]:
    return [
        {"id": s.id, "code": s.code, "name": s.name, "population": s.population}
        for s in db.scalars(select(Sector).order_by(Sector.code))
    ]


@router.post("/staff", response_model=StaffMemberOut, status_code=status.HTTP_201_CREATED)
def invite_staff(
    data: InviteIn, db: DbSession, _: ManagerUser, background: BackgroundTasks
) -> StaffMemberOut:
    """Create an agent (or manager) and e-mail a link to set their own password.

    Staff accept the terms through their employment with the municipality; the version
    current at the invitation is recorded.
    """
    settings = get_settings()
    if data.role not in STAFF_ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Convide agente ou gestor.")
    try:
        email = validate_email(
            data.email,
            check_deliverability=False,
            test_environment=settings.allow_test_email_domains,
        ).normalized.lower()
    except EmailNotValidError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "E-mail inválido.") from exc
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe uma conta com este e-mail.")
    user = User(
        name=data.name.strip(),
        email=email,
        # Unusable until the invitation link sets a real password.
        password_hash=hash_password(secrets.token_urlsafe(32)),
        role=data.role,
        terms_version=settings.terms_version,
        terms_accepted_at=datetime.now(UTC),
    )
    db.add(user)
    db.flush()
    token = issue_password_token(db, user, INVITE)
    db.commit()
    background.add_task(send_password_email, settings, user, token, INVITE)
    return _member(db, user)


@router.patch("/staff/{user_id}", response_model=StaffMemberOut)
def set_active(user_id: int, data: ActiveIn, db: DbSession, manager: ManagerUser) -> StaffMemberOut:
    """Deactivate (or reactivate) a staff member. Deactivation logs them out at once."""
    user = db.get(User, user_id)
    if user is None or user.role not in STAFF_ROLES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membro da equipe não encontrado.")
    if user.id == manager.id and not data.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Você não pode desativar a própria conta.")
    if user.is_active != data.is_active:
        user.is_active = data.is_active
        user.token_version += 1
    db.commit()
    return _member(db, user)
