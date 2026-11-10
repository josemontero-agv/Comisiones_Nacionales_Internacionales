"""Contratos canónicos compartidos por motor, paridad, exportador y UI."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from mvp.domain.money import COMPARISON_POLICY, decimal_text, quantize_money
from mvp.domain.periods import BUSINESS_TIMEZONE, Period


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return decimal_text(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in sorted(value.items())}
    return value


def canonical_json(value: Any) -> str:
    """Serializa sin depender de locale, orden de diccionario ni representación float."""
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    return json.dumps(
        _json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CommissionRunRequest:
    channel: str
    period_start: date
    period_end: date
    source_snapshot_id: str
    ruleset_version: str
    engine_version: str = "0.1.0"
    business_timezone: str = BUSINESS_TIMEZONE

    def __post_init__(self) -> None:
        Period(self.channel, self.period_start, self.period_end)
        if self.business_timezone != BUSINESS_TIMEZONE:
            raise ValueError(f"business timezone must be {BUSINESS_TIMEZONE}")
        if not self.source_snapshot_id or not self.ruleset_version:
            raise ValueError("snapshot and ruleset versions are required")

    @property
    def request_sha256(self) -> str:
        return sha256_json(self)


@dataclass(frozen=True, slots=True)
class GoldRow:
    channel: str
    category: str
    document: str
    line: str
    allocation: str
    person: str
    role: str
    currency: str
    base_raw: Decimal
    rate: Decimal
    commission_raw: Decimal
    rule_id: str
    source_key: str
    commercial_line: str = ""

    @property
    def key(self) -> str:
        return f"{self.channel}|{self.category}|{self.document}|{self.line}|{self.allocation}|{self.person}|{self.role}"

    @property
    def commission_presented(self) -> Decimal:
        return quantize_money(self.commission_raw)

    def contract(self) -> dict[str, Any]:
        return {
            "key": self.key,
            **_json_value(asdict(self)),
            "commission_presented": decimal_text(self.commission_presented),
            "comparison_policy": COMPARISON_POLICY,
        }


@dataclass(frozen=True, slots=True)
class CollectedLine:
    """Cobro atribuible a una línea fuente, sin duplicarlo por beneficiario."""

    channel: str
    category: str
    commercial_line: str
    document: str
    line: str
    allocation: str
    currency: str
    collected_raw: Decimal
    source_key: str

    @property
    def key(self) -> str:
        return (
            f"{self.channel}|{self.category}|{self.document}|{self.line}|"
            f"{self.allocation}|{self.source_key}"
        )

    @property
    def collected_presented(self) -> Decimal:
        return quantize_money(self.collected_raw)

    def contract(self) -> dict[str, Any]:
        return {
            "key": self.key,
            **_json_value(asdict(self)),
            "collected_presented": decimal_text(self.collected_presented),
        }


@dataclass(frozen=True, slots=True)
class ParityDifference:
    key: str
    classification: str
    expected: Decimal | None
    actual: Decimal | None
    delta: Decimal | None
    detail: str


@dataclass(slots=True)
class RunResult:
    run_id: str
    snapshot_id: str
    channel: str
    period_start: date
    period_end: date
    currency: str
    status: str
    expected_total: Decimal
    actual_total: Decimal
    rows: list[GoldRow] = field(default_factory=list)
    collected_rows: list[CollectedLine] = field(default_factory=list)
    differences: list[ParityDifference] = field(default_factory=list)
    exceptions: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def delta(self) -> Decimal:
        return self.actual_total - self.expected_total

    def manifest(self) -> dict[str, Any]:
        rows_hash = hashlib.sha256(
            (
                "\n".join(
                    canonical_json(row.contract())
                    for row in sorted(self.rows, key=lambda item: item.key)
                )
            ).encode("utf-8")
        ).hexdigest()
        collected_hash = hashlib.sha256(
            (
                "\n".join(
                    canonical_json(row.contract())
                    for row in sorted(self.collected_rows, key=lambda item: item.key)
                )
            ).encode("utf-8")
        ).hexdigest()
        return {
            "run_id": self.run_id,
            "snapshot_id": self.snapshot_id,
            "channel": self.channel,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "currency": self.currency,
            "status": self.status,
            "expected_total": decimal_text(self.expected_total),
            "actual_total": decimal_text(self.actual_total),
            "delta": decimal_text(self.delta),
            "row_count": len(self.rows),
            "collected_row_count": len(self.collected_rows),
            "difference_count": len(self.differences),
            "exception_count": len(self.exceptions),
            "gold_sha256": rows_hash,
            "collected_sha256": collected_hash,
            "comparison_policy": COMPARISON_POLICY,
            **self.metadata,
        }
