"""Deterministic invoice validation against extracted contract terms.

No model is involved here: every number is computed in Python so that a
finding can be reproduced and explained line by line.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, List

from .schema import ContractTerms, Finding, InvoiceLine

AMOUNT_TOLERANCE = 0.005  # 0.5 % of the expected milestone amount


def _norm(s: str | None) -> str:
    return " ".join((s or "").lower().split())


def _parse_date(s: str | None) -> date | None:
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def validate_invoices(terms: ContractTerms, invoices: Iterable[InvoiceLine]) -> List[Finding]:
    invoices = list(invoices)
    findings: List[Finding] = []

    def add(code: str, severity: str, inv: InvoiceLine | None, msg: str) -> None:
        findings.append(Finding(code=code, severity=severity, invoice_number=inv.invoice_number if inv else None, message=msg))

    if terms.total_contract_value is None:
        add("V00", "warning", None, "Contract total value was not extracted; amount checks skipped.")

    milestones = {_norm(m.name): m for m in terms.milestones}
    seen_numbers: dict[str, InvoiceLine] = {}
    seen_milestones: dict[str, InvoiceLine] = {}
    billed_total = 0.0

    for inv in invoices:
        # V01 contract number
        if terms.contract_number and _norm(inv.contract_number) != _norm(terms.contract_number):
            add("V01", "error", inv, f"Invoice references contract {inv.contract_number!r}; extracted contract number is {terms.contract_number!r}.")
        # V02 currency
        if terms.currency and inv.currency.upper() != terms.currency.upper():
            add("V02", "error", inv, f"Invoice currency {inv.currency} differs from contract currency {terms.currency}.")
        # V03 duplicate invoice number
        if inv.invoice_number in seen_numbers:
            add("V03", "error", inv, f"Duplicate invoice number {inv.invoice_number} (first seen with amount {seen_numbers[inv.invoice_number].amount:,.2f}).")
        seen_numbers.setdefault(inv.invoice_number, inv)
        # V04/V05/V06 milestone checks
        key = _norm(inv.milestone)
        if inv.milestone:
            m = milestones.get(key)
            if m is None:
                add("V04", "error", inv, f"Milestone {inv.milestone!r} is not in the contract's payment schedule ({', '.join(x.name for x in terms.milestones) or 'none'}).")
            else:
                if key in seen_milestones:
                    add("V05", "error", inv, f"Milestone {inv.milestone!r} was already billed on invoice {seen_milestones[key].invoice_number}.")
                seen_milestones.setdefault(key, inv)
                if terms.total_contract_value is not None:
                    expected = terms.total_contract_value * m.percent_of_total / 100.0
                    if abs(inv.amount - expected) > AMOUNT_TOLERANCE * expected:
                        add("V06", "error", inv, f"Amount {inv.amount:,.2f} does not match {m.percent_of_total:g}% of {terms.total_contract_value:,.2f} = {expected:,.2f}.")
        elif terms.milestones:
            add("V04", "warning", inv, "Invoice has no milestone but the contract bills by milestone.")
        # V07 due date vs payment terms
        inv_date, due = _parse_date(inv.invoice_date), _parse_date(inv.due_date)
        if terms.payment_terms_days is not None and inv_date and due:
            expected_due = inv_date + timedelta(days=terms.payment_terms_days)
            if due != expected_due:
                add("V07", "warning", inv, f"Due date {due} is not invoice date + net {terms.payment_terms_days} days ({expected_due}).")
        billed_total += inv.amount

    # V08 over-billing
    if terms.total_contract_value is not None and billed_total > terms.total_contract_value * (1 + AMOUNT_TOLERANCE):
        add("V08", "error", None, f"Cumulative billed {billed_total:,.2f} exceeds contract value {terms.total_contract_value:,.2f}.")
    return findings


def render_report(terms: ContractTerms, invoices: List[InvoiceLine], findings: List[Finding]) -> str:
    lines = [f"# Billing check: contract {terms.contract_number or '(unknown)'}", ""]
    lines.append(f"- Supplier: {terms.supplier or '—'}  ·  Customer: {terms.customer or '—'}")
    tcv = f"{terms.total_contract_value:,.2f} {terms.currency or ''}" if terms.total_contract_value is not None else "not stated"
    lines.append(f"- Contract value: {tcv}  ·  Payment terms: {'net ' + str(terms.payment_terms_days) if terms.payment_terms_days is not None else 'not stated'}")
    if terms.milestones:
        lines.append("- Milestones: " + "; ".join(f"{m.name} {m.percent_of_total:g}%" for m in terms.milestones))
    lines.append(f"- Invoices checked: {len(invoices)}  ·  Findings: {sum(f.severity == 'error' for f in findings)} error(s), {sum(f.severity == 'warning' for f in findings)} warning(s)")
    lines.append("")
    if not findings:
        lines.append("No issues found.")
    else:
        lines += ["| Code | Severity | Invoice | Finding |", "|---|---|---|---|"]
        lines += [f"| {f.code} | {f.severity} | {f.invoice_number or '—'} | {f.message} |" for f in findings]
    return "\n".join(lines) + "\n"
