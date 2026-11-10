"""Adaptador Postgres/Supabase del mismo contrato que el repositorio SQLite."""

from mvp.infrastructure.postgres.repository import PostgresMedallionRepository

__all__ = ["PostgresMedallionRepository"]
