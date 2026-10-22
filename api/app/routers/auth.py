from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select

from app.config import get_settings
from app.deps import CurrentUser, DbSession
from app.models import User, UserRole
from app.ratelimit import rate_limit
from app.schemas import ChangePasswordIn, ForgotIn, LoginIn, RegisterIn, ResetIn, TokenOut, UserOut
from app.security import create_access_token, hash_password, verify_password
from app.services.accounts import (
    RESET,
    AccountError,
    change_password,
    issue_password_token,
    send_password_email,
    set_password_with_token,
)

router = APIRouter(prefix="/auth", tags=["autenticação"])


def _token_for(user: User) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user.id, user.role.value, user.token_version),
        user=UserOut.model_validate(user),
    )


@router.post(
    "/register",
    response_model=TokenOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("register", 5, 3600))],
)
def register(data: RegisterIn, db: DbSession) -> TokenOut:
    settings = get_settings()
    if not data.accept_terms:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "É preciso aceitar o termo de uso."
        )
    if data.terms_version != settings.terms_version:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "O termo de uso foi atualizado. Recarregue a página e leia a nova versão.",
        )
    email = data.email.lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe uma conta com este e-mail.")

    # Self-registration always creates a resident; agents and managers are created by the CLI.
    user = User(
        name=data.name.strip(),
        email=email,
        password_hash=hash_password(data.password),
        role=UserRole.RESIDENT,
        terms_version=settings.terms_version,
        terms_accepted_at=datetime.now(UTC),
    )
    db.add(user)
    db.commit()
    return _token_for(user)


@router.post(
    "/login", response_model=TokenOut, dependencies=[Depends(rate_limit("login", 10, 300))]
)
def login(data: LoginIn, db: DbSession) -> TokenOut:
    user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    if user is None or not user.is_active or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos.")
    return _token_for(user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user


@router.post(
    "/forgot",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("forgot", 5, 3600))],
)
def forgot_password(data: ForgotIn, db: DbSession, background: BackgroundTasks) -> dict:
    """Same answer whether or not the e-mail exists, so accounts cannot be discovered."""
    user = db.scalar(select(User).where(func.lower(User.email) == data.email.strip().lower()))
    if user is not None and user.is_active:
        token = issue_password_token(db, user, RESET)
        db.commit()
        background.add_task(send_password_email, get_settings(), user, token, RESET)
    return {
        "message": "Se existir uma conta com este e-mail, enviamos um link para criar uma nova senha."
    }


@router.post(
    "/reset", response_model=TokenOut, dependencies=[Depends(rate_limit("reset", 10, 3600))]
)
def reset_password(data: ResetIn, db: DbSession) -> TokenOut:
    """Set a new password with the e-mailed link (reset or invitation) and log in."""
    try:
        user = set_password_with_token(db, data.token, data.password)
    except AccountError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    db.commit()
    return _token_for(user)


@router.post("/change-password", response_model=TokenOut)
def change_my_password(data: ChangePasswordIn, db: DbSession, user: CurrentUser) -> TokenOut:
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A senha atual está incorreta.")
    change_password(user, data.new_password)
    db.commit()
    return _token_for(user)  # the other sessions are logged out
