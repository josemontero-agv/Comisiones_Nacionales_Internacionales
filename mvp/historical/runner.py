"""Ejecución reproducible de los cierres históricos aprobados."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from mvp.application.contracts import GoldRow, RunResult, sha256_json
from mvp.domain.commissions import letter_line_commission, payment_line_commission
from mvp.domain.money import quantize_money, to_decimal
from mvp.historical.importers import (
    cell_value,
    file_sha256,
    nacional_matrix,
    rows_with_header,
)
from mvp.historical.parity import compare
from mvp.infrastructure.sqlite import MedallionRepository

ROOT = Path(__file__).resolve().parents[2]
NACIONAL_GOLDEN = (
    ROOT
    / "Proceso_Manual/nacional/calculo_vendedores/COMISIONES 2026 SETIEMBRE (1).xlsx"
)
INTERNACIONAL_GOLDEN = (
    ROOT
    / "Proceso_Manual/internacional/SEPTIEMBRE"
    / "COMISION EXTERIOR 20 AGOSTO 2026 AL 20 SEPTIEMBRE 2026.xlsx"
)

NACIONAL_ROLES = (
    ("Representante de Ventas", "Representante de Ventas", "Comision"),
    ("Jefe Tecnico", "Jefe Tecnico", "Comisión4"),
    ("Jefe Comercial", "Jefe Comercial", "Comision2"),
    ("Gerente", "Gerente", "Comision3"),
)

INTL_RATES: dict[str, dict[str, Decimal]] = {
    "Ariana Carmona": {
        "AGROVET": Decimal("0.0001"),
        "PETMEDICA": Decimal("0.00015"),
        "AVIVET": Decimal("0.0002"),
    },
    "Ivonne Panta": {
        "AGROVET": Decimal("0.0001"),
        "PETMEDICA": Decimal("0.00015"),
        "AVIVET": Decimal("0.0002"),
    },
    "Sandra Meneses": {
        "AGROVET": Decimal("0.0008"),
        "PETMEDICA": Decimal("0.0012"),
        "AVIVET": Decimal("0.0016"),
    },
    "Luis Chavez": {
        "AGROVET": Decimal(0),
        "PETMEDICA": Decimal("0.005"),
        "AVIVET": Decimal(0),
    },
    "Vanessa Parker": {
        "AGROVET": Decimal("0.0002"),
        "PETMEDICA": Decimal("0.0003"),
        "AVIVET": Decimal("0.0004"),
    },
    "Umberto Calderón": {
        "AGROVET": Decimal("0.0016"),
        "PETMEDICA": Decimal("0.0024"),
        "AVIVET": Decimal("0.0032"),
    },
}


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _date_text(value: object) -> str:
    if hasattr(value, "date"):
        value = value.date()
    return value.isoformat() if hasattr(value, "isoformat") else _text(value)


def _gold_row(
    *,
    channel: str,
    category: str,
    document: str,
    line: str,
    allocation: str,
    person: str,
    role: str,
    currency: str,
    base: Decimal,
    rate: Decimal,
    commission: Decimal,
    rule_id: str,
    source_key: str,
) -> GoldRow:
    return GoldRow(
        channel=channel,
        category=category,
        document=document,
        line=line,
        allocation=allocation,
        person=person,
        role=role,
        currency=currency,
        base_raw=base,
        rate=rate,
        commission_raw=commission,
        rule_id=rule_id,
        source_key=source_key,
    )


def _national_rows() -> tuple[
    list[GoldRow], list[GoldRow], list[dict[str, Any]], list[dict[str, Any]]
]:
    matrix = nacional_matrix(NACIONAL_GOLDEN)
    expected: list[GoldRow] = []
    actual: list[GoldRow] = []
    exceptions: list[dict[str, Any]] = [
        {
            "key": "NAC-LEGACY-ELIGIBILITY",
            "code": "LEGACY_ELIGIBILITY_INPUT",
            "blocking": True,
            "detail": "El cierre no contiene todos los atributos Odoo; FILTRO se usa solo como membresía histórica.",
        }
    ]
    bronze: list[dict[str, Any]] = []
    missing_beneficiaries: set[tuple[str, str]] = set()
    for sheet in ("CONTADO - CREDITO", "LETRAS"):
        for row in rows_with_header(NACIONAL_GOLDEN, sheet):
            if _text(row.get("FILTRO")).upper() != "COMISIONA":
                continue
            excel_row = int(row["__excel_row"])
            document = _text(row.get("Factura"))
            product = _text(row.get("Referencia Interna"))
            line = f"{product}|{sheet}|{excel_row}"
            category = _text(row.get("TIPO")).upper()
            allocation = (
                _text(row.get("NumLetra"))
                if category == "LETRAS"
                else f"{document}|{_date_text(row.get('FechaPagLT'))}|{excel_row}"
            )
            source_key = f"{sheet}!{excel_row}"
            bronze.append(row)
            subtotal = to_decimal(row.get("Subtotal x Linea"))
            total = to_decimal(row.get("Total FT"))
            paid = to_decimal(
                row.get("ValorLT") if category == "LETRAS" else row.get("Monto Pagado")
            )
            if total <= 0:
                exceptions.append(
                    {
                        "key": source_key,
                        "code": "INVALID_DOCUMENT_TOTAL",
                        "blocking": True,
                        "detail": document,
                    }
                )
                continue
            matrix_key = _text(row.get("Linea Comercial Zona")).upper()
            assignments = matrix.get(matrix_key)
            if assignments is None:
                exceptions.append(
                    {
                        "key": source_key,
                        "code": "MISSING_NATIONAL_RULE",
                        "blocking": True,
                        "detail": matrix_key,
                    }
                )
                continue
            by_role = {
                role: (person, to_decimal(rate)) for role, person, rate in assignments
            }
            for role, person_column, commission_column in NACIONAL_ROLES:
                expected_person = _text(row.get(person_column))
                expected_amount = to_decimal(row.get(commission_column))
                if expected_amount and expected_person not in {"", "0"}:
                    expected.append(
                        _gold_row(
                            channel="nacional",
                            category=category,
                            document=document,
                            line=line,
                            allocation=allocation,
                            person=expected_person,
                            role=role,
                            currency="PEN",
                            base=Decimal(0),
                            rate=Decimal(0),
                            commission=expected_amount,
                            rule_id="GOLDEN-NACIONAL",
                            source_key=source_key,
                        )
                    )
                person, rate = by_role[role]
                if rate <= 0:
                    continue
                if not person:
                    missing_key = (matrix_key, role)
                    if missing_key not in missing_beneficiaries:
                        missing_beneficiaries.add(missing_key)
                        exceptions.append(
                            {
                                "key": f"{matrix_key}|{role}",
                                "code": "MISSING_BENEFICIARY",
                                "blocking": True,
                                "detail": matrix_key,
                                "amount": str(quantize_money(subtotal * rate)),
                            }
                        )
                    continue
                if category == "LETRAS":
                    base, commission = letter_line_commission(
                        paid, subtotal, total, rate
                    )
                else:
                    base, commission = payment_line_commission(
                        paid, subtotal, total, rate
                    )
                actual.append(
                    _gold_row(
                        channel="nacional",
                        category=category,
                        document=document,
                        line=line,
                        allocation=allocation,
                        person=person,
                        role=role,
                        currency="PEN",
                        base=base,
                        rate=rate,
                        commission=commission,
                        rule_id=f"NAC:{matrix_key}",
                        source_key=source_key,
                    )
                )
    return expected, actual, exceptions, bronze


def _flag(row: dict[str, Any], column: str) -> bool:
    return _text(row.get(column)).upper() == "SI"


def _international_rows() -> tuple[
    list[GoldRow], list[GoldRow], list[dict[str, Any]], list[dict[str, Any]]
]:
    rows = rows_with_header(INTERNACIONAL_GOLDEN, "DETALLE DE COBRANZA ", header_row=3)
    expected: list[GoldRow] = []
    actual: list[GoldRow] = []
    bronze: list[dict[str, Any]] = []
    exceptions: list[dict[str, Any]] = [
        {
            "key": "INTL-LUIS-SCOPE",
            "code": "PROVISIONAL_COUNTRY_MAPPING",
            "blocking": True,
            "detail": "El Excel no incluye país ISO; se conserva la marca histórica de Luis como evidencia provisional.",
        },
        {
            "key": "INTL-MAYUMI-SCOPE",
            "code": "MISSING_LATAM_MAPPING",
            "blocking": True,
            "detail": "No puede calcularse Mayumi 0.5% AVIVET+LATAM sin país ISO aprobado.",
        },
    ]
    for row in rows:
        document = _text(row.get("FACTURA /LETRA"))
        product = _text(row.get("CODIGO"))
        commercial_line = _text(row.get("LINEA")).upper()
        if not document or commercial_line not in {"AGROVET", "PETMEDICA", "AVIVET"}:
            continue
        excel_row = int(row["__excel_row"])
        line = f"{product}|DETALLE|{excel_row}"
        payment_date = _date_text(row.get("FECHA DE PAGO"))
        allocation = f"{document}|{payment_date}|{excel_row}"
        source_key = f"DETALLE DE COBRANZA !{excel_row}"
        bronze.append(row)
        line_amount = to_decimal(row.get("MONTO VENTA US$"))
        document_total = to_decimal(row.get("TOTAL POR FACTURA USD $"))
        paid = to_decimal(row.get("PAGO USD"))
        if document_total <= 0:
            continue
        base, _ = payment_line_commission(paid, line_amount, document_total, Decimal(0))
        expected_flags = {
            "Vanessa Parker": _flag(row, "COMISION VANESSA PARKER"),
            "Ariana Carmona": _flag(
                row,
                "COMISION VANESSA PARKER"
                if commercial_line == "PETMEDICA"
                else "COMISION\nARIANA",
            ),
            "Ivonne Panta": _flag(row, "IVONNE PANTA"),
            "Luis Chavez": _flag(row, "COMISION LUIS"),
            "Sandra Meneses": True,
            "Umberto Calderón": True,
        }
        actual_flags = {
            "Vanessa Parker": True,
            "Ariana Carmona": True,
            "Ivonne Panta": True,
            "Luis Chavez": _flag(row, "COMISION LUIS"),
            "Sandra Meneses": True,
            "Umberto Calderón": True,
        }
        for person, rates in INTL_RATES.items():
            rate = rates[commercial_line]
            if rate <= 0:
                continue
            if expected_flags[person]:
                expected.append(
                    _gold_row(
                        channel="internacional",
                        category="CREDITO",
                        document=document,
                        line=line,
                        allocation=allocation,
                        person=person,
                        role="Ventas Internacionales",
                        currency="USD",
                        base=base,
                        rate=rate,
                        commission=base * rate,
                        rule_id="GOLDEN-INTERNACIONAL",
                        source_key=source_key,
                    )
                )
            if actual_flags[person]:
                actual.append(
                    _gold_row(
                        channel="internacional",
                        category="CREDITO",
                        document=document,
                        line=line,
                        allocation=allocation,
                        person=person,
                        role="Ventas Internacionales",
                        currency="USD",
                        base=base,
                        rate=rate,
                        commission=base * rate,
                        rule_id=f"INTL-2026:{person}",
                        source_key=source_key,
                    )
                )
    return expected, actual, exceptions, bronze


def run_historical_parity(
    channel: str,
    database: Path | str,
    root: Path | None = None,
) -> RunResult:
    """Ejecuta septiembre y persiste evidencia Bronze y resultados Gold."""
    del root  # Las rutas aprobadas son deliberadamente fijas respecto del repositorio.
    if channel == "nacional":
        path = NACIONAL_GOLDEN
        start, end, currency = date(2026, 9, 1), date(2026, 9, 30), "PEN"
        expected, actual, exceptions, bronze = _national_rows()
        authoritative_expected = to_decimal(
            cell_value(NACIONAL_GOLDEN, "RESUMEN COMISIONES", "E48")
        )
    elif channel == "internacional":
        path = INTERNACIONAL_GOLDEN
        start, end, currency = date(2026, 8, 20), date(2026, 9, 20), "USD"
        expected, actual, exceptions, bronze = _international_rows()
        authoritative_expected = sum(
            (row.commission_raw for row in expected), Decimal(0)
        )
    else:
        raise ValueError(f"unknown channel: {channel}")

    source_hash = file_sha256(path)
    snapshot_id = f"{channel}-2026-09-{source_hash[:16]}"
    expected_keys = {item.key for item in expected}
    classifications = {
        row.key: "elegibilidad" for row in actual if row.key not in expected_keys
    }
    differences = compare(expected, actual, classifications)
    detail_expected_total = sum((row.commission_raw for row in expected), Decimal(0))
    if quantize_money(detail_expected_total) != quantize_money(authoritative_expected):
        exceptions.append(
            {
                "key": f"{channel}-golden-reconciliation",
                "code": "GOLDEN_DETAIL_SUMMARY_MISMATCH",
                "blocking": True,
                "detail": (
                    f"Detalle={quantize_money(detail_expected_total)}; "
                    f"resumen={quantize_money(authoritative_expected)}"
                ),
            }
        )
    expected_total = authoritative_expected
    actual_total = sum((row.commission_raw for row in actual), Decimal(0))
    run_payload = {
        "channel": channel,
        "snapshot_id": snapshot_id,
        "source_hash": source_hash,
        "engine": "0.1.0",
        "ruleset": "2026-09.v1",
    }
    run_id = hashlib.sha256(sha256_json(run_payload).encode("ascii")).hexdigest()[:24]
    blocking = any(bool(item.get("blocking")) for item in exceptions)
    status = (
        "blocked"
        if blocking
        else ("parity" if not differences else "explained_differences")
    )
    result = RunResult(
        run_id=run_id,
        snapshot_id=snapshot_id,
        channel=channel,
        period_start=start,
        period_end=end,
        currency=currency,
        status=status,
        expected_total=expected_total,
        actual_total=actual_total,
        rows=actual,
        differences=differences,
        exceptions=exceptions,
        metadata={
            "golden_path": str(path.relative_to(ROOT)),
            "golden_sha256": source_hash,
            "expected_row_count": len(expected),
            "additional_closures_ready": False,
            "payable": False,
        },
    )
    repository = MedallionRepository(database)
    repository.store_snapshot(
        snapshot_id=snapshot_id,
        channel=channel,
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        source_path=str(path.relative_to(ROOT)),
        source_sha256=source_hash,
        records=[
            ("excel_row", f"{channel}:{index}", row)
            for index, row in enumerate(bronze, start=1)
        ],
    )
    repository.store_result(result)
    return result
