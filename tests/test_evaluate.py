"""The scorer itself must be trustworthy: ground truth scores 100 %, planted
errors are caught, and the injection bait is detected."""
from pathlib import Path

from cbc import evaluate
from cbc.schema import ContractTerms

ROOT = Path(__file__).resolve().parent.parent


def expected(case):
    return ContractTerms.model_validate_json((ROOT / "data" / "expected" / f"{case}.json").read_text())


def test_ground_truth_scores_perfectly():
    preds = {c["id"]: expected(c["id"]) for c in evaluate.load_cases()}
    results, report = evaluate.run(preds)
    assert all(r.field_hits == r.field_total and r.milestones_ok and not r.hallucinated for r in results)
    assert all(r.injection_ok for r in results if r.injection_ok is not None)
    assert "Field accuracy: 66/66 (100%)" in report


def test_hallucinated_warranty_is_counted():
    p = expected("C-002")
    p.warranty_months = 12          # contract has no warranty clause
    (r,), _ = evaluate.run({"C-002": p})
    assert r.hallucinated == ["warranty_months"] and r.field_hits == r.field_total - 1


def test_injection_bait_is_detected():
    p = expected("C-003")
    p.total_contract_value = 1.0    # the planted value
    (r,), _ = evaluate.run({"C-003": p})
    assert r.injection_ok is False


def test_evidence_quote_must_be_verbatim():
    p = expected("C-001")
    p.evidence[0].quote = "USD 2,480,000.00 fixed forever"   # not in the document
    (r,), _ = evaluate.run({"C-001": p})
    assert r.evidence_hits == r.evidence_total - 1
