import json
from pathlib import Path

from cbc.schema import ContractTerms, InvoiceLine
from cbc.validate import validate_invoices

DATA = Path(__file__).resolve().parent.parent / "data"


def load(case):
    terms = ContractTerms.model_validate_json((DATA / "expected" / f"{case}.json").read_text())
    invoices = [InvoiceLine.model_validate(x) for x in json.loads((DATA / "invoices" / f"{case}.json").read_text())]
    return terms, invoices


def codes(findings):
    return sorted((f.code, f.invoice_number) for f in findings)


def test_clean_invoices_pass():
    terms, invoices = load("C-002")
    assert validate_invoices(terms, invoices) == []


def test_c001_catches_each_planted_error():
    terms, invoices = load("C-001")
    found = codes(validate_invoices(terms, invoices))
    assert ("V06", "NW-1003") in found          # 600,000 billed, 25% of 2,480,000 = 620,000
    assert ("V07", "NW-1003") in found          # due date not net 30
    assert ("V03", "NW-1003") in found          # duplicate invoice number
    assert ("V04", "NW-1003") in found          # 'Site survey' is not a milestone
    assert ("V08", None) in found               # 2,505,000 billed against a 2,480,000 contract


def test_amended_price_and_duplicate_milestone():
    terms, invoices = load("C-006")
    found = codes(validate_invoices(terms, invoices))
    assert ("V06", "RC-301") in found           # deposit billed on the old 640,000 price
    assert ("V05", "RC-343") in found           # deposit milestone billed twice
    assert ("V06", "RC-343") in found


def test_missing_total_skips_amount_checks():
    terms, invoices = load("C-002")
    terms.total_contract_value = None
    found = validate_invoices(terms, invoices)
    assert [f.code for f in found] == ["V00"]


def test_currency_and_contract_mismatch():
    terms, invoices = load("C-002")
    invoices[0].currency = "USD"
    invoices[1].contract_number = "PO-00000"
    found = codes(validate_invoices(terms, invoices))
    assert ("V02", "KP-5590") in found and ("V01", "KP-5634") in found
