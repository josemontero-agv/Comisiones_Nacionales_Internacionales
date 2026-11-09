"""Cálculo puro de bases y comisiones."""

from __future__ import annotations

from decimal import Decimal

from mvp.domain.money import calculate_commission, prorated_base


def payment_line_commission(
    paid_amount: Decimal,
    line_subtotal: Decimal,
    document_total: Decimal,
    rate: Decimal,
) -> tuple[Decimal, Decimal]:
    """Prorratea el monto real cobrado; no aplica el atajo fijo de IGV del Excel."""
    base = prorated_base(paid_amount, line_subtotal, document_total)
    return base, calculate_commission(base, rate)


def letter_line_commission(
    actual_letter_amount: Decimal,
    line_subtotal: Decimal,
    document_total: Decimal,
    rate: Decimal,
) -> tuple[Decimal, Decimal]:
    """Usa monto real de la letra, aunque las cuotas del documento sean desiguales."""
    return payment_line_commission(
        actual_letter_amount, line_subtotal, document_total, rate
    )
