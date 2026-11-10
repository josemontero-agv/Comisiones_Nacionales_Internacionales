"""Repositorio Postgres con el mismo contrato que MedallionRepository.

No calcula comisiones. La cadena de conexión llega por argumento (DATABASE_URL en
el servidor) y no se registra. `prepare_threshold=None` permite el pooler de
Supabase en modo transacción, que no admite prepared statements.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

from mvp.application.contracts import RunResult, canonical_json


class PostgresSchemaMissing(RuntimeError):
    """El proyecto aún no tiene aplicadas las tablas raw/gold."""


class PostgresMedallionRepository:
    def __init__(self, dsn: str) -> None:
        if not dsn or "://" not in dsn:
            raise ValueError("la cadena de Postgres está vacía o no es una URL")
        self.dsn = dsn

    @contextmanager
    def connect(self) -> Iterator[psycopg.Connection]:
        connection = psycopg.connect(
            self.dsn,
            prepare_threshold=None,
            row_factory=dict_row,
            application_name="comisiones-api",
            connect_timeout=10,
            sslmode="require",
        )
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def ping(self) -> None:
        """Comprueba conexión y que el manifiesto Gold ya exista. No aplica DDL."""
        with self.connect() as connection:
            missing = connection.execute(
                """
                SELECT name
                FROM (VALUES
                    ('gold.gold_run'),
                    ('gold.gold_commission_line'),
                    ('gold.gold_difference'),
                    ('gold.gold_exception'),
                    ('raw.bronze_snapshot')
                ) AS expected(name)
                WHERE to_regclass(name) IS NULL
                """
            ).fetchall()
        if missing:
            names = ", ".join(str(row["name"]) for row in missing)
            raise PostgresSchemaMissing(
                "Supabase respondió, pero falta el esquema del piloto "
                f"({names}). Aplique supabase/migrations/"
                "20261110154000_raw_gold_contract.sql en el SQL Editor. "
                "Esta API no crea tablas ni calcula comisiones."
            )

    def store_snapshot(
        self,
        snapshot_id: str,
        channel: str,
        period_start: str,
        period_end: str,
        source_path: str,
        source_sha256: str,
        records: list[tuple[str, str, dict[str, Any]]],
    ) -> None:
        loaded_at = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO raw.bronze_snapshot
                (snapshot_id, channel, period_start, period_end, source_path,
                 source_sha256, loaded_at, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'closed')
                ON CONFLICT (snapshot_id) DO NOTHING
                """,
                (
                    snapshot_id,
                    channel,
                    period_start,
                    period_end,
                    source_path,
                    source_sha256,
                    loaded_at,
                ),
            )
            _executemany(connection, 
                """
                INSERT INTO raw.bronze_record
                (snapshot_id, source_model, source_key, payload_json, payload_sha256)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (snapshot_id, source_model, source_key) DO NOTHING
                """,
                [
                    (
                        snapshot_id,
                        model,
                        key,
                        canonical_json(payload),
                        hashlib.sha256(
                            canonical_json(payload).encode("utf-8")
                        ).hexdigest(),
                    )
                    for model, key, payload in records
                ],
            )

    def store_result(self, result: RunResult) -> None:
        manifest = result.manifest()
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM gold.gold_commission_line WHERE run_id = %s",
                (result.run_id,),
            )
            connection.execute(
                "DELETE FROM gold.gold_collected_line WHERE run_id = %s",
                (result.run_id,),
            )
            connection.execute(
                "DELETE FROM gold.gold_difference WHERE run_id = %s",
                (result.run_id,),
            )
            connection.execute(
                "DELETE FROM gold.gold_exception WHERE run_id = %s",
                (result.run_id,),
            )
            connection.execute(
                "DELETE FROM gold.gold_run WHERE run_id = %s",
                (result.run_id,),
            )
            connection.execute(
                """
                INSERT INTO gold.gold_run
                (run_id, snapshot_id, channel, status, manifest_json, completed_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    result.run_id,
                    result.snapshot_id,
                    result.channel,
                    result.status,
                    canonical_json(manifest),
                    datetime.now(UTC).isoformat(),
                ),
            )
            _executemany(connection, 
                """
                INSERT INTO gold.gold_commission_line (run_id, row_key, payload_json)
                VALUES (%s, %s, %s)
                """,
                [
                    (result.run_id, row.key, canonical_json(row.contract()))
                    for row in result.rows
                ],
            )
            _executemany(connection, 
                """
                INSERT INTO gold.gold_collected_line (run_id, row_key, payload_json)
                VALUES (%s, %s, %s)
                """,
                [
                    (result.run_id, row.key, canonical_json(row.contract()))
                    for row in result.collected_rows
                ],
            )
            _executemany(connection, 
                """
                INSERT INTO gold.gold_difference
                (run_id, difference_key, classification, payload_json)
                VALUES (%s, %s, %s, %s)
                """,
                [
                    (
                        result.run_id,
                        diff.key,
                        diff.classification,
                        canonical_json(diff),
                    )
                    for diff in result.differences
                ],
            )
            _executemany(connection, 
                """
                INSERT INTO gold.gold_exception (run_id, exception_key, payload_json)
                VALUES (%s, %s, %s)
                """,
                [
                    (
                        result.run_id,
                        str(item.get("key", index)),
                        canonical_json(item),
                    )
                    for index, item in enumerate(result.exceptions)
                ],
            )

    def store_silver_records(
        self,
        snapshot_id: str,
        records: list[tuple[str, str, dict[str, Any]]],
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM raw.silver_record WHERE snapshot_id = %s",
                (snapshot_id,),
            )
            _executemany(connection, 
                """
                INSERT INTO raw.silver_record
                (snapshot_id, entity_type, entity_key, payload_json)
                VALUES (%s, %s, %s, %s)
                """,
                [
                    (snapshot_id, entity_type, entity_key, canonical_json(payload))
                    for entity_type, entity_key, payload in records
                ],
            )

    def snapshot_counts(self, snapshot_id: str) -> dict[str, int]:
        with self.connect() as connection:
            bronze = connection.execute(
                "SELECT COUNT(*) AS count FROM raw.bronze_record WHERE snapshot_id = %s",
                (snapshot_id,),
            ).fetchone()
            silver = connection.execute(
                "SELECT COUNT(*) AS count FROM raw.silver_record WHERE snapshot_id = %s",
                (snapshot_id,),
            ).fetchone()
        return {
            "bronze": int(bronze["count"] if bronze else 0),
            "silver": int(silver["count"] if silver else 0),
        }

    def latest_snapshot(
        self,
        channel: str,
        period_start: str,
        period_end: str,
        source_path: str,
    ) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT snapshot_id FROM raw.bronze_snapshot
                WHERE channel = %s AND period_start = %s AND period_end = %s
                  AND source_path = %s AND status = 'closed'
                ORDER BY loaded_at DESC
                LIMIT 1
                """,
                (channel, period_start, period_end, source_path),
            ).fetchone()
        return str(row["snapshot_id"]) if row else None

    def load_snapshot_records(
        self, snapshot_id: str
    ) -> list[tuple[str, dict[str, Any]]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT source_model, payload_json FROM raw.bronze_record
                WHERE snapshot_id = %s
                ORDER BY source_model, source_key
                """,
                (snapshot_id,),
            ).fetchall()
        return [
            (str(row["source_model"]), json.loads(row["payload_json"])) for row in rows
        ]

    def latest_manifests(
        self, bronze_origin: str | None = None
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT manifest_json FROM gold.gold_run
                ORDER BY completed_at DESC, run_id DESC
                """
            ).fetchall()
        selected: dict[str, dict[str, Any]] = {}
        for row in rows:
            manifest = json.loads(row["manifest_json"])
            if bronze_origin and manifest.get("bronze_origin") != bronze_origin:
                continue
            selected.setdefault(str(manifest["channel"]), manifest)
        return [selected[channel] for channel in sorted(selected)]

    def load_result_payload(self, run_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            run = connection.execute(
                "SELECT manifest_json FROM gold.gold_run WHERE run_id = %s",
                (run_id,),
            ).fetchone()
            if run is None:
                raise KeyError(run_id)
            lines = connection.execute(
                """
                SELECT payload_json FROM gold.gold_commission_line
                WHERE run_id = %s ORDER BY row_key
                """,
                (run_id,),
            ).fetchall()
            collected_lines = connection.execute(
                """
                SELECT payload_json FROM gold.gold_collected_line
                WHERE run_id = %s ORDER BY row_key
                """,
                (run_id,),
            ).fetchall()
            differences = connection.execute(
                """
                SELECT payload_json FROM gold.gold_difference
                WHERE run_id = %s
                ORDER BY difference_key, classification
                """,
                (run_id,),
            ).fetchall()
            exceptions = connection.execute(
                """
                SELECT payload_json FROM gold.gold_exception
                WHERE run_id = %s ORDER BY exception_key
                """,
                (run_id,),
            ).fetchall()
        return {
            "manifest": json.loads(run["manifest_json"]),
            "rows": [_load_json(row["payload_json"]) for row in lines],
            "collected_rows": [
                _load_json(row["payload_json"]) for row in collected_lines
            ],
            "differences": [_load_json(row["payload_json"]) for row in differences],
            "exceptions": [_load_json(row["payload_json"]) for row in exceptions],
        }


def _executemany(connection: psycopg.Connection, sql: str, rows: list) -> None:
    with connection.cursor() as cursor:
        cursor.executemany(sql, rows)


def _load_json(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value
