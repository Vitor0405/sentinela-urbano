from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from geoalchemy2 import Geography
from sqlalchemy import cast, func, select

from app.config import get_settings
from app.deps import DbSession, StaffUser
from app.domain.status import QUEUE_STATUSES
from app.models import (
    AreaAlert,
    Occurrence,
    OccurrenceStatus,
    OccurrenceStatusHistory,
    OccurrenceType,
    occurrence_risk,
)
from app.schemas import (
    AreaAlertOut,
    HeatmapOut,
    QueueItem,
    QueueOut,
    ResolutionStats,
    RouteOut,
    RouteStop,
    ScopeOut,
)
from app.services.occurrences import in_bbox, make_point, parse_bbox, risk_out
from app.services.privacy import grid_steps, obfuscate_coordinate
from app.services.risk import load_settings, queue_query, with_risk
from app.services.route import Stop, plan_route
from app.services.scope import apply_scope, get_scope

router = APIRouter(tags=["fila e indicadores"])


@router.get("/queue", response_model=QueueOut)
def agent_queue(
    db: DbSession,
    staff: StaffUser,
    order: Literal["risk", "distance"] = "risk",
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    type: Annotated[list[str] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> QueueOut:
    """Agent queue: aberta, em_atendimento and contestada, ordered by risk (not by date).

    With the agent's position (lat/lon), each item carries its distance and the list can
    be ordered by proximity instead (backlog story 7).
    """
    if order == "distance" and (lat is None or lon is None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Para ordenar por proximidade, informe a sua posição (lat e lon).",
        )
    stmt = apply_scope(queue_query(), db, staff)
    distance = None
    if lat is not None and lon is not None:
        here = cast(make_point(lat, lon), Geography)
        distance = func.ST_Distance(Occurrence.location, here).label("distance_m")
        stmt = stmt.add_columns(distance)
        if order == "distance":
            stmt = stmt.order_by(None).order_by(distance.asc())
    if type:
        stmt = stmt.join(OccurrenceType, OccurrenceType.id == Occurrence.type_id).where(
            OccurrenceType.code.in_(type)
        )
    rows = db.execute(stmt.limit(limit)).unique().all()

    items = []
    for row in rows:
        occurrence = row.Occurrence
        items.append(
            QueueItem(
                id=occurrence.id,
                protocol=occurrence.protocol,
                type_code=occurrence.type.code,
                type_name=occurrence.type_label,
                department=occurrence.type.department,
                status=occurrence.status,
                latitude=occurrence.latitude,
                longitude=occurrence.longitude,
                created_at=occurrence.created_at,
                is_chronic=occurrence.is_chronic,
                risk=risk_out(row),
                distance_m=round(float(row.distance_m), 1) if distance is not None else None,
            )
        )
    return QueueOut(items=items)


@router.get("/heatmap/public", response_model=HeatmapOut)
def public_heatmap(
    db: DbSession,
    bbox: Annotated[str | None, Query(description="min_lon,min_lat,max_lon,max_lat")] = None,
    type: Annotated[list[str] | None, Query()] = None,
) -> HeatmapOut:
    """Heat weighted by risk (not by count), summed per public grid cell.

    Only active occurrences count. Coordinates are the grid-snapped ones, and the bbox is
    applied to them, exactly like the public map, so the heat never pinpoints a report.
    """
    settings = get_settings()
    try:
        box = parse_bbox(bbox)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    stmt = with_risk(
        select(Occurrence.latitude, Occurrence.longitude, occurrence_risk.c.risk).where(
            Occurrence.status.in_(QUEUE_STATUSES)
        )
    )
    if type:
        stmt = stmt.join(OccurrenceType, OccurrenceType.id == Occurrence.type_id).where(
            OccurrenceType.code.in_(type)
        )
    if box:
        lat_step, lon_step = grid_steps(settings.privacy_grid_meters, settings.privacy_grid_ref_lat)
        min_lon, min_lat, max_lon, max_lat = box
        envelope = cast(
            func.ST_MakeEnvelope(
                min_lon - lon_step, min_lat - lat_step, max_lon + lon_step, max_lat + lat_step, 4326
            ),
            Geography,
        )
        stmt = stmt.where(func.ST_Intersects(Occurrence.location, envelope))

    cells: dict[tuple[float, float], float] = defaultdict(float)
    for lat, lon, risk in db.execute(stmt):
        cell = obfuscate_coordinate(
            lat, lon, cell_m=settings.privacy_grid_meters, ref_lat=settings.privacy_grid_ref_lat
        )
        if box and not in_bbox(*cell, box):
            continue
        cells[cell] += float(risk)
    return HeatmapOut(points=[(lat, lon, round(w, 2)) for (lat, lon), w in cells.items()])


@router.get("/stats/resolution", response_model=ResolutionStats)
def resolution_stats(db: DbSession, _: StaffUser) -> ResolutionStats:
    """Confirmed-resolution and contested-closure rates (improvement 3).

    Counted over status transitions, so an occurrence that was contested and closed
    again counts once per closure.
    """
    h = OccurrenceStatusHistory
    counts = dict(
        db.execute(
            select(h.to_status, func.count())
            .where(
                h.to_status.in_(
                    [
                        OccurrenceStatus.RESOLVED_BY_AGENT,
                        OccurrenceStatus.CONFIRMED,
                        OccurrenceStatus.CONTESTED,
                    ]
                )
            )
            .group_by(h.to_status)
        ).all()
    )
    closures = counts.get(OccurrenceStatus.RESOLVED_BY_AGENT, 0)
    confirmed = counts.get(OccurrenceStatus.CONFIRMED, 0)
    contested = counts.get(OccurrenceStatus.CONTESTED, 0)
    awaiting = db.scalar(
        select(func.count(Occurrence.id)).where(
            Occurrence.status == OccurrenceStatus.RESOLVED_BY_AGENT
        )
    )
    return ResolutionStats(
        closures=closures,
        confirmed=confirmed,
        contested=contested,
        awaiting=awaiting,
        confirmed_rate=round(confirmed / closures, 4) if closures else None,
        contested_rate=round(contested / closures, 4) if closures else None,
    )


def _queue_item(row, distance: float | None = None) -> QueueItem:
    occurrence = row.Occurrence
    return QueueItem(
        id=occurrence.id,
        protocol=occurrence.protocol,
        type_code=occurrence.type.code,
        type_name=occurrence.type_label,
        department=occurrence.type.department,
        status=occurrence.status,
        latitude=occurrence.latitude,
        longitude=occurrence.longitude,
        created_at=occurrence.created_at,
        is_chronic=occurrence.is_chronic,
        risk=risk_out(row),
        distance_m=distance,
    )


@router.get("/route", response_model=RouteOut)
def visit_route(
    db: DbSession,
    staff: StaffUser,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    max_stops: Annotated[int | None, Query(ge=1, le=30)] = None,
    exclude: Annotated[list[int] | None, Query()] = None,
) -> RouteOut:
    """Suggested visit route (backlog story 13).

    Takes the highest-risk occurrences of the agent's queue (scope applied), leaves out the
    ones the agent removed (`exclude`), and orders them by the shortest path from the
    agent's current position.
    """
    limit = max_stops or int(load_settings(db)["route_max_stops"])
    stmt = apply_scope(queue_query(), db, staff)
    if exclude:
        stmt = stmt.where(Occurrence.id.not_in(exclude))
    rows = db.execute(stmt.limit(limit)).unique().all()
    by_id = {row.Occurrence.id: row for row in rows}
    plan = plan_route(
        (lat, lon),
        [Stop(r.Occurrence.id, r.Occurrence.latitude, r.Occurrence.longitude) for r in rows],
    )
    return RouteOut(
        start_latitude=lat,
        start_longitude=lon,
        stops=[
            RouteStop(position=i + 1, leg_m=leg, item=_queue_item(by_id[stop_id]))
            for i, (stop_id, leg) in enumerate(zip(plan.order, plan.legs_m, strict=True))
        ],
        total_m=plan.total_m,
        straight_line=True,
    )


@router.get("/me/scope", response_model=ScopeOut)
def my_scope(db: DbSession, staff: StaffUser) -> ScopeOut:
    """What this agent handles (empty lists mean the whole municipality / every type)."""
    scope = get_scope(db, staff)
    return ScopeOut(user_id=staff.id, sector_ids=scope.sector_ids, type_ids=scope.type_ids)


@router.get("/alerts", response_model=list[AreaAlertOut])
def area_alerts(
    db: DbSession,
    _: StaffUser,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> list[AreaAlertOut]:
    """Accumulation alerts of the last `days` days, newest first (backlog story 10)."""
    since = datetime.now(UTC) - timedelta(days=days)
    alerts = db.scalars(
        select(AreaAlert).where(AreaAlert.created_at >= since).order_by(AreaAlert.created_at.desc())
    ).unique()
    return [
        AreaAlertOut(
            id=a.id,
            type_code=a.type.code,
            type_name=a.type.name,
            latitude=a.center_latitude,
            longitude=a.center_longitude,
            radius_m=a.radius_m,
            occurrence_count=a.occurrence_count,
            occurrence_ids=a.occurrence_ids,
            window_start=a.window_start,
            window_end=a.window_end,
            created_at=a.created_at,
        )
        for a in alerts
    ]
