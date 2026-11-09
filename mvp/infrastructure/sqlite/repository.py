"""Repositorio transaccional para Bronze, Silver y Gold."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mvp.application.contracts import RunResult, canonical_json


class MedallionRepository:
    def __init__(self, database: Path | str) -> None:
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._schema = (
            Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        )
        with self.connect() as connection:
            connection.executescript(self._schema)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

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
                INSERT OR IGNORE INTO bronze_snapshot
                (snapshot_id, channel, period_start, period_end, source_path, source_sha256, loaded_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'closed')
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
            for model, key, payload in records:
                text = canonical_json(payload)
                connection.execute(
                    """
                    INSERT OR IGNORE INTO bronze_record
                    (snapshot_id, source_model, source_key, payload_json, payload_sha256)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        model,
                        key,
                        text,
                        hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    ),
                )

    def store_result(self, result: RunResult) -> None:
        manifest = result.manifest()
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM gold_commission_line WHERE run_id = ?", (result.run_id,)
            )
            connection.execute(
                "DELETE FROM gold_difference WHERE run_id = ?", (result.run_id,)
            )
            connection.execute(
                "DELETE FROM gold_exception WHERE run_id = ?", (result.run_id,)
            )
            connection.execute(
                "DELETE FROM gold_run WHERE run_id = ?", (result.run_id,)
            )
            connection.execute(
                """
                INSERT INTO gold_run(run_id, snapshot_id, channel, status, manifest_json, completed_at)
                VALUES (?, ?, ?, ?, ?, ?)
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
            connection.executemany(
                "INSERT INTO gold_commission_line(run_id, row_key, payload_json) VALUES (?, ?, ?)",
                [
                    (result.run_id, row.key, canonical_json(row.contract()))
                    for row in result.rows
                ],
            )
            connection.executemany(
                """
                INSERT INTO gold_difference(run_id, difference_key, classification, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (result.run_id, diff.key, diff.classification, canonical_json(diff))
                    for diff in result.differences
                ],
            )
            connection.executemany(
                "INSERT INTO gold_exception(run_id, exception_key, payload_json) VALUES (?, ?, ?)",
                [
                    (result.run_id, str(item.get("key", index)), canonical_json(item))
                    for index, item in enumerate(result.exceptions)
                ],
            )

    def latest_manifests(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT manifest_json FROM gold_run
                WHERE rowid IN (SELECT MAX(rowid) FROM gold_run GROUP BY channel)
                ORDER BY channel
                """
            ).fetchall()
        return [json.loads(row["manifest_json"]) for row in rows]

    def load_result_payload(self, run_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            run = connection.execute(
                "SELECT manifest_json FROM gold_run WHERE run_id = ?", (run_id,)
            ).fetchone()
            if run is None:
                raise KeyError(run_id)
            lines = connection.execute(
                "SELECT payload_json FROM gold_commission_line WHERE run_id = ? ORDER BY row_key",
                (run_id,),
            ).fetchall()
            differences = connection.execute(
                """
                SELECT payload_json FROM gold_difference
                WHERE run_id = ? ORDER BY difference_key, classification
                """,
                (run_id,),
            ).fetchall()
            exceptions = connection.execute(
                "SELECT payload_json FROM gold_exception WHERE run_id = ? ORDER BY exception_key",
                (run_id,),
            ).fetchall()
        return {
            "manifest": json.loads(run["manifest_json"]),
            "rows": [json.loads(row["payload_json"]) for row in lines],
            "differences": [json.loads(row["payload_json"]) for row in differences],
            "exceptions": [json.loads(row["payload_json"]) for row in exceptions],
        }
