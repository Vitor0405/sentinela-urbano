"""Which sectors and risk types each agent handles (backlog story 6).

No rows for an agent means "everything": scoping is opt-in, so a newly created agent
still sees the whole municipality until the manager narrows it down.
"""

from sqlalchemy import Column, ForeignKey, Integer, Table

from app.db import Base

agent_sectors = Table(
    "agent_sectors",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("sector_id", Integer, ForeignKey("sectors.id", ondelete="CASCADE"), primary_key=True),
)

agent_types = Table(
    "agent_types",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "type_id",
        Integer,
        ForeignKey("occurrence_types.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
