"""Entidades Silver tipadas. No dependen de Excel, Odoo ni SQLite."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

CATEGORY_CONTADO = "CONTADO"
CATEGORY_CREDITO = "CREDITO"
CATEGORY_LETRAS = "LETRAS"
CATEGORIES = (CATEGORY_CONTADO, CATEGORY_CREDITO, CATEGORY_LETRAS)

KIND_PAYMENT = "payment"
KIND_CREDIT_NOTE = "credit_note"
KIND_LETTER_TRANSFER = "letter_transfer"
KIND_UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Document:
    doc_key: str
    channel: str
    currency: str
    amount_total: Decimal
    amount_untaxed: Decimal
    move_type: str | None = None
    doc_type_code: str | None = None
    doc_type_name: str | None = None
    journal_code: str | None = None
    journal_name: str | None = None
    team_name: str | None = None
    sale_type_name: str | None = None
    payment_term_name: str | None = None
    payment_state: str | None = None
    invoice_date: date | None = None
    partner_ref: str | None = None
    partner_name: str | None = None
    country_id: int | None = None
    country_code: str | None = None
    zone_name: str | None = None
    salesperson: str | None = None
    enriched: bool = False
    source_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DocumentLine:
    doc_key: str
    line_key: str
    price_subtotal: Decimal
    price_total: Decimal
    product_code: str | None = None
    product_name: str | None = None
    commercial_line: str | None = None
    line_category: str | None = None
    account_code: str | None = None
    tax_names: tuple[str, ...] = ()
    source_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PaymentAllocation:
    doc_key: str
    allocation_key: str
    payment_date: date
    amount: Decimal
    counterpart_kind: str = KIND_PAYMENT
    counterpart_ref: str | None = None
    fx_rate: Decimal | None = None
    review_flag: str | None = None
    source_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LetterPayment:
    letter_number: str
    doc_key: str
    status: str
    amount: Decimal
    payment_date: date
    source_keys: tuple[str, ...] = ()

    @property
    def letter_key(self) -> str:
        return f"{self.letter_number}|{self.doc_key}"


@dataclass(frozen=True, slots=True)
class LetterIssued:
    letter_number: str
    doc_key: str
    amount: Decimal
    source_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SilverSnapshot:
    """Conjunto Silver completo de un snapshot, listo para calcular."""

    snapshot_id: str
    channel: str
    documents: tuple[Document, ...] = ()
    lines: tuple[DocumentLine, ...] = ()
    allocations: tuple[PaymentAllocation, ...] = ()
    letter_payments: tuple[LetterPayment, ...] = ()
    letters_issued: tuple[LetterIssued, ...] = ()
    letter_history: tuple[LetterPayment, ...] = ()
    source_notes: tuple[str, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class EngineException:
    code: str
    severity: str
    blocking: bool
    entity_type: str
    entity_key: str
    message: str
    action_required: str
    amount: Decimal | None = None
    evidence: tuple[tuple[str, str], ...] = ()

    def sort_key(self) -> tuple[int, str, str, str]:
        rank = {"error": 0, "warning": 1, "info": 2}.get(self.severity, 3)
        return (rank, self.code, self.entity_type, self.entity_key)


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    doc_key: str
    line_key: str
    allocation_key: str
    category: str
    eligible: bool
    reason_code: str
    rule_id: str
    base: Decimal
    evidence: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class CommissionLine:
    category: str
    doc_key: str
    line_key: str
    allocation_key: str
    payment_date: date
    product_code: str | None
    commercial_line: str | None
    rule_key: str
    role: str
    beneficiary: str
    rule_id: str
    rate: Decimal
    base: Decimal
    commission: Decimal
    source_keys: tuple[str, ...] = ()

    def sort_key(self) -> tuple[str, ...]:
        return (
            self.category,
            self.doc_key,
            self.line_key,
            self.allocation_key,
            self.role,
            self.beneficiary,
            self.rule_id,
        )


@dataclass(frozen=True, slots=True)
class LetterTracking:
    doc_key: str
    issued_count: int
    issued_amount: Decimal
    paid_before_count: int
    paid_before_amount: Decimal
    paid_in_period_count: int
    paid_in_period_amount: Decimal
    protested_in_period_count: int
    missing_count: int
    missing_amount: Decimal
    status: str
