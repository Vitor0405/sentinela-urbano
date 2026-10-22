import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response, status

from app.deps import CurrentUser, DbSession
from app.schemas import DeleteAccountIn
from app.security import verify_password
from app.services.accounts import AccountError, delete_account, export_user_data

router = APIRouter(prefix="/me", tags=["minha conta (LGPD)"])


@router.get("/data")
def my_data(db: DbSession, user: CurrentUser) -> Response:
    """Download of everything kept about the logged-in person (LGPD, art. 18)."""
    body = json.dumps(export_user_data(db, user), ensure_ascii=False, indent=2)
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return Response(
        body,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="meus-dados-sentinela-{stamp}.json"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/delete", status_code=status.HTTP_200_OK)
def delete_me(data: DeleteAccountIn, db: DbSession, user: CurrentUser) -> dict:
    """Delete the resident's account (password required). Reports stay, anonymised."""
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Senha incorreta.")
    try:
        anonymised = delete_account(db, user)
    except AccountError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    db.commit()
    return {"anonymised_occurrences": anonymised}
