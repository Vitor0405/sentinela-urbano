"""Aggregations for the management panel and the LIRAa comparison.

Every per-sector index is normalised by population (per 1,000 inhabitants): raw counts
would favour areas where more people own smartphones (reporting bias), not where the risk is.
Occurrences are matched to sectors spatially (ST_Covers) at query time.
"""

import json
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.status import QUEUE_STATUSES
from app.services.liraa import liraa_class
from app.services.risk import load_settings
from app.services.stats import describe_correlation, spearman

ACTIVE = tuple(s.value for s in QUEUE_STATUSES)


def per_thousand(value: float, population: int) -> float:
    return round(value / population * 1000, 3) if population else 0.0


# --- current index per sector --------------------------------------------------------------

CURRENT_SQL = text(
    """
    SELECT s.id, s.code, s.name, s.population, s.source,
           ST_AsGeoJSON(s.geom, 6) AS geometry,
           COUNT(o.id) AS active_count,
           COALESCE(SUM(r.risk), 0) AS risk_sum
    FROM sectors s
    LEFT JOIN occurrences o
           ON o.status::text = ANY(:active) AND ST_Covers(s.geom, o.location::geometry)
    LEFT JOIN occurrence_risk r ON r.occurrence_id = o.id
    GROUP BY s.id
    ORDER BY s.code
    """
)


def sector_current(db: Session) -> list[dict]:
    rows = db.execute(CURRENT_SQL, {"active": list(ACTIVE)}).mappings().all()
    return [
        {
            "id": r["id"],
            "code": r["code"],
            "name": r["name"],
            "population": r["population"],
            "source": r["source"],
            "geometry": json.loads(r["geometry"]),
            "active_count": r["active_count"],
            "risk_sum": float(r["risk_sum"]),
            "risk_per_1000": per_thousand(float(r["risk_sum"]), r["population"]),
            "active_per_1000": per_thousand(r["active_count"], r["population"]),
        }
        for r in rows
    ]


# --- LIRAa comparison --------------------------------------------------------------------

PERIODS_SQL = text(
    """
    SELECT period, MAX(survey_date) AS survey_date, COUNT(*) AS sectors
    FROM liraa_surveys GROUP BY period ORDER BY MAX(survey_date) DESC, period DESC
    """
)

COMPARISON_SQL = text(
    """
    SELECT s.id, s.code, s.name, s.population, ST_AsGeoJSON(s.geom, 6) AS geometry,
           v.survey_date, v.iip, v.ib,
           COUNT(o.id) AS occurrences,
           COALESCE(SUM(t.weight), 0) AS weight_sum
    FROM sectors s
    LEFT JOIN liraa_surveys v ON v.sector_id = s.id AND v.period = :period
    LEFT JOIN occurrences o
           ON v.id IS NOT NULL
          AND ST_Covers(s.geom, o.location::geometry)
          AND o.created_at >= v.survey_date - make_interval(days => :window)
          AND o.created_at < v.survey_date + 1
    LEFT JOIN occurrence_types t ON t.id = o.type_id
    GROUP BY s.id, v.id
    ORDER BY s.code
    """
)


def liraa_periods(db: Session) -> list[dict]:
    return [
        {"period": r["period"], "survey_date": r["survey_date"], "sectors": r["sectors"]}
        for r in db.execute(PERIODS_SQL).mappings()
    ]


def liraa_comparison(db: Session, period: str | None) -> dict:
    """Community index vs LIRAa IIP per sector, for one survey period.

    Community index = Σ type weights of the occurrences registered in the `liraa_window_days`
    before the survey date, per 1,000 inhabitants (same period as the LIRAa, and weighted by
    how much each type favours the mosquito). Agreement is measured with Spearman's rho.
    """
    periods = liraa_periods(db)
    if period is None and periods:
        period = periods[0]["period"]
    window = int(load_settings(db)["liraa_window_days"])
    rows = db.execute(COMPARISON_SQL, {"period": period or "", "window": window}).mappings().all()
    sectors = []
    for r in rows:
        has_survey = r["iip"] is not None
        sectors.append(
            {
                "id": r["id"],
                "code": r["code"],
                "name": r["name"],
                "population": r["population"],
                "geometry": json.loads(r["geometry"]),
                "survey_date": r["survey_date"],
                "iip": float(r["iip"]) if has_survey else None,
                "ib": float(r["ib"]) if r["ib"] is not None else None,
                "liraa_class": liraa_class(float(r["iip"])) if has_survey else None,
                "occurrences": r["occurrences"] if has_survey else None,
                "community_index": (
                    per_thousand(float(r["weight_sum"]), r["population"]) if has_survey else None
                ),
            }
        )
    paired = [s for s in sectors if s["iip"] is not None]
    rho = spearman([s["community_index"] for s in paired], [s["iip"] for s in paired])
    _rank(paired, "community_index", "community_rank")
    _rank(paired, "iip", "liraa_rank")
    return {
        "period": period,
        "periods": periods,
        "window_days": window,
        "sectors": sectors,
        "paired_sectors": len(paired),
        "spearman_rho": round(rho, 3) if rho is not None else None,
        "interpretation": describe_correlation(rho, len(paired)),
    }


