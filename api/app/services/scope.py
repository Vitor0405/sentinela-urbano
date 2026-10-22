"""Agent scope: the sectors and risk types an agent handles (backlog story 6).

Applies to the agent's queue, route and map. Managers always see everything. An agent with
no sectors (or no types) configured is not restricted on that dimension.
"""

from dataclasses import dataclass

from geoalchemy2 import Geometry
from sqlalchemy import Select, cast, delete, exists, func, insert, select
from sqlalchemy.orm import Session

from app.models import Occurrence, Sector, User, UserRole, agent_sectors, agent_types


@dataclass(frozen=True)
class Scope:
    sector_ids: list[int]
    type_ids: list[int]

    @property
    def unrestricted(self) -> bool:
        return not self.sector_ids and not self.type_ids


def get_scope(db: Session, user: User) -> Scope:
    return Scope(
        sector_ids=sorted(
            db.scalars(select(agent_sectors.c.sector_id).where(agent_sectors.c.user_id == user.id))
        ),
        type_ids=sorted(
            db.scalars(select(agent_types.c.type_id).where(agent_types.c.user_id == user.id))
        ),
    )


def apply_scope(stmt: Select, db: Session, user: User) -> Select:
    """Restrict a select over Occurrence to what this agent handles."""
    if user.role != UserRole.AGENT:
        return stmt
    scope = get_scope(db, user)
    if scope.type_ids:
        stmt = stmt.where(Occurrence.type_id.in_(scope.type_ids))
    if scope.sector_ids:
        stmt = stmt.where(
            exists().where(
                Sector.id.in_(scope.sector_ids),
                func.ST_Covers(Sector.geom, cast(Occurrence.location, Geometry)),
            )
        )
    return stmt


def set_scope(db: Session, user: User, sector_ids: list[int], type_ids: list[int]) -> Scope:
    db.execute(delete(agent_sectors).where(agent_sectors.c.user_id == user.id))
    db.execute(delete(agent_types).where(agent_types.c.user_id == user.id))
    for sector_id in sorted(set(sector_ids)):
        db.execute(insert(agent_sectors).values(user_id=user.id, sector_id=sector_id))
    for type_id in sorted(set(type_ids)):
        db.execute(insert(agent_types).values(user_id=user.id, type_id=type_id))
    db.flush()
    return get_scope(db, user)
