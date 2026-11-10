"""Repositorio de trabajo: solo Postgres/Supabase, vía DATABASE_URL."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from mvp.infrastructure.postgres.repository import PostgresMedallionRepository

ROOT = Path(__file__).resolve().parents[2]


def database_url() -> str:
    """La línea de .env gana sobre un DATABASE_URL viejo del proceso."""
    load_dotenv(ROOT / ".env", override=False)
    env_path = ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    return os.environ.get("DATABASE_URL", "").strip()


def open_working_repository() -> PostgresMedallionRepository:
    dsn = database_url()
    if not dsn:
        raise RuntimeError(
            "Falta DATABASE_URL. La aplicación ya no usa SQLite. "
            "Ponga la cadena postgresql:// del proyecto en .env, sin commitearla."
        )
    repository = PostgresMedallionRepository(dsn)
    repository.ping()
    return repository
