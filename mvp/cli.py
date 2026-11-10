"""CLI del piloto local."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from mvp.application.contracts import canonical_json
from mvp.application.odoo_load import load_september
from mvp.export import export_rrhh_workbook
from mvp.historical import run_historical_parity
from mvp.infrastructure.copy_sqlite import copy_sqlite_gold
from mvp.infrastructure.typed_raw import project_typed_raw
from mvp.infrastructure.working import open_working_repository


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m mvp.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    load = commands.add_parser(
        "load", help="extrae Odoo, calcula Gold y exporta septiembre"
    )
    load.add_argument("--channel", choices=("nacional", "internacional"), required=True)
    load.add_argument("--output", type=Path)
    load.add_argument("--page-size", type=int, default=300)
    load.add_argument(
        "--refresh",
        action="store_true",
        help="ignora el snapshot Odoo cerrado y vuelve a extraer",
    )

    parity = commands.add_parser(
        "run-parity", help="ejecuta el cierre histórico aprobado"
    )
    parity.add_argument(
        "--channel", choices=("nacional", "internacional"), required=True
    )
    parity.add_argument("--json-output", type=Path)

    export = commands.add_parser(
        "export-xlsx", help="genera el libro separado de un canal desde Gold"
    )
    export.add_argument(
        "--channel", choices=("nacional", "internacional"), required=True
    )
    export.add_argument("--output", type=Path, required=True)

    contract = commands.add_parser(
        "export-contract", help="exporta filas Gold en JSONL"
    )
    contract.add_argument("--run-id", required=True)
    contract.add_argument("--output", type=Path, required=True)

    copy = commands.add_parser(
        "copy-sqlite-gold",
        help="copia una vez el Gold del SQLite local a Supabase",
    )
    copy.add_argument(
        "--source",
        type=Path,
        default=Path("var/commission-pilot.sqlite3"),
    )

    commands.add_parser(
        "project-typed-raw",
        help="llena raw.factura, linea, pago y letra desde Bronze/Gold",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.command == "copy-sqlite-gold":
        counts = copy_sqlite_gold(arguments.source, open_working_repository())
        print(json.dumps(counts, ensure_ascii=False, sort_keys=True))
        return 0
    if arguments.command == "project-typed-raw":
        counts = project_typed_raw(open_working_repository())
        print(json.dumps(counts, ensure_ascii=False, sort_keys=True))
        return 0
    repository = open_working_repository()
    if arguments.command == "load":
        output = arguments.output or Path(
            f"entrega_rrhh/comisiones_{arguments.channel}_septiembre_2026.xlsx"
        )
        result = load_september(
            arguments.channel,
            repository=repository,
            page_size=arguments.page_size,
            refresh=arguments.refresh,
        )
        written = export_rrhh_workbook(
            output.parent,
            output,
            arguments.channel,
            bronze_origin="odoo",
            repository=repository,
        )
        response = {
            "manifest": result.manifest(),
            "excel": str(written),
            "requested_excel": str(output),
            "excel_blocked": written.resolve() != output.resolve(),
        }
        print(json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if arguments.command == "run-parity":
        result = run_historical_parity(arguments.channel, repository=repository)
        manifest = result.manifest()
        if arguments.json_output:
            arguments.json_output.parent.mkdir(parents=True, exist_ok=True)
            arguments.json_output.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if arguments.command == "export-xlsx":
        output = export_rrhh_workbook(
            arguments.output.parent,
            arguments.output,
            arguments.channel,
            repository=repository,
        )
        print(output)
        return 0
    if arguments.command == "export-contract":
        payload = repository.load_result_payload(arguments.run_id)
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            "\n".join(canonical_json(row) for row in payload["rows"]) + "\n",
            encoding="utf-8",
        )
        print(arguments.output)
        return 0
    raise AssertionError(arguments.command)


if __name__ == "__main__":
    raise SystemExit(main())
