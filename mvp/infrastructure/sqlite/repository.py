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
                "DELETE FROM gold_collected_line WHERE run_id = ?", (result.run_id,)
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
                "INSERT INTO gold_collected_line(run_id, row_key, payload_json) VALUES (?, ?, ?)",
                [
                    (result.run_id, row.key, canonical_json(row.contract()))
                    for row in result.collected_rows
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

    def store_silver_records(
        self,
        snapshot_id: str,
        records: list[tuple[str, str, dict[str, Any]]],
    ) -> None:
        """Reemplaza de forma atómica la proyección Silver de un snapshot."""
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM silver_record WHERE snapshot_id = ?", (snapshot_id,)
            )
            connection.executemany(
                """
                INSERT INTO silver_record
                (snapshot_id, entity_type, entity_key, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (snapshot_id, entity_type, entity_key, canonical_json(payload))
                    for entity_type, entity_key, payload in records
                ],
            )

    def snapshot_counts(self, snapshot_id: str) -> dict[str, int]:
        with self.connect() as connection:
            bronze = connection.execute(
                "SELECT COUNT(*) FROM bronze_record WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()[0]
            silver = connection.execute(
                "SELECT COUNT(*) FROM silver_record WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()[0]
        return {"bronze": int(bronze), "silver": int(silver)}

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
                SELECT snapshot_id FROM bronze_snapshot
                WHERE channel = ? AND period_start = ? AND period_end = ?
                  AND source_path = ? AND status = 'closed'
                ORDER BY loaded_at DESC LIMIT 1
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
                SELECT source_model, payload_json FROM bronze_record
                WHERE snapshot_id = ? ORDER BY source_model, source_key
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
                SELECT manifest_json FROM gold_run
                ORDER BY rowid DESC
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
                "SELECT manifest_json FROM gold_run WHERE run_id = ?", (run_id,)
            ).fetchone()
            if run is None:
                raise KeyError(run_id)
            lines = connection.execute(
                "SELECT payload_json FROM gold_commission_line WHERE run_id = ? ORDER BY row_key",
                (run_id,),
            ).fetchall()
            collected_lines = connection.execute(
                "SELECT payload_json FROM gold_collected_line WHERE run_id = ? ORDER BY row_key",
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
            "collected_rows": [
                json.loads(row["payload_json"]) for row in collected_lines
            ],
            "differences": [json.loads(row["payload_json"]) for row in differences],
            "exceptions": [json.loads(row["payload_json"]) for row in exceptions],
        }
