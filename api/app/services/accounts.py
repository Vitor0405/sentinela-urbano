"""Accounts: password reset, agent invitations, data export and account deletion (LGPD)."""

import logging
import secrets
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Occurrence, OccurrenceConfirmation, PasswordToken, User, UserRole
from app.security import hash_password, hash_tracking_token
from app.services.mailer import send_email

log = logging.getLogger(__name__)

RESET = "redefinir"
INVITE = "convite"
TTL = {RESET: timedelta(hours=1), INVITE: timedelta(days=3)}


class AccountError(ValueError):
    """pt-BR message for the API response."""


def issue_password_token(db: Session, user: User, purpose: str) -> str:
    """New single-use token (older unused ones of the same purpose stop working)."""
    now = datetime.now(UTC)
    db.execute(
        update(PasswordToken)
        .where(
            PasswordToken.user_id == user.id,
            PasswordToken.purpose == purpose,
            PasswordToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    token = secrets.token_urlsafe(32)
    db.add(
        PasswordToken(
            user_id=user.id,
            token_hash=hash_tracking_token(token),
            purpose=purpose,
            expires_at=now + TTL[purpose],
        )
    )
    db.flush()
    return token


def set_password_with_token(db: Session, token: str, new_password: str) -> User:
    now = datetime.now(UTC)
    row = db.scalar(
        select(PasswordToken).where(PasswordToken.token_hash == hash_tracking_token(token))
    )
    if row is None or row.used_at is not None or row.expires_at < now:
        raise AccountError("Este link é inválido ou expirou. Peça um novo.")
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise AccountError("Esta conta está desativada.")
    row.used_at = now
    change_password(user, new_password)
    return user


def change_password(user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    user.token_version += 1  # every other session is logged out


def password_link(settings: Settings, token: str, purpose: str) -> str:
    # Fragment: browsers never send it to servers or write it to access logs.
    return f"{settings.public_web_url.rstrip('/')}/nova-senha#t={token}&tipo={purpose}"


def send_password_email(settings: Settings, user: User, token: str, purpose: str) -> None:
    """Best effort (called as a background task): failures are logged, never raised."""
    msg = EmailMessage()
    msg["From"] = settings.mail_from
    msg["To"] = user.email
    link = password_link(settings, token, purpose)
    if purpose == INVITE:
        role = "gestor(a)" if user.role == UserRole.MANAGER else "agente de saúde"
        msg["Subject"] = "[Sentinela Urbano] Convite para a equipe"
        body = (
            f"Olá, {user.name}!\n\nVocê foi cadastrado(a) como {role} no Sentinela Urbano.\n"
            f"Para entrar, crie sua senha (o link vale por 3 dias):\n{link}\n"
        )
    else:
        msg["Subject"] = "[Sentinela Urbano] Redefinição de senha"
        body = (
            f"Olá, {user.name}!\n\nRecebemos um pedido para redefinir a sua senha.\n"
            f"Use o link abaixo (vale por 1 hora e só uma vez):\n{link}\n\n"
            "Se não foi você, ignore esta mensagem: sua senha continua a mesma.\n"
        )
    msg.set_content(body + "\nEsta mensagem foi enviada automaticamente.\n")
    try:
        send_email(msg, settings)
    except OSError as exc:
        log.warning("password e-mail to user %s failed: %s", user.id, exc)


def export_user_data(db: Session, user: User) -> dict:
    """Everything the platform keeps about this person (LGPD, art. 18)."""
    occurrences = db.scalars(
        select(Occurrence).where(Occurrence.author_id == user.id).order_by(Occurrence.created_at)
    ).unique()
    confirmations = db.scalars(
        select(OccurrenceConfirmation).where(OccurrenceConfirmation.user_id == user.id)
    ).all()
    return {
        "gerado_em": datetime.now(UTC).isoformat(),
        "conta": {
            "nome": user.name,
            "email": user.email,
            "perfil": user.role.value,
            "criada_em": user.created_at.isoformat(),
            "termo_de_uso_aceito": user.terms_version,
            "termo_aceito_em": user.terms_accepted_at.isoformat(),
        },
        "ocorrencias_registradas": [
            {
                "protocolo": o.protocol,
                "tipo": o.type_label,
                "situacao": o.status.value,
                "registrada_em": o.created_at.isoformat(),
                "latitude": o.latitude,
                "longitude": o.longitude,
                "descricao": o.description,
                "anonima": o.is_anonymous,
                "fotos": len(o.photos),
            }
            for o in occurrences
        ],
        "confirmacoes_eu_tambem_vi": [
            {"ocorrencia_id": c.occurrence_id, "em": c.created_at.isoformat()}
            for c in confirmations
        ],
        "observacao": (
            "Fotos e localização das ocorrências podem ser mantidas sem identificação, para fins de "
            "saúde pública, mesmo após a exclusão da conta."
        ),
    }


def delete_account(db: Session, user: User) -> int:
    """Delete a resident's account. Their reports stay, anonymised, for public health.

    Returns how many reports were anonymised. Staff accounts are deactivated, not deleted,
    to keep the record of who did what.
    """
    if user.role != UserRole.RESIDENT:
        raise AccountError(
            "Contas da equipe não são excluídas por aqui: peça ao gestor a desativação."
        )
    result = db.execute(
        update(Occurrence)
        .where(Occurrence.author_id == user.id)
        .values(author_id=None, is_anonymous=True, reporter_name=None, reporter_contact=None)
    )
    db.delete(user)  # confirmations, password links and scopes go with it (ON DELETE CASCADE)
    db.flush()
    return result.rowcount
