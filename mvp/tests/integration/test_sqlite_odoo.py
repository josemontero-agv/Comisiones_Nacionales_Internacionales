from pathlib import Path

import pytest

from mvp.infrastructure.odoo_readonly import OdooReadOnlyClient, ReadOnlyViolation
from mvp.infrastructure.sqlite import MedallionRepository


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, list, dict]] = []

    def execute_kw(self, model: str, method: str, args: list, kwargs: dict) -> object:
        self.calls.append((model, method, args, kwargs))
        if method == "search_read":
            last_id = next((item[2] for item in args[0] if item[:2] == ("id", ">")), 0)
            return (
                [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}] if last_id == 0 else []
            )
        return 2


def test_readonly_client_paginates_and_rejects_writes() -> None:
    transport = FakeTransport()
    client = OdooReadOnlyClient(transport, page_size=2)
    assert [
        row["id"]
        for row in client.search_read_paged("account.move", [], ("id", "name"))
    ] == [1, 2]
    call = transport.calls[0]
    assert call[3]["fields"] == ["id", "name"]
    assert call[3]["order"] == "id asc"
    with pytest.raises(ReadOnlyViolation):
        client.execute("account.move", "write", [1], {"name": "X"})


def test_bronze_load_is_idempotent(tmp_path: Path) -> None:
    repository = MedallionRepository(tmp_path / "pilot.sqlite3")
    args = (
        "snapshot",
        "nacional",
        "2026-09-01",
        "2026-09-30",
        "source.xlsx",
        "abc",
        [("excel", "1", {"amount": "1.00"})],
    )
    repository.store_snapshot(*args)
    repository.store_snapshot(*args)
    with repository.connect() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM bronze_snapshot").fetchone()[0]
            == 1
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM bronze_record").fetchone()[0] == 1
        )
