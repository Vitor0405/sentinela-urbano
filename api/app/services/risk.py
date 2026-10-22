from decimal import Decimal

from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session

from app.domain.status import QUEUE_STATUSES, RESOLVED_STATUSES
from app.models import Occurrence, RiskSetting, occurrence_risk
from app.seed_data import risk_setting_defaults


def load_settings(db: Session) -> dict[str, Decimal]:
    """Coefficients from `risk_settings`, falling back to the seed defaults."""
    values = risk_setting_defaults()
    values.update({row.key: row.value for row in db.scalars(select(RiskSetting))})
    return values


def deadline_days(db: Session) -> int:
    return int(load_settings(db)["response_deadline_days"])


def detect_chronic(db: Session, occurrence: Occurrence) -> bool:
    """True if a resolved occurrence lies within chronic_radius_m of this one.

    Must run after the occurrence is flushed (it needs the stored geography).
    """
    radius = float(load_settings(db)["chronic_radius_m"])
    other = Occurrence.__table__.alias("other")
    this = Occurrence.__table__.alias("this")
    stmt = (
        select(other.c.id)
        .join(
            this,
            and_(
                this.c.id == occurrence.id,
                func.ST_DWithin(other.c.location, this.c.location, radius),
            ),
        )
        .where(other.c.id != occurrence.id, other.c.status.in_(RESOLVED_STATUSES))
        .limit(1)
    )
    return db.scalar(stmt) is not None


def with_risk(stmt: Select) -> Select:
    """Join the risk view onto a select over Occurrence."""
    return stmt.join(occurrence_risk, occurrence_risk.c.occurrence_id == Occurrence.id)


def queue_query(statuses=QUEUE_STATUSES) -> Select:
    """Agent queue: active occurrences ordered by risk, never by date.

    Unconfirmed reports all stop at the cap, so ties are broken by the raw (uncapped) risk:
    among them the most severe comes first, yet none overtakes a confirmed one above the
    cap. The oldest wins any remaining tie.
    """
    return with_risk(
        select(Occurrence, occurrence_risk).where(Occurrence.status.in_(statuses))
    ).order_by(
        occurrence_risk.c.risk.desc(),
        occurrence_risk.c.raw_risk.desc(),
        Occurrence.created_at.asc(),
    )


def risk_row(db: Session, occurrence_id: int):
    return db.execute(
        select(occurrence_risk).where(occurrence_risk.c.occurrence_id == occurrence_id)
    ).one_or_none()
