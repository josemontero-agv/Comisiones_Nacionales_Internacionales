"""Libro único para RRHH y Dirección, construido exclusivamente desde Gold."""

from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from mvp.infrastructure.sqlite import MedallionRepository

CATEGORIES = ("CONTADO", "CREDITO", "LETRAS")


def _style_sheet(worksheet: Any) -> None:
    fill = PatternFill("solid", fgColor="1F4E78")
    for cell in worksheet[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = fill
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    for column in worksheet.columns:
        width = min(max(len(str(cell.value or "")) for cell in column) + 2, 48)
        worksheet.column_dimensions[get_column_letter(column[0].column)].width = width


def _append_dicts(
    worksheet: Any, rows: list[dict[str, Any]], columns: list[str]
) -> None:
    worksheet.append(columns)
    for row in rows:
        worksheet.append([row.get(column) for column in columns])
    _style_sheet(worksheet)


def export_rrhh_workbook(database: Path | str, output: Path | str) -> Path:
    repository = MedallionRepository(database)
    manifests = repository.latest_manifests()
    if not manifests:
        raise RuntimeError("no existen corridas Gold para exportar")
    payloads = [
        repository.load_result_payload(str(manifest["run_id"]))
        for manifest in manifests
    ]

    summary: dict[tuple[str, str, str, str], dict[str, Decimal]] = defaultdict(
        lambda: {category: Decimal(0) for category in CATEGORIES}
    )
    detail: list[dict[str, Any]] = []
    differences: list[dict[str, Any]] = []
    exceptions: list[dict[str, Any]] = []
    for payload in payloads:
        manifest = payload["manifest"]
        for row in payload["rows"]:
            category = str(row["category"])
            key = (
                str(row["channel"]),
                str(row["currency"]),
                str(row["person"]),
                str(row["role"]),
            )
            summary[key][category] = summary[key].get(category, Decimal(0)) + Decimal(
                str(row["commission_presented"])
            )
            detail.append(row)
        for row in payload["differences"]:
            differences.append({"channel": manifest["channel"], **row})
        for row in payload["exceptions"]:
            exceptions.append({"channel": manifest["channel"], **row})

    workbook = Workbook()
    resumen = workbook.active
    resumen.title = "Resumen RRHH"
    resumen.append(["Canal", "Moneda", "Persona", "Puesto", *CATEGORIES, "TOTAL"])
    for key in sorted(summary):
        values = summary[key]
        total = sum(values.values(), Decimal(0))
        resumen.append(
            [*key, *(float(values[category]) for category in CATEGORIES), float(total)]
        )
    _style_sheet(resumen)
    for row in resumen.iter_rows(min_row=2, min_col=5, max_col=8):
        for cell in row:
            cell.number_format = "#,##0.00"

    detail_columns = [
        "channel",
        "category",
        "document",
        "line",
        "allocation",
        "person",
        "role",
        "currency",
        "base_raw",
        "rate",
        "commission_raw",
        "commission_presented",
        "rule_id",
        "source_key",
    ]
    _append_dicts(workbook.create_sheet("Detalle"), detail, detail_columns)
    _append_dicts(
        workbook.create_sheet("Excepciones"),
        exceptions,
        ["channel", "key", "code", "blocking", "detail", "amount"],
    )
    _append_dicts(
        workbook.create_sheet("Diferencias"),
        differences,
        ["channel", "key", "classification", "expected", "actual", "delta", "detail"],
    )
    manifest_sheet = workbook.create_sheet("Manifest")
    manifest_sheet.append(["Canal", "Manifest JSON"])
    for manifest in manifests:
        manifest_sheet.append(
            [
                manifest["channel"],
                json.dumps(manifest, ensure_ascii=False, sort_keys=True),
            ]
        )
    _style_sheet(manifest_sheet)

    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(destination)
    return destination
