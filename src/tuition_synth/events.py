"""Collects lifecycle transitions and turns them into numbered status_event rows.

Each stage of the pipeline calls `add(...)` when something changes state.
At the very end `rows()` sorts everything by date and numbers it, so event IDs
increase with time and the log is never edited afterwards.
"""
from __future__ import annotations

from datetime import date

from . import ids


class EventLog:
    def __init__(self) -> None:
        self._items: list[tuple] = []
        self._index: dict | None = None

    def add(self, entity_type: str, entity_id: str, from_status: str | None,
            to_status: str, event_date: date) -> None:
        seq = len(self._items)  # keeps insertion order for same-day events
        self._items.append((event_date, entity_type, entity_id, seq, from_status, to_status))
        self._index = None

    def date_of(self, entity_type: str, entity_id: str, to_status: str):
        """Date on which the entity first moved to `to_status` (None if it never did)."""
        if self._index is None:
            self._index = {}
            for when, etype, eid, _seq, _frm, to in self._items:
                self._index.setdefault((etype, eid, to), when)
        return self._index.get((entity_type, entity_id, to_status))

    def rows(self) -> list[dict]:
        ordered = sorted(self._items, key=lambda item: item[:4])
        return [
            {
                "event_id": ids.status_event_id(i),
                "entity_type": etype,
                "entity_id": eid,
                "from_status": frm,
                "to_status": to,
                "event_date": when,
            }
            for i, (when, etype, eid, _seq, frm, to) in enumerate(ordered, start=1)
        ]


def renumber(rows: list[dict]) -> list[dict]:
    """Re-sort status events by date and give them fresh sequential IDs.

    Used after anomaly injection added events, so IDs still increase with time.
    The previous position breaks ties, so same-day events keep their order.
    """
    ordered = sorted(enumerate(rows), key=lambda t: (t[1]["event_date"], t[1]["entity_type"], t[1]["entity_id"], t[0]))
    return [dict(row, event_id=ids.status_event_id(i)) for i, (_old, row) in enumerate(ordered, start=1)]
