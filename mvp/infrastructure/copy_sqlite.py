"""Copia única del medallón SQLite hacia Supabase. No calcula comisiones."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from mvp.infrastructure.postgres.repository import PostgresMedallionRepository

_BATCH = 500


def copy_sqlite_gold(
    source: Path | str, repository: PostgresMedallionRepository
) -> dict[str, int]:
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(
            f"No existe el SQLite de origen en {path}. No se inventan filas."
        )
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        with repository.connect() as destination:
            counts = {
                "bronze_snapshot": _copy_snapshots(connection, destination),
                "bronze_record": _copy_table(
                    connection,
                    destination,
                    "SELECT snapshot_id, source_model, source_key, payload_json, payload_sha256 FROM bronze_record",
                    """
                    INSERT INTO raw.bronze_record
                    (snapshot_id, source_model, source_key, payload_json, payload_sha256)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (snapshot_id, source_model, source_key) DO NOTHING
                    """,
                ),
                "silver_record": _copy_table(
                    connection,
                    destination,
                    "SELECT snapshot_id, entity_type, entity_key, payload_json FROM silver_record",
                    """
                    INSERT INTO raw.silver_record
                    (snapshot_id, entity_type, entity_key, payload_json)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (snapshot_id, entity_type, entity_key) DO NOTHING
                    """,
                ),
                "gold_run": _copy_runs(connection, destination),
                "gold_commission_line": _copy_table(
                    connection,
                    destination,
                    "SELECT run_id, row_key, payload_json FROM gold_commission_line",
                    """
                    INSERT INTO gold.gold_commission_line (run_id, row_key, payload_json)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (run_id, row_key) DO NOTHING
                    """,
                ),
                "gold_collected_line": _copy_table(
                    connection,
                    destination,
                    "SELECT run_id, row_key, payload_json FROM gold_collected_line",
                    """
                    INSERT INTO gold.gold_collected_line (run_id, row_key, payload_json)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (run_id, row_key) DO NOTHING
                    """,
                ),
                "gold_difference": _copy_table(
                    connection,
                    destination,
                    """
                    SELECT run_id, difference_key, classification, payload_json
                    FROM gold_difference
                    """,
                    """
                    INSERT INTO gold.gold_difference
                    (run_id, difference_key, classification, payload_json)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (run_id, difference_key, classification) DO NOTHING
                    """,
                ),
                "gold_exception": _copy_table(
                    connection,
                    destination,
                    "SELECT run_id, exception_key, payload_json FROM gold_exception",
                    """
                    INSERT INTO gold.gold_exception (run_id, exception_key, payload_json)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (run_id, exception_key) DO NOTHING
                    """,
                ),
            }
    finally:
        connection.close()
    counts["payable"] = 0
    return counts


def _copy_snapshots(source: sqlite3.Connection, destination: Any) -> int:
    rows = source.execute(
        """
        SELECT snapshot_id, channel, period_start, period_end, source_path,
               source_sha256, loaded_at, status
        FROM bronze_snapshot
        """
    )
    copied = 0
    batch: list[tuple] = []
    for row in rows:
        batch.append(tuple(row))
        if len(batch) >= _BATCH:
            copied += _insert_snapshots(destination, batch)
            batch = []
    copied += _insert_snapshots(destination, batch)
    return copied


def _insert_snapshots(destination: Any, batch: list[tuple]) -> int:
    if not batch:
        return 0
    with destination.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO raw.bronze_snapshot
            (snapshot_id, channel, period_start, period_end, source_path,
             source_sha256, loaded_at, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (snapshot_id) DO NOTHING
            """,
            batch,
        )
    return len(batch)


def _copy_runs(source: sqlite3.Connection, destination: Any) -> int:
    rows = source.execute(
        """
        SELECT run_id, snapshot_id, channel, status, manifest_json, completed_at
        FROM gold_run
        """
    )
    copied = 0
    batch: list[tuple] = []
    for row in rows:
        manifest = json.loads(row["manifest_json"])
        manifest["payable"] = False
        batch.append(
            (
                row["run_id"],
                row["snapshot_id"],
                row["channel"],
                row["status"],
                json.dumps(manifest, ensure_ascii=False, sort_keys=True),
                row["completed_at"],
            )
        )
        if len(batch) >= _BATCH:
            copied += _insert_runs(destination, batch)
            batch = []
    copied += _insert_runs(destination, batch)
    return copied


def _insert_runs(destination: Any, batch: list[tuple]) -> int:
    if not batch:
        return 0
    with destination.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO gold.gold_run
            (run_id, snapshot_id, channel, status, manifest_json, completed_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_id) DO NOTHING
            """,
            batch,
        )
    return len(batch)


def _copy_table(
    source: sqlite3.Connection,
    destination: Any,
    select_sql: str,
    insert_sql: str,
) -> int:
    cursor = source.execute(select_sql)
    copied = 0
    while True:
        chunk = cursor.fetchmany(_BATCH)
        if not chunk:
            break
        with destination.cursor() as writer:
            writer.executemany(insert_sql, [tuple(row) for row in chunk])
        copied += len(chunk)
    return copied
