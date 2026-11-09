from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

MONEY_SCALE = 2
MONEY_QUANTUM = Decimal("0.01")
ABSOLUTE_TOLERANCE = Decimal("0.01")
ZERO = Decimal(0)

COMPARISON_POLICY: dict[str, object] = {
    "scale": MONEY_SCALE,
    "rounding": "ROUND_HALF_UP",
    "absolute_tolerance": str(ABSOLUTE_TOLERANCE),
    "keys_must_match_exactly": True,
    "membership_must_match_exactly": True,
}


def to_decimal(value: object) -> Decimal:
    """Convierte a Decimal pasando siempre por texto.

    Los `float` provenientes de Excel/XML-RPC se convierten con `repr`, que produce la
    representación decimal más corta que reproduce el binario; nunca se usa
    `Decimal(float)` porque arrastraría el error binario completo.
    """
    if value is None or value == "":
        return ZERO
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise TypeError("bool is not a monetary value")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(repr(value))
    text = str(value).strip().replace("\xa0", "")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"invalid decimal value: {value!r}") from exc


def quantize_money(value: Decimal) -> Decimal:
    """Cuantiza solo en la frontera de presentación/comparación."""
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def decimal_text(value: Decimal) -> str:
    """Texto canónico estable para hashes y contratos (sin notación científica)."""
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        normalized = normalized.quantize(Decimal(1))
    return format(normalized, "f")


def within_tolerance(left: Decimal, right: Decimal) -> bool:
    return abs(quantize_money(left) - quantize_money(right)) <= ABSOLUTE_TOLERANCE


@dataclass(frozen=True, slots=True)
class CommissionAmount:
    raw: Decimal
    currency: str

    def presented(self) -> Decimal:
        return quantize_money(self.raw)


def calculate_commission(base: Decimal, rate: Decimal) -> Decimal:
    if base < ZERO or rate < ZERO:
        raise ValueError("base and rate must be non-negative")
    return base * rate


def prorated_base(
    paid: Decimal, line_subtotal: Decimal, document_total: Decimal
) -> Decimal:
    """Base neta de una línea para un cobro.

    `paid × subtotal_línea / total_documento` aplica el impuesto real de cada línea: con IGV
    18% en todo el documento equivale a `(paid / 1.18) × subtotal_línea / subtotal_doc`, y
    en una exportación exonerada no divide entre 1.18.
    """
    if document_total <= ZERO:
        raise ValueError("document total must be positive")
    if paid < ZERO or line_subtotal < ZERO:
        raise ValueError("paid and line subtotal must be non-negative")
    return paid * line_subtotal / document_total
