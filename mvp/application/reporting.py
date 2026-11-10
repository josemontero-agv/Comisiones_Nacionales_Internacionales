"""Proyecciones de reporte construidas exclusivamente desde el contrato Gold."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

CATEGORIES = ("CONTADO", "CREDITO", "LETRAS")
ROLE_ORDER = {
    "Gerente": 0,
    "Jefe Comercial": 1,
    "Jefe Tecnico": 2,
    "Representante de Ventas": 3,
    "Ventas Internacionales": 4,
    "Jefe Tecnico Comercial Latinoamerica Avivet": 5,
}


def _money(value: object) -> Decimal:
    return Decimal(str(value or "0"))


def build_commission_pivot(payloads: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Agrupa puesto → línea comercial → persona sin mezclar canales."""
    channels: set[str] = set()
    summary: dict[tuple[str, str, str], dict[str, Decimal]] = defaultdict(
        lambda: {category: Decimal(0) for category in CATEGORIES}
    )
    for payload in payloads:
        channels.add(str(payload["manifest"]["channel"]))
        for row in payload["rows"]:
            category = str(row["category"])
            if category not in CATEGORIES:
                raise ValueError(f"categoría Gold no soportada: {category}")
            key = (
                str(row["role"]),
                str(row["commercial_line"]),
                str(row["person"]),
            )
            summary[key][category] += _money(row["commission_presented"])
    if len(channels) > 1:
        raise ValueError("la pivote no puede mezclar canales")

    rows: list[dict[str, Any]] = []
    for (role, commercial_line, person), values in sorted(
        summary.items(),
        key=lambda item: (
            ROLE_ORDER.get(item[0][0], 99),
            item[0][0],
            item[0][1],
            item[0][2],
        ),
    ):
        total = sum(values.values(), Decimal(0))
        if total == 0:
            continue
        rows.append(
            {
                "Puesto": role,
                "Línea comercial": commercial_line,
                "Nombre": person,
                **{category: values[category] for category in CATEGORIES},
                "Total": total,
            }
        )
    return rows


def build_collected_by_line(
    payloads: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Mantiene el cobrado una sola vez por línea, separado de las comisiones."""
    channels: set[str] = set()
    currency_by_line: dict[str, str] = {}
    collected: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {category: Decimal(0) for category in CATEGORIES}
    )
    commissions: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {category: Decimal(0) for category in CATEGORIES}
    )
    for payload in payloads:
        channels.add(str(payload["manifest"]["channel"]))
        for row in payload.get("collected_rows", []):
            commercial_line = str(row["commercial_line"])
            category = str(row["category"])
            currency_by_line[commercial_line] = str(row["currency"])
            collected[commercial_line][category] += _money(row["collected_presented"])
        for row in payload["rows"]:
            commercial_line = str(row["commercial_line"])
            category = str(row["category"])
            currency_by_line.setdefault(commercial_line, str(row["currency"]))
            commissions[commercial_line][category] += _money(
                row["commission_presented"]
            )
    if len(channels) > 1:
        raise ValueError("el cobrado por línea no puede mezclar canales")

    rows: list[dict[str, Any]] = []
    for commercial_line in sorted(set(collected) | set(commissions)):
        paid = collected[commercial_line]
        commission = commissions[commercial_line]
        rows.append(
            {
                "Moneda": currency_by_line[commercial_line],
                "Línea comercial": commercial_line,
                **{
                    f"Cobrado {category}": paid[category] for category in CATEGORIES
                },
                "Total cobrado": sum(paid.values(), Decimal(0)),
                **{
                    f"Comisión {category}": commission[category]
                    for category in CATEGORIES
                },
                "Total comisión": sum(commission.values(), Decimal(0)),
            }
        )
    return rows
