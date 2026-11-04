"""Schema for extracted contract terms.

Every field is optional on purpose: the extractor must return null when the
contract does not state a term, and the eval set scores a non-null value for a
missing term as a hallucination.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class Milestone(BaseModel):
    name: str = Field(description="Milestone name as written in the contract, e.g. 'Deposit', 'Shipment'.")
    percent_of_total: float = Field(description="Share of the total contract value billed at this milestone, as a percentage (0-100).")
    trigger: str = Field(description="Event that makes the milestone invoiceable, quoted or closely paraphrased from the contract.")


class Evidence(BaseModel):
    field: str = Field(description="Name of the ContractTerms field this quote supports.")
    quote: str = Field(description="Verbatim quote from the contract that supports the value.")


class ContractTerms(BaseModel):
    contract_number: Optional[str] = Field(None, description="Contract or agreement number. Null if not stated.")
    supplier: Optional[str] = Field(None, description="Legal name of the party supplying the goods or services. Null if not stated.")
    customer: Optional[str] = Field(None, description="Legal name of the party buying. Null if not stated.")
    total_contract_value: Optional[float] = Field(None, description="Total contract price as a number, after applying any amendment that changes it. Null if not stated.")
    currency: Optional[str] = Field(None, description="ISO 4217 currency code of the contract price (USD, EUR, ...). Null if not stated.")
    payment_terms_days: Optional[int] = Field(None, description="Number of days after invoice date that payment is due (e.g. 30 for 'net 30'). Null if not stated.")
    milestones: List[Milestone] = Field(default_factory=list, description="Payment milestones in contract order. Empty if the contract has no milestone schedule.")
    delivery_deadline: Optional[str] = Field(None, description="Contractual delivery or completion deadline as an ISO date (YYYY-MM-DD), after any amendment. Null if not stated.")
    liquidated_damages_percent_per_week: Optional[float] = Field(None, description="Late-delivery liquidated damages as percent of contract value per week of delay. Null if the contract has no such clause.")
    liquidated_damages_cap_percent: Optional[float] = Field(None, description="Cap on liquidated damages as percent of contract value. Null if not stated.")
    warranty_months: Optional[int] = Field(None, description="Warranty period in months. Null if the contract has no warranty clause.")
    change_orders_require_written_approval: Optional[bool] = Field(None, description="True if the contract says changes must be approved in writing; false if it says they need not be; null if the contract is silent.")
    evidence: List[Evidence] = Field(default_factory=list, description="One verbatim quote per populated field.")


class InvoiceLine(BaseModel):
    invoice_number: str
    contract_number: str
    invoice_date: str
    due_date: Optional[str] = None
    currency: str
    amount: float
    milestone: Optional[str] = None
    description: str = ""


class Finding(BaseModel):
    code: str
    severity: str  # "error" | "warning"
    invoice_number: Optional[str]
    message: str
