"""The whole generation pipeline, in dependency order."""
from __future__ import annotations

from .config import Config
from .events import EventLog
from .ledger import build_ledger
from .master import build_master
from .payments import build_payments
from .refunds import build_refunds
from .scholarships import add_waivers, build_scholarships
from .schema import TABLES
from .transactions import build_enrollments_and_invoices, recompute_invoice_totals


def build_all(cfg: Config) -> dict:
    """Generate the clean baseline: every table, parents before children, no anomalies."""
    master = build_master(cfg)
    log = EventLog()
    enrollments, invoices, lines = build_enrollments_and_invoices(cfg, master, log)
    scholarships = build_scholarships(cfg, master, invoices, lines, log)
    add_waivers(cfg, invoices, lines)
    recompute_invoice_totals(invoices, lines)
    payments, allocations = build_payments(cfg, invoices, lines, log)
    refunds = build_refunds(cfg, master, enrollments, invoices, lines, payments, allocations, log)
    tables = {
        **master,
        "enrollment": enrollments,
        "invoice": invoices,
        "scholarship": scholarships,
        "invoice_line": lines,
        "payment": payments,
        "payment_allocation": allocations,
        "refund": refunds,
        "status_event": log.rows(),
    }
    tables["ledger_entry"] = build_ledger(tables)
    return {name: tables[name] for name in TABLES if name in tables}


def build_dataset(cfg: Config, anomalies: bool = True):
    """Clean baseline, then (optionally) labelled anomalies. Returns (tables, ground_truth_rows)."""
    from .anomalies import inject_anomalies

    tables = build_all(cfg)
    truth = inject_anomalies(cfg, tables) if anomalies else []
    return tables, truth
