"""Lectura de cierres Gold. No aplica porcentajes, prorrateo ni roles."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg

from mvp.application.reporting import build_commission_pivot
from mvp.domain.money import decimal_text
from mvp.export import export_rrhh_workbook
from mvp.infrastructure.postgres.repository import (
    PostgresMedallionRepository,
    PostgresSchemaMissing,
)

CHANNELS = ("nacional", "internacional")
PILOT_NOTICE = (
    "Septiembre 2026 es un piloto y no es pagable. Faltan 1–2 cierres adicionales "
    "por canal. Esta API no entrega a nómina y ningún periodo nace aprobado. "
    "Nacional e Internacional no se mezclan."
)


class GoldReadError(Exception):
    def __init__(self, message: str, status: int = 404) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def open_source(config: dict[str, Any]) -> tuple[Any | None, dict[str, Any]]:
    dsn = str(config.get("DATABASE_URL") or "").strip()
    meta = {
        "backend": "supabase",
        "ready": False,
        "payable": False,
        "pilot": True,
    }
    if not dsn:
        meta["message"] = (
            "Falta DATABASE_URL. La API lee Gold solo en Supabase y no abre SQLite."
        )
        return None, meta
    repository = PostgresMedallionRepository(dsn)
    try:
        repository.ping()
    except PostgresSchemaMissing as exc:
        meta["message"] = str(exc)
        return None, meta
    except psycopg.Error:
        meta["message"] = (
            "No se pudo conectar a Supabase con DATABASE_URL. Revise la cadena "
            "y que el proyecto esté activo. La API no calculó comisiones."
        )
        return None, meta
    meta["ready"] = True
    meta["message"] = (
        "Leyendo Gold en Supabase. Septiembre sigue siendo piloto y no pagable."
    )
    return repository, meta


def list_closures(repository: Any | None, meta: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "payable": False,
        "pilot": True,
        "payroll_delivery": False,
        "notice": PILOT_NOTICE,
        "backend": meta.get("backend"),
        "database_ready": bool(meta.get("ready")),
        "message": meta.get("message"),
        "cierres": [],
    }
    if repository is None:
        return body
    latest = {
        str(item["channel"]): item for item in repository.latest_manifests()
    }
    for channel in CHANNELS:
        manifest = latest.get(channel)
        if manifest is None:
            body["cierres"].append(
                {
                    "channel": channel,
                    "has_gold": False,
                    "payable": False,
                    "message": (
                        f"No hay Gold en Supabase para {channel}. La API no lo calcula."
                    ),
                }
            )
            continue
        body["cierres"].append(_closure(manifest))
    return body


def channel_summary(repository: Any | None, meta: dict[str, Any], channel: str) -> dict[str, Any]:
    _require_channel(channel)
    if repository is None:
        raise GoldReadError(str(meta.get("message")), status=409)
    manifest = _latest_manifest(repository, channel)
    payload = repository.load_result_payload(str(manifest["run_id"]))
    if str(payload["manifest"].get("channel")) != channel:
        raise GoldReadError(
            f"La corrida de {channel} no coincide con el canal pedido.",
            status=409,
        )
    pivot = [
        _pivot_row(row) for row in build_commission_pivot([payload])
    ]
    exceptions = list(payload["exceptions"])
    return {
        "payable": False,
        "pilot": True,
        "payroll_delivery": False,
        "notice": PILOT_NOTICE,
        "backend": meta.get("backend"),
        "channel": channel,
        "status": manifest.get("status"),
        "period_start": manifest.get("period_start"),
        "period_end": manifest.get("period_end"),
        "run_id": manifest.get("run_id"),
        "bronze_origin": manifest.get("bronze_origin"),
        "manifest_payable": bool(manifest.get("payable")),
        "additional_closures_ready": bool(manifest.get("additional_closures_ready")),
        "totals": {
            "currency": manifest.get("currency"),
            "expected": manifest.get("expected_total"),
            "calculated": manifest.get("actual_total"),
            "difference": manifest.get("delta"),
        },
        "persona_puesto": pivot,
        "detalle": payload["rows"],
        "excepciones": exceptions,
        "diferencias": payload["differences"],
        "counts": {
            "persona_puesto": len(pivot),
            "detalle": len(payload["rows"]),
            "excepciones": len(exceptions),
            "excepciones_bloqueantes": sum(
                1 for item in exceptions if item.get("blocking") is True
            ),
            "diferencias": len(payload["differences"]),
        },
    }


def export_channel(
    repository: Any | None,
    meta: dict[str, Any],
    channel: str,
    destination: Path,
) -> Path:
    _require_channel(channel)
    if repository is None:
        raise GoldReadError(str(meta.get("message")), status=409)
    _latest_manifest(repository, channel)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        return export_rrhh_workbook(
            destination.parent,
            destination,
            channel,
            repository=repository,
        )
    except RuntimeError as exc:
        raise GoldReadError(str(exc), status=404) from exc


def _require_channel(channel: str) -> None:
    if channel not in CHANNELS:
        raise GoldReadError(
            "Canal no soportado. Use nacional o internacional, nunca ambos juntos.",
            status=400,
        )


def _latest_manifest(repository: Any, channel: str) -> dict[str, Any]:
    matches = [
        item
        for item in repository.latest_manifests()
        if item.get("channel") == channel
    ]
    if not matches:
        raise GoldReadError(
            f"No hay Gold en Supabase para {channel}. Esta ruta no calcula "
            "comisiones ni usa el otro canal.",
            status=404,
        )
    return matches[0]


def _closure(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "channel": manifest.get("channel"),
        "has_gold": True,
        "payable": False,
        "manifest_payable": bool(manifest.get("payable")),
        "status": manifest.get("status"),
        "currency": manifest.get("currency"),
        "period_start": manifest.get("period_start"),
        "period_end": manifest.get("period_end"),
        "run_id": manifest.get("run_id"),
        "bronze_origin": manifest.get("bronze_origin"),
        "expected_total": manifest.get("expected_total"),
        "actual_total": manifest.get("actual_total"),
        "delta": manifest.get("delta"),
        "difference_count": manifest.get("difference_count"),
        "exception_count": manifest.get("exception_count"),
    }


def _pivot_row(row: dict[str, Any]) -> dict[str, str]:
    public: dict[str, str] = {}
    for key, value in row.items():
        public[str(key)] = decimal_text(value) if isinstance(value, Decimal) else str(value)
    return public
