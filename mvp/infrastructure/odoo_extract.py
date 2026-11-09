"""Extractor Bronze genérico sobre el cliente Odoo de solo lectura."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from mvp.application.contracts import canonical_json
from mvp.infrastructure.odoo_readonly import OdooReadOnlyClient
from mvp.infrastructure.sqlite import MedallionRepository


@dataclass(frozen=True, slots=True)
class ExtractionSpec:
    model: str
    domain: list
    fields: tuple[str, ...]


def extract_snapshot(
    client: OdooReadOnlyClient,
    repository: MedallionRepository,
    channel: str,
    period_start: date,
    period_end: date,
    specs: tuple[ExtractionSpec, ...],
) -> str:
    """Extrae campos explícitos, pagina por id y cierra un snapshot inmutable."""
    records: list[tuple[str, str, dict]] = []
    for spec in specs:
        if "id" not in spec.fields:
            raise ValueError(f"{spec.model}: fields must include id")
        for row in client.search_read_paged(spec.model, spec.domain, spec.fields):
            records.append((spec.model, str(row["id"]), row))
    payload_hash = hashlib.sha256(
        canonical_json(sorted(records, key=lambda item: (item[0], item[1]))).encode(
            "utf-8"
        )
    ).hexdigest()
    snapshot_id = f"odoo-{channel}-{period_start.isoformat()}-{payload_hash[:16]}"
    repository.store_snapshot(
        snapshot_id,
        channel,
        period_start.isoformat(),
        period_end.isoformat(),
        "odoo:xmlrpc-readonly",
        payload_hash,
        records,
    )
    return snapshot_id


def repository_for(database: Path | str) -> MedallionRepository:
    return MedallionRepository(database)
