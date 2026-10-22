"""Import of sensitive points (schools, day-care centres, health units) from Overpass.

Run by `python -m app.cli import-sensitive-points`, on demand or from a scheduler
(cron / Agendador de Tarefas). The API never queries Overpass while serving requests.
"""

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from sqlalchemy import delete, select, tuple_
from sqlalchemy.orm import Session

from app.models import SensitivePoint
from app.services.occurrences import make_point

log = logging.getLogger(__name__)

AMENITIES = ("school", "kindergarten", "hospital", "clinic", "doctors")
USER_AGENT = "SentinelaUrbano/0.1 (vigilancia comunitaria de arbovirose; importacao agendada)"


@dataclass(frozen=True)
class SensitivePointData:
    osm_type: str
    osm_id: int
    kind: str
    name: str
    lat: float
    lon: float


def build_query(
    bbox: tuple[float, float, float, float] | None = None,
    osm_relation: int | None = None,
    timeout: int = 120,
) -> str:
    """Overpass QL for amenity=school|kindergarten|hospital|clinic|doctors and healthcare=*.

    With the municipality's OSM relation the query covers exactly its boundary, and is far
    lighter for Overpass than a large bbox; the bbox is the fallback.
    """
    if osm_relation:
        header = f"area({3_600_000_000 + osm_relation})->.city;\n"
        scope = "(area.city)"
    elif bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        header = ""
        scope = f"({min_lat},{min_lon},{max_lat},{max_lon})"  # Overpass order: S,W,N,E
    else:
        raise ValueError("informe a relação OSM do município ou um bbox")
    # Exact tag matches are much cheaper for Overpass than one regex.
    lines = [f'  nwr["amenity"="{value}"]{scope};' for value in AMENITIES]
    lines.append(f'  nwr["healthcare"]{scope};')
    body = "\n".join(lines)
    return f"[out:json][timeout:{timeout}];\n{header}(\n{body}\n);\nout center tags;"


def _kind(tags: dict) -> str | None:
    amenity = tags.get("amenity")
    if amenity in AMENITIES:
        return amenity
    healthcare = tags.get("healthcare")
    if healthcare:
        return f"healthcare:{healthcare}"[:60]
    return None


def parse_overpass(payload: dict) -> list[SensitivePointData]:
    """Elements → points. Ways/relations use their `center`; duplicates are dropped."""
    points: dict[tuple[str, int], SensitivePointData] = {}
    for element in payload.get("elements", []):
        osm_type, osm_id = element.get("type"), element.get("id")
        tags = element.get("tags") or {}
        kind = _kind(tags)
        if osm_type not in ("node", "way", "relation") or osm_id is None or kind is None:
            continue
        if osm_type == "node":
            lat, lon = element.get("lat"), element.get("lon")
        else:
            center = element.get("center") or {}
            lat, lon = center.get("lat"), center.get("lon")
        if lat is None or lon is None:
            continue
        name = (tags.get("name") or tags.get("official_name") or "").strip() or "(sem nome)"
        points[(osm_type, int(osm_id))] = SensitivePointData(
            osm_type=osm_type,
            osm_id=int(osm_id),
            kind=kind,
            name=name[:200],
            lat=float(lat),
            lon=float(lon),
        )
    return list(points.values())


def fetch_overpass(url: str, query: str, timeout: int = 180, attempts: int = 3) -> dict:
    """POST the query; retries with backoff on the busy answers Overpass often gives."""
    data = urllib.parse.urlencode({"data": query}).encode()
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 502, 503, 504) or attempt == attempts:
                raise
            wait = 15 * attempt
            log.warning("Overpass respondeu %s; nova tentativa em %ss", exc.code, wait)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def sync_points(db: Session, points: list[SensitivePointData]) -> tuple[int, int, int]:
    """Upsert the imported points and remove the ones that disappeared from OSM.

    Returns (inserted, updated, removed). The caller commits.
    """
    existing = {(p.osm_type, p.osm_id): p for p in db.scalars(select(SensitivePoint))}
    inserted = updated = 0
    for data in points:
        key = (data.osm_type, data.osm_id)
        row = existing.get(key)
        if row is None:
            db.add(
                SensitivePoint(
                    osm_type=data.osm_type,
                    osm_id=data.osm_id,
                    kind=data.kind,
                    name=data.name,
                    location=make_point(data.lat, data.lon),
                )
            )
            inserted += 1
        else:
            row.kind, row.name = data.kind, data.name
            row.location = make_point(data.lat, data.lon)
            updated += 1
    gone = set(existing) - {(p.osm_type, p.osm_id) for p in points}
    if gone:
        db.execute(
            delete(SensitivePoint).where(
                tuple_(SensitivePoint.osm_type, SensitivePoint.osm_id).in_(list(gone))
            )
        )
    return inserted, updated, len(gone)
