"""Elegibilidad explícita de documento, línea y cobro."""

from __future__ import annotations

from dataclasses import dataclass

from mvp.domain.models import (
    KIND_CREDIT_NOTE,
    KIND_LETTER_TRANSFER,
    Document,
    DocumentLine,
    PaymentAllocation,
)
from mvp.domain.rules import Ruleset, normalize_key


@dataclass(frozen=True, slots=True)
class Eligibility:
    eligible: bool
    code: str
    blocking: bool = False


def evaluate(
    document: Document,
    line: DocumentLine,
    allocation: PaymentAllocation,
    ruleset: Ruleset,
) -> Eligibility:
    if normalize_key(document.channel) == "DIGITAL":
        return Eligibility(False, "DIGITAL_OUT_OF_PILOT")
    doc_type = normalize_key(f"{document.doc_type_code} {document.doc_type_name}")
    if "BOLETA" in doc_type or document.doc_type_code in {"03", "07"}:
        return Eligibility(False, "DOCUMENT_TYPE_EXCLUDED")
    if normalize_key(document.sale_type_name) == "TTG" or "TTG" in normalize_key(
        document.payment_term_name
    ):
        return Eligibility(False, "TTG_EXCLUDED")
    team = normalize_key(document.team_name)
    if team.startswith("MARKETING") or team == "OFICINA":
        return Eligibility(False, "TEAM_EXCLUDED")
    if normalize_key(document.journal_code) in {"001", "060"}:
        return Eligibility(False, "JOURNAL_EXCLUDED")
    if normalize_key(document.payment_state) == "REVERSED":
        return Eligibility(False, "REVERSED")
    if allocation.counterpart_kind == KIND_CREDIT_NOTE:
        return Eligibility(False, "CREDIT_NOTE_ALLOCATION")
    if allocation.counterpart_kind == KIND_LETTER_TRANSFER:
        return Eligibility(False, "LETTER_TRANSFER_NOT_PAYMENT")

    excluded_accounts = ruleset.catalogs.get("excluded_accounts")
    if excluded_accounts and excluded_accounts.contains(line.account_code):
        return Eligibility(False, "ACCOUNT_EXCLUDED")
    allowed_accounts = ruleset.catalogs.get("allowed_accounts")
    if allowed_accounts and not allowed_accounts.contains(line.account_code):
        return Eligibility(False, "UNKNOWN_ACCOUNT", blocking=True)
    excluded_concepts = ruleset.catalogs.get("excluded_concepts")
    text = normalize_key(f"{line.product_name} {line.line_category}")
    if excluded_concepts and any(
        normalize_key(value) in text for value in excluded_concepts.values
    ):
        return Eligibility(False, "CONCEPT_EXCLUDED")
    if not line.product_code:
        return Eligibility(False, "MISSING_PRODUCT", blocking=True)
    return Eligibility(True, "ELIGIBLE")
