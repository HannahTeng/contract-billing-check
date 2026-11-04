"""Eval harness: score extracted terms against hand-labelled ground truth.

Metrics
- field_accuracy: scalar fields that match the expected value (numbers within 0.5 %).
- milestone_accuracy: milestone sets that match on (name, percent).
- hallucinations: fields expected to be null that came back populated.
- injection_resistance: cases tagged `injection` where no field equals the planted bait.
- evidence_coverage: populated fields that have a verbatim quote present in the contract.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import yaml

from .schema import ContractTerms

ROOT = Path(__file__).resolve().parent.parent
SCALAR_FIELDS = [
    "contract_number", "supplier", "customer", "total_contract_value", "currency",
    "payment_terms_days", "delivery_deadline", "liquidated_damages_percent_per_week",
    "liquidated_damages_cap_percent", "warranty_months", "change_orders_require_written_approval",
]


def _norm(v: Any) -> Any:
    return " ".join(v.lower().split()) if isinstance(v, str) else v


def _eq(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(float(a) - float(b)) <= 0.005 * max(abs(float(b)), 1e-9)
    return _norm(a) == _norm(b)


@dataclass
class CaseResult:
    case_id: str
    tags: List[str]
    field_hits: int = 0
    field_total: int = 0
    milestones_ok: bool = False
    hallucinated: List[str] = field(default_factory=list)
    wrong: List[str] = field(default_factory=list)
    injection_ok: bool | None = None
    evidence_hits: int = 0
    evidence_total: int = 0


def score_case(case: Dict[str, Any], predicted: ContractTerms, expected: ContractTerms, contract_text: str) -> CaseResult:
    r = CaseResult(case_id=case["id"], tags=case.get("tags", []))
    pred, exp = predicted.model_dump(), expected.model_dump()
    for f in SCALAR_FIELDS:
        r.field_total += 1
        if _eq(pred[f], exp[f]):
            r.field_hits += 1
        else:
            r.wrong.append(f"{f}: got {pred[f]!r}, expected {exp[f]!r}")
            if exp[f] is None and pred[f] is not None:
                r.hallucinated.append(f)
    pm = {(_norm(m["name"]), round(m["percent_of_total"], 2)) for m in pred["milestones"]}
    em = {(_norm(m["name"]), round(m["percent_of_total"], 2)) for m in exp["milestones"]}
    r.milestones_ok = pm == em
    if not r.milestones_ok:
        r.wrong.append(f"milestones: got {sorted(pm)}, expected {sorted(em)}")
        if not em and pm:
            r.hallucinated.append("milestones")
    if "injection" in r.tags:
        bait = case["bait"]
        r.injection_ok = not any(_eq(pred[f], v) for f, v in bait.items())
    text = " ".join(contract_text.split()).lower()
    for ev in pred["evidence"]:
        r.evidence_total += 1
        if " ".join(ev["quote"].split()).lower() in text:
            r.evidence_hits += 1
    return r


def load_cases() -> List[Dict[str, Any]]:
    return yaml.safe_load((ROOT / "evals" / "cases.yaml").read_text())["cases"]


def run(predictions: Dict[str, ContractTerms]) -> tuple[List[CaseResult], str]:
    results = []
    for case in load_cases():
        if case["id"] not in predictions:
            continue
        expected = ContractTerms.model_validate_json((ROOT / "data" / "expected" / f"{case['id']}.json").read_text())
        text = (ROOT / "data" / "contracts" / f"{case['id']}.md").read_text()
        results.append(score_case(case, predictions[case["id"]], expected, text))
    return results, render(results)


def render(results: List[CaseResult]) -> str:
    if not results:
        return "No cases scored.\n"
    fh, ft = sum(r.field_hits for r in results), sum(r.field_total for r in results)
    eh, et = sum(r.evidence_hits for r in results), sum(r.evidence_total for r in results)
    halluc = sum(len(r.hallucinated) for r in results)
    inj = [r for r in results if r.injection_ok is not None]
    lines = ["# Eval results", "",
             f"- Cases: {len(results)}",
             f"- Field accuracy: {fh}/{ft} ({100*fh/ft:.0f}%)",
             f"- Milestone schedule exact match: {sum(r.milestones_ok for r in results)}/{len(results)}",
             f"- Hallucinated fields (expected null, got a value): {halluc}",
             f"- Injection resistance: {sum(bool(r.injection_ok) for r in inj)}/{len(inj)} cases" if inj else "- Injection resistance: n/a",
             f"- Evidence quotes found verbatim in the contract: {eh}/{et} ({100*eh/max(et,1):.0f}%)",
             "", "| Case | Tags | Fields | Milestones | Hallucinated | Injection | Notes |", "|---|---|---|---|---|---|---|"]
    for r in results:
        inj_s = "—" if r.injection_ok is None else ("pass" if r.injection_ok else "FAIL")
        notes = "<br>".join(r.wrong) or "all correct"
        lines.append(f"| {r.case_id} | {', '.join(r.tags)} | {r.field_hits}/{r.field_total} | {'ok' if r.milestones_ok else 'mismatch'} | {', '.join(r.hallucinated) or '—'} | {inj_s} | {notes} |")
    return "\n".join(lines) + "\n"


def save_predictions(preds: Dict[str, ContractTerms], path: Path) -> None:
    path.write_text(json.dumps({k: v.model_dump() for k, v in preds.items()}, indent=2))


def load_predictions(path: Path) -> Dict[str, ContractTerms]:
    return {k: ContractTerms.model_validate(v) for k, v in json.loads(path.read_text()).items()}
