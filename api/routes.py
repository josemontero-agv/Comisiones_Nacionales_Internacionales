"""Rutas de lectura y descarga. No contienen fórmulas de comisión."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, send_file

from api.gold_read import (
    GoldReadError,
    channel_summary,
    export_channel,
    list_closures,
    open_source,
)

blueprint = Blueprint("comisiones", __name__)


@blueprint.get("/health")
def health():
    _repository, meta = open_source(current_app.config)
    return jsonify(
        {
            "status": "ok",
            "payable": False,
            "pilot": True,
            "backend": meta.get("backend"),
            "database_ready": bool(meta.get("ready")),
            "message": meta.get("message"),
        }
    )


@blueprint.get("/api/cierres")
def cierres():
    repository, meta = open_source(current_app.config)
    return jsonify(list_closures(repository, meta))


@blueprint.get("/api/canales/<channel>/resumen")
def resumen(channel: str):
    repository, meta = open_source(current_app.config)
    try:
        return jsonify(channel_summary(repository, meta, channel))
    except GoldReadError as exc:
        return _gold_error(exc)


@blueprint.get("/api/canales/<channel>/xlsx")
def xlsx(channel: str):
    repository, meta = open_source(current_app.config)
    root = Path(current_app.config["ROOT"])
    destination = root / "var" / "api-exports" / f"comisiones_{channel}_septiembre_2026.xlsx"
    try:
        written = export_channel(repository, meta, channel, destination)
    except GoldReadError as exc:
        return _gold_error(exc)
    response = send_file(
        written,
        as_attachment=True,
        download_name=f"comisiones_{channel}_septiembre_2026.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response.headers["X-Comisiones-Pagable"] = "false"
    return response


def _gold_error(exc: GoldReadError):
    return jsonify(
        {
            "error": "sin_gold" if exc.status == 404 else "lectura",
            "payable": False,
            "pilot": True,
            "payroll_delivery": False,
            "message": exc.message,
        }
    ), exc.status
