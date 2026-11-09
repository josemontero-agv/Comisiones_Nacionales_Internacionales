from datetime import date
from decimal import Decimal

import pytest

from mvp.domain.money import prorated_base, quantize_money, within_tolerance
from mvp.domain.periods import Period


def test_money_rounds_half_up_and_compares_after_presentation() -> None:
    assert quantize_money(Decimal("1.005")) == Decimal("1.01")
    assert within_tolerance(Decimal("1.004"), Decimal("1.014"))
    assert not within_tolerance(Decimal("1.004"), Decimal("1.025"))


def test_prorated_base_uses_real_document_total() -> None:
    assert prorated_base(Decimal(118), Decimal(50), Decimal(118)) == Decimal(50)
    assert prorated_base(Decimal(100), Decimal(50), Decimal(100)) == Decimal(50)


def test_period_is_inclusive_and_validated() -> None:
    period = Period("nacional", date(2026, 9, 1), date(2026, 9, 30))
    assert period.contains(date(2026, 9, 1))
    assert period.contains(date(2026, 9, 30))
    with pytest.raises(ValueError):
        Period("digital", date(2026, 9, 1), date(2026, 9, 30))