def _rank(items: list[dict], key: str, target: str) -> None:
    """1 = highest value (most risk); ties share the best rank."""
    ordered = sorted(items, key=lambda s: s[key], reverse=True)
    for position, item in enumerate(ordered, start=1):
        previous = ordered[position - 2] if position > 1 else None
        item[target] = previous[target] if previous and previous[key] == item[key] else position


# --- management overview -----------------------------------------------------------------


@dataclass(frozen=True)
class Period:
    start: datetime
    end: datetime  # exclusive


def make_period(date_from: date | None, date_to: date | None, today: date, timezone: str) -> Period:
    """Whole local days [from, to]; defaults to the last 90 days."""
    tz = ZoneInfo(timezone)
    end = (date_to or today) + timedelta(days=1)
    start = date_from or (end - timedelta(days=90))
    return Period(
        datetime.combine(start, datetime.min.time(), tzinfo=tz),
        datetime.combine(end, datetime.min.time(), tzinfo=tz),
    )


def _summary(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "mean_days": None, "median_days": None}
    return {
        "n": len(values),
        "mean_days": round(statistics.fmean(values), 1),
        "median_days": round(statistics.median(values), 1),
    }


def overview(db: Session, period: Period) -> dict:
    params = {"start": period.start, "end": period.end}
    settings = load_settings(db)
    deadline = int(settings["response_deadline_days"])

    by_status = dict(
        db.execute(
            text(
                """SELECT status::text, COUNT(*) FROM occurrences
                   WHERE created_at >= :start AND created_at < :end GROUP BY status"""
            ),
            params,
        ).all()
    )
    by_type = [
        {"code": code, "name": name, "count": count}
        for code, name, count in db.execute(
            text(
                """SELECT t.code, t.name, COUNT(o.id) FROM occurrence_types t
                   LEFT JOIN occurrences o ON o.type_id = t.id
                        AND o.created_at >= :start AND o.created_at < :end
                   GROUP BY t.id ORDER BY COUNT(o.id) DESC, t.sort_order"""
            ),
            params,
        ).all()
    ]
    first_response = [
        float(v)
        for (v,) in db.execute(
            text(
                """SELECT EXTRACT(EPOCH FROM first_response_at - COALESCE(notified_at, created_at))
                          / 86400
                   FROM occurrences
                   WHERE first_response_at IS NOT NULL
                     AND created_at >= :start AND created_at < :end"""
            ),
            params,
        ).all()
    ]
    to_resolution = [
        float(v)
        for (v,) in db.execute(
            text(
                """SELECT EXTRACT(EPOCH FROM MIN(h.created_at) - o.created_at) / 86400
                   FROM occurrences o
                   JOIN occurrence_status_history h
                     ON h.occurrence_id = o.id AND h.to_status = 'resolvida_pelo_agente'
                   WHERE o.created_at >= :start AND o.created_at < :end
                   GROUP BY o.id"""
            ),
            params,
        ).all()
    ]
    waiting, overdue = db.execute(
        text(
            """SELECT COUNT(*),
                      COUNT(*) FILTER (
                          WHERE now() - COALESCE(notified_at, created_at)
                                >= make_interval(days => :deadline))
               FROM occurrences
               WHERE first_response_at IS NULL AND status::text = ANY(:active)"""
        ),
        {"deadline": deadline, "active": list(ACTIVE)},
    ).one()
    transitions = dict(
        db.execute(
            text(
                """SELECT to_status::text, COUNT(*) FROM occurrence_status_history
                   WHERE created_at >= :start AND created_at < :end
                     AND to_status IN ('resolvida_pelo_agente', 'confirmada', 'contestada')
                   GROUP BY to_status"""
            ),
            params,
        ).all()
    )
    closures = transitions.get("resolvida_pelo_agente", 0)

    sectors = sector_current(db)
    for s in sectors:
        s.pop("geometry")
    return {
        "period": {"start": period.start.date(), "end": (period.end - timedelta(days=1)).date()},
        "registered": sum(by_status.values()),
        "by_status": by_status,
        "by_type": by_type,
        "time_to_first_response": _summary(first_response),
        "time_to_resolution": _summary(to_resolution),
        "no_response": {"waiting": waiting, "overdue": overdue, "deadline_days": deadline},
        "resolution": {
            "closures": closures,
            "confirmed": transitions.get("confirmada", 0),
            "contested": transitions.get("contestada", 0),
            "confirmed_rate": (
                round(transitions.get("confirmada", 0) / closures, 4) if closures else None
            ),
            "contested_rate": (
                round(transitions.get("contestada", 0) / closures, 4) if closures else None
            ),
        },
        "sectors": sorted(sectors, key=lambda s: s["risk_per_1000"], reverse=True),
    }
