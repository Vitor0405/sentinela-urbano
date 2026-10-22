"""The public "X dias sem resposta" counter (improvement 4).

The clock starts when the prefecture was e-mailed (or at registration, if the e-mail has
not gone out yet: the report is public from that moment) and stops at the first action of
an agent or manager. Past `response_deadline_days`, the silence is overdue and the reporter
may generate the document for the municipal ombudsman (ouvidoria).
"""

from dataclasses import dataclass
from datetime import datetime

DAY_SECONDS = 86_400


@dataclass(frozen=True)
class ResponseClock:
    deadline_days: int
    # Whole days waiting for the prefecture; None once it has responded.
    days_without_response: int | None
    overdue: bool
    days_left: int | None
    # How long the prefecture took, when it did respond.
    responded_after_days: int | None


def _whole_days(start: datetime, end: datetime) -> int:
    return max(0, int((end - start).total_seconds() // DAY_SECONDS))


def response_clock(
    *,
    created_at: datetime,
    notified_at: datetime | None,
    first_response_at: datetime | None,
    deadline_days: int,
    now: datetime,
) -> ResponseClock:
    start = notified_at or created_at
    if first_response_at is not None:
        return ResponseClock(
            deadline_days=deadline_days,
            days_without_response=None,
            overdue=False,
            days_left=None,
            responded_after_days=_whole_days(start, first_response_at),
        )
    days = _whole_days(start, now)
    return ResponseClock(
        deadline_days=deadline_days,
        days_without_response=days,
        overdue=days >= deadline_days,
        days_left=max(0, deadline_days - days),
        responded_after_days=None,
    )
