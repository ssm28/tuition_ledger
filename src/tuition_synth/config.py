"""Run configuration: seed, scale, fixed as-of date, terms and base volumes.

Everything that influences generated output lives here or in the seed, so a
run is fully described by (seed, scale). No wall-clock time is ever used.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

DEFAULT_SEED = 20261022

# Fixed "today" for all date-dependent derivations (overdue status, late fees).
AS_OF_DATE = date(2026, 12, 31)

# Full-scale volumes required by the problem statement.
BASE_VOLUMES = {
    "students": 10_000,
    "programs": 20,  # fixed: not scaled, so starter data still spans 20 programs
    "invoices": 30_000,
    "scholarships": 15_000,
    "payments": 50_000,
}
_FIXED_VOLUMES = {"programs"}

# (term_id, label, start_date, end_date). All in 2026 so invoice IDs
# (INV-<student-id>-2026-NNNNNN) carry a consistent year.
TERMS = (
    ("TERM-2026-SPRING", "Spring 2026", date(2026, 1, 12), date(2026, 5, 15)),
    ("TERM-2026-SUMMER", "Summer 2026", date(2026, 6, 1), date(2026, 7, 31)),
    ("TERM-2026-FALL", "Fall 2026", date(2026, 8, 17), date(2026, 12, 18)),
)


@dataclass(frozen=True)
class Config:
    seed: int = DEFAULT_SEED
    scale: float = 1.0
    as_of: date = AS_OF_DATE

    def __post_init__(self) -> None:
        if self.scale <= 0:
            raise ValueError("scale must be > 0")

    def volume(self, name: str) -> int:
        """Row target for a driver table at this scale (at least 1)."""
        base = BASE_VOLUMES[name]
        if name in _FIXED_VOLUMES:
            return base
        return max(1, round(base * self.scale))
