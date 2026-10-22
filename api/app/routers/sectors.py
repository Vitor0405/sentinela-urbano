import csv
import io
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from app.config import get_settings
from app.deps import DbSession, ManagerUser, StaffUser
from app.services.indicators import (
    liraa_comparison,
    liraa_periods,
    make_period,
    overview,
    sector_current,
)
from app.services.liraa import LiraaCsvError, parse_liraa_csv, save_liraa

router = APIRouter(tags=["setores, LIRAa e indicadores"])

MAX_CSV_BYTES = 2 * 1024 * 1024


def _feature_collection(sectors: list[dict], **meta) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": s["geometry"],
                "properties": {k: v for k, v in s.items() if k != "geometry"},
            }
            for s in sectors
        ],
        **meta,
    }


@router.get("/sectors/current")
def sectors_current(db: DbSession, _: StaffUser) -> dict:
    """Current risk per sector (active occurrences), per 1,000 inhabitants, as GeoJSON."""
    return _feature_collection(sector_current(db))


@router.get("/liraa/periods")
def periods(db: DbSession, _: StaffUser) -> list[dict]:
    return liraa_periods(db)


@router.get("/liraa/comparison")
def comparison(db: DbSession, _: StaffUser, period: Annotated[str | None, Query()] = None) -> dict:
    """Community index vs LIRAa (IIP) per sector, side by side, with Spearman's rho."""
    result = liraa_comparison(db, period)
    sectors = result.pop("sectors")
    return _feature_collection(sectors, meta=result)


@router.post("/liraa/import")
def import_liraa(
    db: DbSession,
    _: ManagerUser,
    file: Annotated[UploadFile, File(description="CSV: setor;periodo;data;iip;ib")],
) -> dict:
    """Upload a LIRAa CSV. All lines are validated; nothing is saved if any is wrong."""
    raw = file.file.read(MAX_CSV_BYTES + 1)
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Arquivo maior que 2 MB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")  # spreadsheets exported on Windows
    try:
        rows = parse_liraa_csv(text)
        inserted, updated = save_liraa(db, rows)
    except LiraaCsvError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"message": "O arquivo não foi importado.", "errors": exc.errors[:50]},
        ) from exc
    db.commit()
    return {"inserted": inserted, "updated": updated, "lines": len(rows)}


@router.get("/indicators")
def indicators(
    db: DbSession,
    _: StaffUser,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> dict:
    """Management panel (default: last 90 days)."""
    settings = get_settings()
    today = datetime.now(ZoneInfo(settings.timezone)).date()
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Data inicial após a final.")
    return overview(db, make_period(date_from, date_to, today, settings.timezone))


@router.get("/indicators/sectors.csv")
def sectors_csv(db: DbSession, _: StaffUser) -> Response:
    """Per-sector indicators for spreadsheets (backlog story 12)."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(
        [
            "codigo",
            "setor",
            "populacao",
            "ocorrencias_ativas",
            "ativas_por_mil_hab",
            "risco_total",
            "risco_por_mil_hab",
            "fonte",
        ]
    )
    for s in sector_current(db):
        writer.writerow(
            [
                s["code"],
                s["name"],
                s["population"],
                s["active_count"],
                _br(s["active_per_1000"]),
                _br(s["risk_sum"]),
                _br(s["risk_per_1000"]),
                s["source"],
            ]
        )
    return Response(
        "﻿" + out.getvalue(),  # BOM so Excel opens the accents correctly
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="indicadores-setores.csv"'},
    )


def _br(value: float) -> str:
    return f"{value:.3f}".replace(".", ",")
