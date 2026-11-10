"""Health sin base de trabajo."""

from __future__ import annotations

from api import create_app


def test_health_sin_database_url_no_es_pagable() -> None:
    app = create_app({"DATABASE_URL": ""})
    response = app.test_client().get("/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["payable"] is False
    assert body["database_ready"] is False
    assert body["backend"] == "supabase"
