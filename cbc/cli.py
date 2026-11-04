"""Command line: cbc extract | check | eval."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from . import evaluate
from .schema import ContractTerms, InvoiceLine
from .validate import render_report, validate_invoices

ROOT = Path(__file__).resolve().parent.parent


def cmd_extract(a: argparse.Namespace) -> int:
    from .extract import extract_file
    terms = extract_file(a.contract, model=a.model)
    out = json.dumps(terms.model_dump(), indent=2)
    Path(a.out).write_text(out) if a.out else print(out)
    return 0


def cmd_check(a: argparse.Namespace) -> int:
    terms = ContractTerms.model_validate_json(Path(a.terms).read_text())
    invoices = [InvoiceLine.model_validate(x) for x in json.loads(Path(a.invoices).read_text())]
    findings = validate_invoices(terms, invoices)
    report = render_report(terms, invoices, findings)
    Path(a.report).write_text(report) if a.report else print(report)
    return 1 if any(f.severity == "error" for f in findings) else 0


def cmd_eval(a: argparse.Namespace) -> int:
    if a.predictions:
        preds = evaluate.load_predictions(Path(a.predictions))
        run_dir = Path(a.predictions).parent
    else:
        from .extract import extract_file
        run_dir = ROOT / "evals" / "runs" / datetime.now().strftime("%Y-%m-%d_%H%M%S")
        run_dir.mkdir(parents=True, exist_ok=True)
        preds = {}
        for case in evaluate.load_cases():
            if a.only and case["id"] not in a.only:
                continue
            print(f"extracting {case['id']} ...", file=sys.stderr)
            preds[case["id"]] = extract_file(ROOT / "data" / "contracts" / f"{case['id']}.md", model=a.model)
        evaluate.save_predictions(preds, run_dir / "predictions.json")
    results, report = evaluate.run(preds)
    (run_dir / "results.md").write_text(report)
    print(report)
    print(f"written to {run_dir}", file=sys.stderr)
    bad = any(r.hallucinated or r.injection_ok is False for r in results)
    return 1 if bad else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="cbc", description="Contract term extraction + invoice validation + evals")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract", help="extract ContractTerms from a contract file with Claude")
    e.add_argument("contract"); e.add_argument("--out"); e.add_argument("--model", default=None)
    e.set_defaults(fn=cmd_extract)
    c = sub.add_parser("check", help="validate invoices against extracted terms (no model)")
    c.add_argument("--terms", required=True); c.add_argument("--invoices", required=True); c.add_argument("--report")
    c.set_defaults(fn=cmd_check)
    v = sub.add_parser("eval", help="run the eval set live, or re-score saved predictions")
    v.add_argument("--predictions", help="score an existing predictions.json instead of calling the API")
    v.add_argument("--model", default=None); v.add_argument("--only", nargs="*")
    v.set_defaults(fn=cmd_eval)
    a = p.parse_args(argv)
    if getattr(a, "model", None) is None and hasattr(a, "model"):
        from .extract import DEFAULT_MODEL
        a.model = DEFAULT_MODEL
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
