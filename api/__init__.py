"""API delgada: lee Gold ya calculado y no ejecuta el motor."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from api.routes import blueprint
from mvp.infrastructure.working import database_url

ROOT = Path(__file__).resolve().parents[1]
_LOCAL_ORIGINS = ("http://127.0.0.1:3000", "http://localhost:3000")


def create_app(config: dict | None = None) -> Flask:
    load_dotenv(ROOT / ".env", override=False)
    app = Flask(__name__)
    app.json.ensure_ascii = False
    app.config.update(
        DATABASE_URL=database_url(),
        WEB_ORIGIN=os.environ.get("COMISIONES_WEB_ORIGIN", _LOCAL_ORIGINS[0]),
        ROOT=str(ROOT),
    )
    if config:
        app.config.update(config)
    app.register_blueprint(blueprint)

    @app.before_request
    def preflight():
        if request.method == "OPTIONS":
            response = app.make_response(("", 204))
            _apply_cors(app, response)
            return response
        return None

    @app.after_request
    def cors(response):
        _apply_cors(app, response)
        return response

    @app.errorhandler(Exception)
    def unexpected(exc: Exception):
        if isinstance(exc, HTTPException):
            return exc
        app.logger.exception("error de lectura: %s", type(exc).__name__)
        return jsonify(
            {
                "error": "error_interno",
                "payable": False,
                "pilot": True,
                "message": (
                    "No se pudo completar la lectura. La API no calculó comisiones "
                    "ni escribió en Odoo."
                ),
            }
        ), 500

    return app


def _apply_cors(app: Flask, response) -> None:
    origin = request.headers.get("Origin", "")
    allowed = {app.config["WEB_ORIGIN"], *_LOCAL_ORIGINS}
    if origin in allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["X-Comisiones-Pagable"] = "false"
