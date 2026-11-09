"""CLI del piloto local."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from mvp.application.contracts import canonical_json
from mvp.export import export_rrhh_workbook
from mvp.historical import run_historical_parity
from mvp.infrastructure.sqlite import MedallionRepository


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m mvp.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    parity = commands.add_parser(
        "run-parity", help="ejecuta el cierre histórico aprobado"
    )
    parity.add_argument(
        "--channel", choices=("nacional", "internacional"), required=True
    )
    parity.add_argument("--database", type=Path, required=True)
    parity.add_argument("--json-output", type=Path)

    export = commands.add_parser(
        "export-xlsx", help="genera el libro separado de un canal desde Gold"
    )
    export.add_argument(
        "--channel", choices=("nacional", "internacional"), required=True
    )
    export.add_argument("--database", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)

    contract = commands.add_parser(
        "export-contract", help="exporta filas Gold en JSONL"
    )
    contract.add_argument("--run-id", required=True)
    contract.add_argument("--database", type=Path, required=True)
    contract.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.command == "run-parity":
        result = run_historical_parity(arguments.channel, arguments.database)
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
            arguments.database, arguments.output, arguments.channel
        )
        print(output)
        return 0
    if arguments.command == "export-contract":
        payload = MedallionRepository(arguments.database).load_result_payload(
            arguments.run_id
        )
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
