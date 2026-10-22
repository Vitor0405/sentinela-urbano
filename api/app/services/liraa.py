"""LIRAa CSV import (Levantamento Rápido de Índices para Aedes aegypti).

Expected columns (header names are case/accent-insensitive; ";" or "," as delimiter):

    setor;periodo;data;iip;ib
    S01;2026-1;15/01/2026;1,8;2,4

`setor` is the sector code; `ib` (Breteau) is optional. The whole file is validated first
and nothing is saved if any line is wrong (all or nothing), so a half-imported cycle never
skews the comparison.
"""

import csv
import io
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LiraaSurvey, Sector

MAX_LINES = 5000

ALIASES = {
    "setor": {"setor", "codigo_setor", "cod_setor", "codigo", "estrato"},
    "periodo": {"periodo", "ciclo", "levantamento"},
    "data": {"data", "data_levantamento", "data_liraa"},
    "iip": {"iip", "indice_infestacao_predial"},
    "ib": {"ib", "breteau", "indice_breteau"},
}
REQUIRED = ("setor", "periodo", "data", "iip")


class LiraaCsvError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors[:5]))
        self.errors = errors


@dataclass(frozen=True)
class LiraaRow:
    line: int
    sector_code: str
    period: str
    survey_date: date
    iip: Decimal
    ib: Decimal | None


def _key(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return plain.strip().lower().replace(" ", "_").replace("-", "_")


def _number(raw: str) -> Decimal:
    text = raw.strip().replace("%", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")  # 1.234,5 → 1234.5
    return Decimal(text)


def _date(raw: str) -> date:
    text = raw.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(text)


def liraa_class(iip: float) -> str:
    """Ministry of Health classes: < 1% satisfatório, 1–3,9% alerta, ≥ 4% risco."""
    if iip < 1:
        return "satisfatorio"
    if iip < 4:
        return "alerta"
    return "risco"


def parse_liraa_csv(text: str) -> list[LiraaRow]:
    text = text.lstrip("﻿")
    if not text.strip():
        raise LiraaCsvError(["O arquivo está vazio."])
    first_line = text.splitlines()[0]
    delimiter = ";" if first_line.count(";") >= first_line.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header = next(reader)

    columns: dict[str, int] = {}
    for index, name in enumerate(header):
        key = _key(name)
        for canonical, names in ALIASES.items():
            if key in names:
                columns[canonical] = index
    missing = [c for c in REQUIRED if c not in columns]
    if missing:
        raise LiraaCsvError([f"Coluna obrigatória ausente: {', '.join(missing)}."])

    rows: list[LiraaRow] = []
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for line, record in enumerate(reader, start=2):
        if not any(cell.strip() for cell in record):
            continue
        if line > MAX_LINES + 1:
            errors.append(f"O arquivo passa de {MAX_LINES} linhas.")
            break

        def cell(name: str, record=record) -> str:
            index = columns.get(name)
            return record[index].strip() if index is not None and index < len(record) else ""

        code, period = cell("setor"), cell("periodo")
        if not code or not period:
            errors.append(f"Linha {line}: setor e período são obrigatórios.")
            continue
        try:
            survey_date = _date(cell("data"))
        except ValueError:
            errors.append(f"Linha {line}: data inválida '{cell('data')}' (use dd/mm/aaaa).")
            continue
        try:
            iip = _number(cell("iip"))
        except InvalidOperation:
            errors.append(f"Linha {line}: IIP inválido '{cell('iip')}'.")
            continue
        if not Decimal(0) <= iip <= Decimal(100):
            errors.append(f"Linha {line}: IIP deve estar entre 0 e 100.")
            continue
        ib = None
        if cell("ib"):
            try:
                ib = _number(cell("ib"))
            except InvalidOperation:
                errors.append(f"Linha {line}: índice de Breteau inválido '{cell('ib')}'.")
                continue
            if ib < 0:
                errors.append(f"Linha {line}: índice de Breteau não pode ser negativo.")
                continue
        if (code, period) in seen:
            errors.append(f"Linha {line}: setor {code} repetido no período {period}.")
            continue
        seen.add((code, period))
        rows.append(LiraaRow(line, code, period, survey_date, iip, ib))

    if errors:
        raise LiraaCsvError(errors)
    if not rows:
        raise LiraaCsvError(["Nenhuma linha de dados encontrada."])
    return rows


def save_liraa(db: Session, rows: list[LiraaRow]) -> tuple[int, int]:
    """Upsert by (sector, period). Unknown sector codes abort the whole import."""
    sectors = {s.code: s for s in db.scalars(select(Sector))}
    unknown = sorted({r.sector_code for r in rows if r.sector_code not in sectors})
    if unknown:
        raise LiraaCsvError(
            [f"Setor(es) não cadastrado(s): {', '.join(unknown[:20])}. Importe os setores antes."]
        )
    existing = {(s.sector_id, s.period): s for s in db.scalars(select(LiraaSurvey))}
    inserted = updated = 0
    for row in rows:
        sector = sectors[row.sector_code]
        survey = existing.get((sector.id, row.period))
        if survey is None:
            db.add(
                LiraaSurvey(
                    sector_id=sector.id,
                    period=row.period,
                    survey_date=row.survey_date,
                    iip=row.iip,
                    ib=row.ib,
                )
            )
            inserted += 1
        else:
            survey.survey_date, survey.iip, survey.ib = row.survey_date, row.iip, row.ib
            updated += 1
    db.flush()
    return inserted, updated
