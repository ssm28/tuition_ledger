"""Payments, allocations, late fees and derived invoice statuses.

Each non-cancelled invoice is given a payment behaviour; everything else
(late fee, installment amounts and dates, allocations, statuses) follows from it:

    FULL_ON_TIME  paid in full on or before the due date, in 1-4 installments
    OVERPAID      like FULL_ON_TIME but with extra paid (credit on account)
    FULL_LATE     last installment arrives after the grace period -> late fee, paid with it
    PARTIAL       only part of the amount is ever paid -> late fee, stays unpaid in part
    UNPAID        nothing paid -> late fee, OVERDUE

The total number of payments is steered to exactly `volume("payments")`.
Assumes the as-of date is after every invoice's grace period plus 45 days
(true for the default configuration).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal

from . import ids
from .config import Config
from .events import EventLog
from .master import money, rng_for
from .rules import LATE_FEE_AMOUNT, grace_end, late_fee_date, line_net_dues
from .transactions import recompute_invoice_totals

BEHAVIORS = ("UNPAID", "PARTIAL", "FULL_LATE", "OVERPAID", "FULL_ON_TIME")
BEHAVIOR_WEIGHTS = (4, 8, 10, 5, 73)
INSTALLMENT_CHOICES = (1, 2, 3, 4)
INSTALLMENT_WEIGHTS = (50, 30, 15, 5)
PARTIAL_SHARE = (0.2, 0.8)               # share of the amount a partial payer pays
OVERPAY_EXTRAS = (200, 500, 1000, 2500, 5000)
LATE_PAY_DAYS = (1, 45)                  # late payers pay this long after the grace period
METHODS = ("UPI", "CARD", "NET_BANKING", "BANK_TRANSFER", "CASH")
METHOD_WEIGHTS = (45, 15, 20, 12, 8)


def _plan_counts(rng, payers: int, target: int) -> list:
    """Installments per paying invoice; nudged until the total equals `target`."""
    counts = rng.choices(INSTALLMENT_CHOICES, weights=INSTALLMENT_WEIGHTS, k=payers)
    diff = target - sum(counts)
    for _ in range(50 * payers + 100):
        if diff == 0 or not payers:
            break
        i = rng.randrange(payers)
        if diff > 0 and counts[i] < max(INSTALLMENT_CHOICES):
            counts[i] += 1
            diff -= 1
        elif diff < 0 and counts[i] > 1:
            counts[i] -= 1
            diff += 1
    return counts


def _split(rng, total: Decimal, k: int, limit: Decimal | None = None) -> list:
    """Split `total` into k positive parts. The first k-1 are multiples of 100
    and together stay below `limit` (default: total); the last takes the rest."""
    if k == 1:
        return [total]
    hundreds = int((total if limit is None else limit) // 100)
    cuts = sorted(rng.sample(range(1, hundreds), k - 1))
    parts, prev = [], 0
    for c in cuts:
        parts.append(money((c - prev) * 100))
        prev = c
    parts.append(total - money(prev * 100))
    return parts


def _dates(rng, lo, hi, k: int) -> list:
    span = (hi - lo).days
    return sorted(lo + timedelta(days=rng.randint(0, span)) for _ in range(k))


def _status(paid: Decimal, net: Decimal, on, due) -> str:
    if paid >= net:
        return "PAID"
    if paid > 0:
        return "PARTIALLY_PAID"
    return "OVERDUE" if on > due else "ISSUED"


def build_payments(cfg: Config, invoices: list, lines: list, log: EventLog):
    """Create payments and allocations; add late-fee lines; set invoice status and totals."""
    rng = rng_for(cfg, "payment")
    lines_by_inv = defaultdict(list)
    for ln in lines:
        lines_by_inv[ln["invoice_id"]].append(ln)
    line_count = Counter({k: len(v) for k, v in lines_by_inv.items()})

    active = [inv for inv in invoices if inv["status"] != "CANCELLED"]
    behaviors = rng.choices(BEHAVIORS, weights=BEHAVIOR_WEIGHTS, k=len(active))
    payer_idx = [i for i, b in enumerate(behaviors) if b != "UNPAID"]
    installments = dict(zip(payer_idx, _plan_counts(rng, len(payer_idx), cfg.volume("payments"))))

    drafts = []        # (date, invoice_id, part, student_id, amount)
    base_net = {}      # invoice_id -> amount due before any late fee
    has_fee = {}
    for i, inv in enumerate(active):
        iid, behavior = inv["invoice_id"], behaviors[i]
        net0 = sum((ln["amount"] for ln in lines_by_inv[iid]), Decimal(0))
        base_net[iid] = net0
        issue, due, g_end, fee_day = inv["issue_date"], inv["due_date"], grace_end(inv), late_fee_date(inv)

        has_fee[iid] = behavior in ("UNPAID", "PARTIAL", "FULL_LATE")
        if has_fee[iid]:
            line_count[iid] += 1
            fee_line = {
                "invoice_line_id": ids.invoice_line_id(iid, line_count[iid]),
                "invoice_id": iid, "line_type": "LATE_FEE", "fee_schedule_id": None,
                "scholarship_id": None, "description": "Late payment fee",
                "amount": LATE_FEE_AMOUNT, "line_date": fee_day,
            }
            lines.append(fee_line)
            lines_by_inv[iid].append(fee_line)

        if behavior == "UNPAID":
            continue
        k = installments[i]
        if behavior == "FULL_ON_TIME":
            amounts, dates = _split(rng, net0, k), _dates(rng, issue, due, k)
        elif behavior == "OVERPAID":
            total = net0 + money(rng.choice(OVERPAY_EXTRAS))
            amounts, dates = _split(rng, total, k), _dates(rng, issue, due, k)
        elif behavior == "PARTIAL":
            hundreds = int(net0 * Decimal(str(round(rng.uniform(*PARTIAL_SHARE), 4))) // 100)
            hundreds = min(max(hundreds, k), int(net0 // 100) - 1)
            amounts, dates = _split(rng, money(hundreds * 100), k), _dates(rng, issue, g_end, k)
        else:  # FULL_LATE: earlier installments on time, final one after the grace period
            amounts = _split(rng, net0 + LATE_FEE_AMOUNT, k, limit=net0)
            late_day = g_end + timedelta(days=rng.randint(*LATE_PAY_DAYS))
            dates = _dates(rng, issue, due, k - 1) + [late_day]
        for part, (when, amount) in enumerate(zip(dates, amounts), start=1):
            drafts.append((when, iid, part, inv["student_id"], amount))

    # --- number payments in date order
    drafts.sort(key=lambda d: d[:3])
    method_rng = rng_for(cfg, "payment_method")
    payments, by_invoice = [], defaultdict(list)
    for n, (when, iid, _part, student, amount) in enumerate(drafts, start=1):
        method = method_rng.choices(METHODS, weights=METHOD_WEIGHTS, k=1)[0]
        pay_id = ids.payment_id(when.year, n)
        row = {
            "payment_id": pay_id, "student_id": student, "payment_date": when,
            "amount": amount, "method": method,
            "reference": f"{method[:3]}-{n:07d}-{method_rng.randint(100, 999)}",
            "status": "POSTED",
        }
        payments.append(row)
        by_invoice[iid].append(row)
        log.add("payment", pay_id, None, "POSTED", when)

    # --- allocate each payment to the invoice's lines, in line order
    allocations = []
    for iid, pays in by_invoice.items():
        room = dict(line_net_dues(lines_by_inv[iid]))
        for pay in pays:
            left, seq = pay["amount"], 0
            for ln in lines_by_inv[iid]:
                lid = ln["invoice_line_id"]
                if left <= 0:
                    break
                if lid not in room or room[lid] <= 0 or ln["line_date"] > pay["payment_date"]:
                    continue
                take = min(left, room[lid])
                seq += 1
                allocations.append({
                    "allocation_id": ids.allocation_id(pay["payment_id"], seq),
                    "payment_id": pay["payment_id"], "invoice_line_id": lid,
                    "amount": take, "allocated_on": pay["payment_date"],
                })
                room[lid] -= take
                left -= take
            # anything left over is an overpayment: it stays unallocated (credit on account)

    # --- walk each invoice's timeline to derive status changes
    for inv in active:
        iid = inv["invoice_id"]
        events = [(inv["due_date"] + timedelta(days=1), 0, "due", Decimal(0))]
        if has_fee[iid]:
            events.append((late_fee_date(inv), 1, "fee", LATE_FEE_AMOUNT))
        events += [(p["payment_date"], 2, "pay", p["amount"]) for p in by_invoice.get(iid, [])]
        net, paid, status = base_net[iid], Decimal(0), "ISSUED"
        for when, _order, kind, amount in sorted(events, key=lambda e: e[:2]):
            if when > cfg.as_of:
                continue
            net += amount if kind == "fee" else 0
            paid += amount if kind == "pay" else 0
            new = _status(paid, net, when, inv["due_date"])
            if new != status:
                log.add("invoice", iid, status, new, when)
                status = new
        inv["status"] = status

    recompute_invoice_totals(invoices, lines)
    return payments, allocations
