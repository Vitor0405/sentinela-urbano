"""Sector polygons (with population) from GeoJSON, and fictitious ones for development."""

import json
import random
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Sector

FICTITIOUS_SOURCE = "ficticio (seed)"


class SectorImportError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors[:5]))
        self.errors = errors


@dataclass(frozen=True)
class SectorData:
    code: str
    name: str
    population: int
    geometry: dict  # GeoJSON Polygon or MultiPolygon


def parse_sectors_geojson(
    payload: dict,
    *,
    code_field: str = "codigo",
    name_field: str = "nome",
    population_field: str = "populacao",
) -> list[SectorData]:
    """FeatureCollection → sectors. Every feature needs a code, a name and population > 0."""
    if payload.get("type") != "FeatureCollection":
        raise SectorImportError(["O arquivo precisa ser um GeoJSON FeatureCollection."])
    sectors: list[SectorData] = []
    errors: list[str] = []
    seen: set[str] = set()
    for index, feature in enumerate(payload.get("features") or [], start=1):
        props = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        code = str(props.get(code_field, "")).strip()
        name = str(props.get(name_field, "") or code).strip()
        label = f"Feição {index}" + (f" ({code})" if code else "")
        if not code:
            errors.append(f"{label}: campo '{code_field}' ausente.")
            continue
        try:
            population = int(float(str(props.get(population_field, "")).replace(",", ".")))
        except ValueError:
            errors.append(f"{label}: população inválida no campo '{population_field}'.")
            continue
        if population <= 0:
            errors.append(f"{label}: a população deve ser maior que zero.")
            continue
        if geometry.get("type") not in ("Polygon", "MultiPolygon"):
            errors.append(f"{label}: geometria deve ser Polygon ou MultiPolygon.")
            continue
        if code in seen:
            errors.append(f"{label}: código repetido.")
            continue
        seen.add(code)
        sectors.append(SectorData(code, name[:120], population, geometry))
    if errors:
        raise SectorImportError(errors)
    if not sectors:
        raise SectorImportError(["Nenhum setor encontrado no arquivo."])
    return sectors


def _geom(geometry: dict):
    # Always stored as a valid MultiPolygon in SRID 4326.
    return func.ST_Multi(
        func.ST_CollectionExtract(
            func.ST_MakeValid(func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geometry)), 4326)),
            3,
        )
    )


def import_sectors(
    db: Session, sectors: list[SectorData], source: str, replace: bool = False
) -> tuple[int, int, int]:
    """Upsert by code. With `replace`, sectors absent from the file are removed (with
    their LIRAa results). Returns (inserted, updated, removed). The caller commits."""
    existing = {s.code: s for s in db.scalars(select(Sector))}
    inserted = updated = removed = 0
    for data in sectors:
        sector = existing.get(data.code)
        if sector is None:
            db.add(
                Sector(
                    code=data.code,
                    name=data.name,
                    population=data.population,
                    geom=_geom(data.geometry),
                    source=source,
                )
            )
            inserted += 1
        else:
            sector.name, sector.population, sector.source = data.name, data.population, source
            sector.geom = _geom(data.geometry)
            updated += 1
    if replace:
        codes = {d.code for d in sectors}
        for code, sector in existing.items():
            if code not in codes:
                db.delete(sector)
                removed += 1
    db.flush()
    return inserted, updated, removed


def fictitious_grid(
    bbox: tuple[float, float, float, float], rows: int = 4, cols: int = 4, seed: int = 7
) -> list[SectorData]:
    """Demo sectors: a rows × cols grid over bbox with made-up population.

    Clearly fictitious (code 'F01'…, source 'ficticio (seed)'); real sectors must be
    imported from the municipality's files.
    """
    rng = random.Random(seed)
    min_lon, min_lat, max_lon, max_lat = bbox
    dlon, dlat = (max_lon - min_lon) / cols, (max_lat - min_lat) / rows
    sectors = []
    n = 0
    for r in range(rows):
        for c in range(cols):
            n += 1
            west, south = min_lon + c * dlon, min_lat + r * dlat
            ring = [
                [west, south],
                [west + dlon, south],
                [west + dlon, south + dlat],
                [west, south + dlat],
                [west, south],
            ]
            sectors.append(
                SectorData(
                    code=f"F{n:02d}",
                    name=f"Setor fictício {n:02d}",
                    population=rng.randrange(6_000, 28_000, 100),
                    geometry={"type": "Polygon", "coordinates": [ring]},
                )
            )
    return sectors
