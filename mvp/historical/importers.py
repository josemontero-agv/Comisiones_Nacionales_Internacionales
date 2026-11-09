"""Lectores conservadores de Excel: no evalúan fórmulas ni alteran libros."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import openpyxl


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rows_with_header(
    path: Path, sheet: str, header_row: int = 1
) -> list[dict[str, Any]]:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    worksheet = workbook[sheet]
    iterator = worksheet.iter_rows(min_row=header_row, values_only=True)
    headers = [
        str(value).strip() if value is not None else f"__column_{index}"
        for index, value in enumerate(next(iterator))
    ]
    rows: list[dict[str, Any]] = []
    for excel_row, values in enumerate(iterator, start=header_row + 1):
        if not any(value is not None for value in values):
            continue
        item = {header: value for header, value in zip(headers, values, strict=False)}
        item["__excel_row"] = excel_row
        rows.append(item)
    workbook.close()
    return rows


def nacional_matrix(path: Path) -> dict[str, list[tuple[str, str | None, object]]]:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    worksheet = workbook["Tabla Comisiones"]
    matrix: dict[str, list[tuple[str, str | None, object]]] = {}
    roles = (
        ("Representante de Ventas", 2, 3),
        ("Jefe Tecnico", 4, 5),
        ("Jefe Comercial", 6, 7),
        ("Gerente", 8, 9),
    )
    for values in worksheet.iter_rows(min_row=2, values_only=True):
        if not values[0]:
            continue
        matrix[str(values[0]).strip().upper()] = [
            (
                role,
                None
                if values[person_index] in (None, 0, "0", "")
                else str(values[person_index]).strip(),
                values[rate_index],
            )
            for role, person_index, rate_index in roles
        ]
    workbook.close()
    return matrix


def cell_value(path: Path, sheet: str, cell: str) -> Any:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    value = workbook[sheet][cell].value
    workbook.close()
    return value
