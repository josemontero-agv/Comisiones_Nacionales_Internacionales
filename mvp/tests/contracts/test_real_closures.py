from pathlib import Path

import openpyxl
import pytest

from mvp.export import export_rrhh_workbook
from mvp.historical import run_historical_parity
from mvp.infrastructure.sqlite import MedallionRepository


@pytest.mark.parametrize("channel", ["nacional", "internacional"])
def test_real_september_closure_is_reproducible(tmp_path: Path, channel: str) -> None:
    database = tmp_path / "pilot.sqlite3"
    first = run_historical_parity(channel, database)
    second = run_historical_parity(channel, database)
    assert first.run_id == second.run_id
    assert first.manifest()["gold_sha256"] == second.manifest()["gold_sha256"]
    assert first.rows
    assert first.expected_total > 0
    payload = MedallionRepository(database).load_result_payload(first.run_id)
    assert len(payload["rows"]) == len(first.rows)


def test_rrhh_export_contains_contract_sheets(tmp_path: Path) -> None:
    database = tmp_path / "pilot.sqlite3"
    run_historical_parity("nacional", database)
    run_historical_parity("internacional", database)
    output = export_rrhh_workbook(database, tmp_path / "rrhh.xlsx")
    workbook = openpyxl.load_workbook(output, read_only=True, data_only=True)
    assert workbook.sheetnames == [
        "Resumen RRHH",
        "Detalle",
        "Excepciones",
        "Diferencias",
        "Manifest",
    ]
    assert workbook["Resumen RRHH"].max_row > 2
