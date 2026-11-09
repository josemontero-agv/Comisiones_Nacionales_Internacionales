"""Comparador de filas Gold contra golden masters."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from mvp.application.contracts import GoldRow, ParityDifference
from mvp.domain.money import quantize_money, within_tolerance


def aggregate(rows: list[GoldRow]) -> dict[str, Decimal]:
    values: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    for row in rows:
        values[row.key] += row.commission_raw
    return dict(values)


def compare(
    expected: list[GoldRow],
    actual: list[GoldRow],
    classifications: dict[str, str] | None = None,
) -> list[ParityDifference]:
    expected_values = aggregate(expected)
    actual_values = aggregate(actual)
    classifications = classifications or {}
    differences: list[ParityDifference] = []
    for key in sorted(set(expected_values) | set(actual_values)):
        left = expected_values.get(key)
        right = actual_values.get(key)
        if left is not None and right is not None and within_tolerance(left, right):
            continue
        if left is None:
            classification = classifications.get(key, "elegibilidad")
            detail = "fila calculada no presente en el golden master"
        elif right is None:
            classification = classifications.get(key, "beneficiario")
            detail = "fila esperada no generada por el motor"
        else:
            classification = classifications.get(key, "base")
            detail = "importe fuera de tolerancia después de redondear a 2 decimales"
        delta = (
            None
            if left is None or right is None
            else quantize_money(right) - quantize_money(left)
        )
        differences.append(
            ParityDifference(
                key=key,
                classification=classification,
                expected=None if left is None else quantize_money(left),
                actual=None if right is None else quantize_money(right),
                delta=delta,
                detail=detail,
            )
        )
    return differences
