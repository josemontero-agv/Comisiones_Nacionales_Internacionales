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


@pytest.mark.parametrize("channel", ["nacional", "internacional"])
def test_rrhh_export_contains_only_selected_channel(
    tmp_path: Path, channel: str
) -> None:
    database = tmp_path / "pilot.sqlite3"
    run_historical_parity("nacional", database)
    run_historical_parity("internacional", database)
    output = export_rrhh_workbook(database, tmp_path / f"{channel}.xlsx", channel)
    workbook = openpyxl.load_workbook(output, read_only=True, data_only=True)
    assert workbook.sheetnames == [
        "Resumen RRHH",
        "Detalle",
        "Excepciones",
        "Diferencias",
        "Manifest",
    ]
    assert workbook["Resumen RRHH"].max_row > 2
    detail = workbook["Detalle"]
    channel_column = list(next(detail.iter_rows(values_only=True))).index("channel")
    assert {
        row[channel_column] for row in detail.iter_rows(min_row=2, values_only=True)
    } == {channel}
    manifests = list(workbook["Manifest"].iter_rows(min_row=2, values_only=True))
    assert len(manifests) == 1
    assert manifests[0][0] == channel
    workbook.close()
