"""Ejecución reproducible de los cierres históricos aprobados."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from mvp.application.contracts import (
    CollectedLine,
    GoldRow,
    ParityDifference,
    RunResult,
    sha256_json,
)
from mvp.domain.commissions import letter_line_commission, payment_line_commission
from mvp.domain.money import quantize_money, to_decimal
from mvp.domain.rules import load_ruleset_file
from mvp.historical.importers import (
    cell_value,
    file_sha256,
    nacional_matrix,
    rows_with_header,
)
from mvp.historical.parity import compare
from mvp.infrastructure.sqlite import MedallionRepository

ROOT = Path(__file__).resolve().parents[2]
RULESET_PATH = ROOT / "mvp/rulesets/2026-09.v1.json"
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
    commercial_line: str,
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
        commercial_line=commercial_line,
    )


def _national_rows() -> tuple[
    list[GoldRow],
    list[GoldRow],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[CollectedLine],
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
    collected: list[CollectedLine] = []
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
            commercial_line = (
                _text(row.get("Linea Comercial")).upper()
                or matrix_key.partition("/")[0]
            )
            if category == "LETRAS":
                base, _ = letter_line_commission(paid, subtotal, total, Decimal(0))
            else:
                base, _ = payment_line_commission(paid, subtotal, total, Decimal(0))
            collected.append(
                CollectedLine(
                    channel="nacional",
                    category=category,
                    commercial_line=commercial_line,
                    document=document,
                    line=line,
                    allocation=allocation,
                    currency="PEN",
                    collected_raw=base,
                    source_key=source_key,
                )
            )
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
                            commercial_line=commercial_line,
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
                commission = base * rate
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
                        commercial_line=commercial_line,
                    )
                )
    return expected, actual, exceptions, bronze, collected


def _flag(row: dict[str, Any], column: str) -> bool:
    return _text(row.get(column)).upper() == "SI"


def _international_rows() -> tuple[
    list[GoldRow],
    list[GoldRow],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[CollectedLine],
]:
    ruleset = load_ruleset_file(RULESET_PATH)
    rows = rows_with_header(INTERNACIONAL_GOLDEN, "DETALLE DE COBRANZA ", header_row=3)
    expected: list[GoldRow] = []
    actual: list[GoldRow] = []
    bronze: list[dict[str, Any]] = []
    collected: list[CollectedLine] = []
    exceptions: list[dict[str, Any]] = [
        {
            "key": "INTL-LUIS-SCOPE",
            "code": "MISSING_COUNTRY_ISO_IN_SOURCE",
            "blocking": True,
            "detail": "El catálogo América/LATAM está aprobado, pero el Excel histórico no incluye el ISO necesario para evaluar a Luis.",
        },
        {
            "key": "INTL-MAYUMI-SCOPE",
            "code": "MISSING_COUNTRY_ISO_IN_SOURCE",
            "blocking": True,
            "detail": "El catálogo América/LATAM está aprobado, pero el Excel histórico no incluye el ISO necesario para evaluar a Mayumi.",
        },
        {
            "key": "OVR-IVONNE-F522-ATREVIA-2026-09",
            "code": "OVERRIDE_SOURCE_OUTSIDE_CYCLE",
            "blocking": False,
            "detail": (
                "Regla aprobada por Sandra y aplicada por José: solo "
                "F F15-00000522 + 31392PER00007. No aparece en el Excel "
                "20-ago–20-sep; Odoo solo lectura confirmó factura 2026-09-28, "
                "fuera del ciclo, por lo que no se inventa monto de comisión."
            ),
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
        collected.append(
            CollectedLine(
                channel="internacional",
                category="CREDITO",
                commercial_line=commercial_line,
                document=document,
                line=line,
                allocation=allocation,
                currency="USD",
                collected_raw=base,
                source_key=source_key,
            )
        )
        payment_value = row.get("FECHA DE PAGO")
        payment_day = (
            payment_value.date()
            if hasattr(payment_value, "date")
            else date.fromisoformat(_date_text(payment_value))
        )
        description = _text(row.get("Description"))
        ivonne_override = next(
            (
                override
                for override in ruleset.period_overrides
                if override.beneficiary == "Ivonne Panta"
                and override.matches(
                    day=payment_day,
                    invoice_ref=document,
                    product_code=product,
                    product_name=description,
                )
            ),
            None,
        )
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
            "Ivonne Panta": ivonne_override is not None,
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
                        commercial_line=commercial_line,
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
                        rule_id=(
                            ivonne_override.rule_id
                            if person == "Ivonne Panta" and ivonne_override
                            else f"INTL-2026:{person}"
                        ),
                        source_key=source_key,
                        commercial_line=commercial_line,
                    )
                )
    return expected, actual, exceptions, bronze, collected


def run_historical_parity(
    channel: str,
    database: Path | str | None = None,
    root: Path | None = None,
    *,
    repository: Any | None = None,
) -> RunResult:
    """Ejecuta septiembre y persiste evidencia Bronze y resultados Gold."""
    del root  # Las rutas aprobadas son deliberadamente fijas respecto del repositorio.
    if channel == "nacional":
        path = NACIONAL_GOLDEN
        start, end, currency = date(2026, 9, 1), date(2026, 9, 30), "PEN"
        expected, actual, exceptions, bronze, collected = _national_rows()
        authoritative_expected = to_decimal(
            cell_value(NACIONAL_GOLDEN, "RESUMEN COMISIONES", "E48")
        )
    elif channel == "internacional":
        path = INTERNACIONAL_GOLDEN
        start, end, currency = date(2026, 8, 20), date(2026, 9, 20), "USD"
        expected, actual, exceptions, bronze, collected = _international_rows()
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
    if channel == "nacional":
        reference_presented = quantize_money(authoritative_expected)
        calculated_presented = sum(
            (row.commission_presented for row in actual), Decimal(0)
        )
        differences.append(
            ParityDifference(
                key="nacional|TOTAL|REFERENCIA_VS_CALCULADO_PRESENTADO",
                classification="base_prorrateada_y_redondeo_presentacion",
                expected=reference_presented,
                actual=calculated_presented,
                delta=calculated_presented - reference_presented,
                detail=(
                    "La columna G del usuario es referencia menos calculado: 199.33 "
                    "(74,710.24 - 74,510.91). Deltas visibles por persona: Bravo "
                    "10.05; Ríos PETMEDICA 24.87 (no INTERPET); López 0.02; Tauca "
                    "-0.08; Hoyos -0.03; Calderón 13.54; Chinchay 51.37; Paredes "
                    "0.06; Durán 16.28; Bendezú 18.24; Espinoza 6.49; Arias 13.03; "
                    "Mera 2.49; Quea -0.06; Ramos -0.03; Sánchez 5.39; Tomás 0.02; "
                    "Vílchez 18.33; Rojas 56.45; Campos -0.03; Gutiérrez 6.80; "
                    "Francisco Pérez -0.11; Beltrán -0.13; De la Cruz 55.12; "
                    "Plasencia -0.01. Esos renglones suman 298.06; el pivote de "
                    "referencia omite a Chaman (98.73) aunque el detalle sí lo "
                    "calcula, dejando 199.33 netos. El resto proviene del prorrateo "
                    "por cobro real frente al atajo histórico y del redondeo por "
                    "línea: 0.65 separa el total crudo 74,510.25 de la suma "
                    "presentada. No es 7022101: esta corrida Excel no recibe cuentas."
                ),
            )
        )
        chaman_presented = sum(
            (
                row.commission_presented
                for row in actual
                if row.person == "CHAMAN COMOTTO, EDUARDO EDGARDO"
            ),
            Decimal(0),
        )
        differences.append(
            ParityDifference(
                key="nacional|PIVOT|CHAMAN_OMITIDO",
                classification="dato_fuente_pivot",
                expected=Decimal(0),
                actual=chaman_presented,
                delta=chaman_presented,
                detail=(
                    "El detalle COMISIONA y la matriz EQUESTRIA/LIMA calculan a "
                    "Chaman, pero RESUMEN COMISIONES no muestra al beneficiario. "
                    "Este desfase del pivote compensa 98.73 de los 298.06 visibles."
                ),
            )
        )
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
        "ruleset_sha256": load_ruleset_file(RULESET_PATH).sha256,
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
        collected_rows=collected,
        differences=differences,
        exceptions=exceptions,
        metadata={
            "golden_path": str(path.relative_to(ROOT)),
            "golden_sha256": source_hash,
            "bronze_origin": "excel",
            "bronze_loader": "mvp.historical.runner.run_historical_parity",
            "expected_row_count": len(expected),
            "additional_closures_ready": False,
            "payable": False,
            "zero_commission_people": (
                [
                    {
                        "person": "Mayumi Garcilazo",
                        "role": "Jefe Tecnico Comercial Latinoamerica Avivet",
                        "currency": "USD",
                        "rule_id": "INTL-MAYUMI-AVIVET-LATAM-V1",
                        "reason": "El Excel histórico de septiembre no incluye ISO de país; septiembre = 0.",
                    }
                ]
                if channel == "internacional"
                else []
            ),
        },
    )
    if repository is None:
        if database is None:
            raise ValueError("run_historical_parity necesita un repositorio o una base desechable")
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
