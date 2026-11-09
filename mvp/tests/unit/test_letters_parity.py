from datetime import date
from decimal import Decimal

import pytest

from mvp.application.contracts import GoldRow
from mvp.domain.letters import build_tracking
from mvp.domain.models import LetterIssued, LetterPayment
from mvp.domain.periods import Period
from mvp.historical.parity import compare


def test_letters_use_actual_amount_and_reject_duplicate_reconciliation() -> None:
    period = Period("nacional", date(2026, 9, 1), date(2026, 9, 30))
    issued = (
        LetterIssued("L1", "F1", Decimal(60)),
        LetterIssued("L2", "F1", Decimal(40)),
    )
    payments = (LetterPayment("L1", "F1", "Cobranza", Decimal(60), date(2026, 9, 10)),)
    tracking = build_tracking(issued, payments, period)[0]
    assert tracking.paid_in_period_amount == Decimal(60)
    assert tracking.missing_amount == Decimal(40)
    with pytest.raises(ValueError):
        build_tracking(issued, payments + payments, period)


def _row(amount: str) -> GoldRow:
    return GoldRow(
        "nacional",
        "CONTADO",
        "F1",
        "L1",
        "P1",
        "Ana",
        "Gerente",
        "PEN",
        Decimal(100),
        Decimal("0.01"),
        Decimal(amount),
        "R1",
        "S1",
    )


def test_parity_tolerance_is_applied_after_rounding() -> None:
    assert compare([_row("1.004")], [_row("1.014")]) == []
    differences = compare([_row("1.00")], [_row("1.02")])
    assert differences[0].classification == "base"
    assert differences[0].delta == Decimal("0.02")
