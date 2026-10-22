"""Occurrence status flow.

    aberta ─► em_atendimento ─► resolvida_pelo_agente ─► confirmada
       │                ▲               │
       └────────────────┼───────────────┴─► contestada ─► (back to the agent's queue)
                        └─────────────────────────────────┘

Staff (agent or manager) move the occurrence through the queue and close it with a
mandatory photo; only the resident who reported it answers "foi realmente resolvido?".
"""

from enum import StrEnum

from app.models import OccurrenceStatus as S


class Actor(StrEnum):
    STAFF = "staff"
    REPORTER = "reporter"


TRANSITIONS: dict[tuple[S, S], Actor] = {
    (S.OPEN, S.IN_PROGRESS): Actor.STAFF,
    (S.CONTESTED, S.IN_PROGRESS): Actor.STAFF,
    # The agent may close straight from the queue when the visit solves it on the spot.
    (S.OPEN, S.RESOLVED_BY_AGENT): Actor.STAFF,
    (S.IN_PROGRESS, S.RESOLVED_BY_AGENT): Actor.STAFF,
    (S.CONTESTED, S.RESOLVED_BY_AGENT): Actor.STAFF,
    (S.RESOLVED_BY_AGENT, S.CONFIRMED): Actor.REPORTER,
    (S.RESOLVED_BY_AGENT, S.CONTESTED): Actor.REPORTER,
}

# Statuses that appear in the agent's queue.
QUEUE_STATUSES = (S.OPEN, S.IN_PROGRESS, S.CONTESTED)
# Statuses that count as "resolved at this spot" for recurrence and chronic points.
RESOLVED_STATUSES = (S.RESOLVED_BY_AGENT, S.CONFIRMED)


class TransitionError(ValueError):
    """Raised with a pt-BR message suitable for the API response."""


def check_transition(current: S, target: S, actor: Actor) -> None:
    allowed = TRANSITIONS.get((current, target))
    if allowed is None:
        raise TransitionError(f"Não é possível passar de '{current.value}' para '{target.value}'.")
    if allowed != actor:
        who = "a equipe de saúde" if allowed == Actor.STAFF else "quem registrou a ocorrência"
        raise TransitionError(f"Somente {who} pode fazer esta mudança.")
