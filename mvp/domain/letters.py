"""Seguimiento de letras y control anti-duplicado."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from mvp.domain.models import LetterIssued, LetterPayment, LetterTracking
from mvp.domain.periods import Period
from mvp.domain.rules import normalize_key


def reconciliation_key(payment: LetterPayment) -> str:
    return f"{payment.letter_number}|{payment.doc_key}|{payment.payment_date.isoformat()}|{payment.amount}"


def ensure_unique(payments: tuple[LetterPayment, ...]) -> None:
    keys = [reconciliation_key(payment) for payment in payments]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate letter reconciliation")


def eligible_letter(payment: LetterPayment) -> bool:
    return normalize_key(payment.status) in {"DESCUENTO", "CARTERA", "COBRANZA"}


def build_tracking(
    issued: tuple[LetterIssued, ...],
    payments: tuple[LetterPayment, ...],
    period: Period,
    historical_cutoff: date | None = None,
) -> tuple[LetterTracking, ...]:
    ensure_unique(payments)
    by_doc_issued: dict[str, list[LetterIssued]] = defaultdict(list)
    by_doc_paid: dict[str, list[LetterPayment]] = defaultdict(list)
    for item in issued:
        by_doc_issued[item.doc_key].append(item)
    for item in payments:
        by_doc_paid[item.doc_key].append(item)

    result: list[LetterTracking] = []
    for doc_key in sorted(set(by_doc_issued) | set(by_doc_paid)):
        doc_issued = by_doc_issued[doc_key]
        doc_paid = by_doc_paid[doc_key]
        paid_before = [
            item
            for item in doc_paid
            if item.payment_date < period.start and eligible_letter(item)
        ]
        paid_in = [
            item
            for item in doc_paid
            if period.contains(item.payment_date) and eligible_letter(item)
        ]
        protested = [
            item
            for item in doc_paid
            if period.contains(item.payment_date)
            and normalize_key(item.status) == "PROTESTADO"
        ]
        paid_numbers = {
            item.letter_number for item in doc_paid if eligible_letter(item)
        }
        missing = [
            item for item in doc_issued if item.letter_number not in paid_numbers
        ]
        result.append(
            LetterTracking(
                doc_key=doc_key,
                issued_count=len(doc_issued),
                issued_amount=sum((item.amount for item in doc_issued), Decimal(0)),
                paid_before_count=len(paid_before),
                paid_before_amount=sum(
                    (item.amount for item in paid_before), Decimal(0)
                ),
                paid_in_period_count=len(paid_in),
                paid_in_period_amount=sum(
                    (item.amount for item in paid_in), Decimal(0)
                ),
                protested_in_period_count=len(protested),
                missing_count=len(missing),
                missing_amount=sum((item.amount for item in missing), Decimal(0)),
                status="complete" if not missing else "pending",
            )
        )
    return tuple(result)
