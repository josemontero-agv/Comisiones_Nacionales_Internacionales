"""Libro de un solo canal para RRHH y su instancia aprobadora, desde Gold."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from mvp.application.reporting import (
    CATEGORIES,
    build_collected_by_line,
    build_commission_pivot,
)
from mvp.infrastructure.sqlite import MedallionRepository


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


def export_rrhh_workbook(
    database: Path | str,
    output: Path | str,
    channel: str,
    *,
    bronze_origin: str | None = None,
    repository: Any | None = None,
) -> Path:
    """Escribe el libro de un solo canal.

    `repository` permite leer el mismo contrato desde Postgres/Supabase sin abrir
    SQLite. Si no se pasa, el comportamiento sigue siendo el adaptador SQLite.
    """
    if channel not in {"nacional", "internacional"}:
        raise ValueError(f"canal no soportado: {channel}")
    if repository is None:
        repository = MedallionRepository(database)
    manifests = [
        manifest
        for manifest in repository.latest_manifests(bronze_origin=bronze_origin)
        if manifest["channel"] == channel
    ]
    if not manifests:
        raise RuntimeError(f"no existe una corrida Gold para {channel}")
    payloads = [
        repository.load_result_payload(str(manifest["run_id"]))
        for manifest in manifests
    ]

    detail: list[dict[str, Any]] = []
    differences: list[dict[str, Any]] = []
    exceptions: list[dict[str, Any]] = []
    for payload in payloads:
        manifest = payload["manifest"]
        detail.extend(payload["rows"])
        differences.extend(payload["differences"])
        exceptions.extend(payload["exceptions"])

    workbook = Workbook()
    resumen = workbook.active
    resumen.title = "RESUMEN COMISIONES"
    pivot = build_commission_pivot(payloads)
    resumen.append(["Puesto", "Línea comercial", "Nombre", *CATEGORIES, "Total"])
    for row in pivot:
        resumen.append(
            [
                row["Puesto"],
                row["Línea comercial"],
                row["Nombre"],
                *(float(row[category]) for category in CATEGORIES),
                float(row["Total"]),
            ]
        )
    _style_sheet(resumen)
    for row in resumen.iter_rows(min_row=2, min_col=4, max_col=7):
        for cell in row:
            cell.number_format = "#,##0.00"

    cobrado = workbook.create_sheet("Cobrado por linea")
    cobrado.append(
        [
            "Moneda",
            "Línea comercial",
            "Cobrado CONTADO",
            "Cobrado CREDITO",
            "Cobrado LETRAS",
            "Total cobrado",
            "Comisión CONTADO",
            "Comisión CREDITO",
            "Comisión LETRAS",
            "Total comisión",
        ]
    )
    for row in build_collected_by_line(payloads):
        cobrado.append(
            [
                row["Moneda"],
                row["Línea comercial"],
                *(float(row[f"Cobrado {category}"]) for category in CATEGORIES),
                float(row["Total cobrado"]),
                *(float(row[f"Comisión {category}"]) for category in CATEGORIES),
                float(row["Total comisión"]),
            ]
        )
    _style_sheet(cobrado)
    for row in cobrado.iter_rows(min_row=2, min_col=3, max_col=10):
        for cell in row:
            cell.number_format = "#,##0.00"

    detail_columns = [
        "channel",
        "category",
        "document",
        "line",
        "allocation",
        "commercial_line",
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
        ["key", "code", "blocking", "detail", "amount"],
    )
    _append_dicts(
        workbook.create_sheet("Diferencias"),
        differences,
        ["key", "classification", "expected", "actual", "delta", "detail"],
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
    try:
        workbook.save(destination)
        return destination
    except PermissionError:
        fallback = Path(database).parent / destination.name
        fallback.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(fallback)
        return fallback
