"""The whole generation pipeline, in dependency order."""
from __future__ import annotations

from .config import Config
from .events import EventLog
from .master import build_master
from .payments import build_payments
from .scholarships import add_waivers, build_scholarships
from .schema import TABLES
from .transactions import build_enrollments_and_invoices, recompute_invoice_totals


def build_all(cfg: Config) -> dict:
    """Generate every table built so far, parents before children."""
    master = build_master(cfg)
    log = EventLog()
    enrollments, invoices, lines = build_enrollments_and_invoices(cfg, master, log)
    scholarships = build_scholarships(cfg, master, invoices, lines, log)
    add_waivers(cfg, invoices, lines)
    recompute_invoice_totals(invoices, lines)
    payments, allocations = build_payments(cfg, invoices, lines, log)
    tables = {
        **master,
        "enrollment": enrollments,
        "invoice": invoices,
        "scholarship": scholarships,
        "invoice_line": lines,
        "payment": payments,
        "payment_allocation": allocations,
        "status_event": log.rows(),
    }
    return {name: tables[name] for name in TABLES if name in tables}
