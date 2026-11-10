"""Load de septiembre: Odoo read-only → Bronze → Silver → Gold."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from mvp.application.contracts import CollectedLine, GoldRow, RunResult, sha256_json
from mvp.domain.commissions import payment_line_commission
from mvp.domain.eligibility import evaluate
from mvp.domain.models import (
    CATEGORY_CREDITO,
    CATEGORY_LETRAS,
    KIND_CREDIT_NOTE,
    KIND_LETTER_TRANSFER,
    KIND_PAYMENT,
    KIND_UNKNOWN,
    Document,
    DocumentLine,
    PaymentAllocation,
)
from mvp.domain.money import to_decimal
from mvp.domain.periods import Period, parse_date
from mvp.domain.rules import (
    LineContext,
    Ruleset,
    intl_beneficiaries,
    load_ruleset_file,
    normalize_key,
    resolve_beneficiary,
)
from mvp.infrastructure.odoo_extract import store_records_snapshot
from mvp.infrastructure.odoo_readonly import (
    OdooCredentials,
    OdooReadOnlyClient,
    XmlRpcTransport,
)
from mvp.infrastructure.sqlite import MedallionRepository

ROOT = Path(__file__).resolve().parents[2]
RULESET_PATH = ROOT / "mvp/rulesets/2026-09.v1.json"
SEPTEMBER_PERIODS = {
    "nacional": Period("nacional", date(2026, 9, 1), date(2026, 9, 30)),
    "internacional": Period("internacional", date(2026, 8, 20), date(2026, 9, 20)),
}

PARTIAL_FIELDS = (
    "id",
    "max_date",
    "amount",
    "debit_amount_currency",
    "credit_amount_currency",
    "debit_move_id",
    "credit_move_id",
    "full_reconcile_id",
    "exchange_move_id",
    "write_date",
)
RECONCILE_LINE_FIELDS = (
    "id",
    "move_id",
    "account_id",
    "amount_currency",
    "balance",
    "currency_id",
    "write_date",
)
MOVE_FIELDS = (
    "id",
    "name",
    "move_type",
    "state",
    "invoice_date",
    "date",
    "amount_total",
    "amount_untaxed",
    "currency_id",
    "payment_state",
    "invoice_payment_term_id",
    "sale_type_id",
    "sales_channel_id",
    "journal_id",
    "team_id",
    "l10n_latam_document_type_id",
    "partner_id",
    "commercial_partner_id",
    "partner_shipping_id",
    "bill_form_id",
    "l10n_latam_boe_number",
    "invoice_origin",
    "write_date",
)
INVOICE_LINE_FIELDS = (
    "id",
    "move_id",
    "name",
    "display_type",
    "product_id",
    "account_id",
    "price_subtotal",
    "price_total",
    "quantity",
    "currency_id",
    "sale_line_ids",
    "write_date",
)


def _id(value: object) -> int | None:
    return int(value[0]) if isinstance(value, (list, tuple)) and value else None


def _name(value: object) -> str:
    return str(value[1]) if isinstance(value, (list, tuple)) and len(value) > 1 else ""


def _by_id(rows: Iterable[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(row["id"]): row for row in rows}


class _Bronze:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], dict[str, Any]] = {}

    def add(self, model: str, rows: Iterable[dict[str, Any]]) -> None:
        for row in rows:
            self._rows[(model, str(row["id"]))] = row

    def records(self) -> list[tuple[str, str, dict[str, Any]]]:
        return [
            (model, key, payload)
            for (model, key), payload in sorted(self._rows.items())
        ]


def _read(
    client: OdooReadOnlyClient,
    bronze: _Bronze,
    model: str,
    ids: Iterable[int],
    fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    rows = client.read_by_ids(model, ids, fields)
    bronze.add(model, rows)
    return rows


def _search(
    client: OdooReadOnlyClient,
    bronze: _Bronze,
    model: str,
    domain: list,
    fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    rows = list(client.search_read_paged(model, domain, fields))
    bronze.add(model, rows)
    return rows


def _channel_matches(move: dict[str, Any], channel: str) -> bool:
    return normalize_key(_name(move.get("sales_channel_id"))) == normalize_key(channel)


def _source_amount(
    partial: dict[str, Any], source_line_id: int, currency: str
) -> Decimal:
    debit_id = _id(partial.get("debit_move_id"))
    field = (
        "debit_amount_currency"
        if debit_id == source_line_id
        else "credit_amount_currency"
    )
    amount = abs(to_decimal(partial.get(field)))
    if not amount:
        amount = abs(to_decimal(partial.get("amount")))
    return amount


def _counterpart_kind(
    source_line_id: int,
    partial: dict[str, Any],
    reconcile_lines: dict[int, dict[str, Any]],
    moves: dict[int, dict[str, Any]],
    journals: dict[int, dict[str, Any]],
) -> tuple[str, str]:
    debit_id = _id(partial.get("debit_move_id"))
    credit_id = _id(partial.get("credit_move_id"))
    counterpart_line_id = credit_id if source_line_id == debit_id else debit_id
    counterpart_line = reconcile_lines.get(counterpart_line_id or -1, {})
    counterpart = moves.get(_id(counterpart_line.get("move_id")) or -1, {})
    move_type = str(counterpart.get("move_type") or "")
    journal = journals.get(_id(counterpart.get("journal_id")) or -1, {})
    journal_code = normalize_key(journal.get("code"))
    journal_name = normalize_key(journal.get("name"))
    if move_type == "out_refund":
        return KIND_CREDIT_NOTE, str(counterpart.get("name") or "")
    if move_type == "out_bill" or journal_code == "TRP" or "TRANSITORY" in journal_name:
        return KIND_LETTER_TRANSFER, str(counterpart.get("name") or "")
    if move_type in {"entry", "inbound", "outbound"}:
        return KIND_PAYMENT, str(counterpart.get("name") or "")
    if move_type == "out_invoice":
        return KIND_LETTER_TRANSFER, str(counterpart.get("name") or "")
    return KIND_UNKNOWN, str(counterpart.get("name") or "")


def _category(
    channel: str,
    source_is_letter: bool,
    move: dict[str, Any],
    terms: dict[int, dict[str, Any]],
    ruleset: Ruleset,
) -> str:
    if source_is_letter:
        return CATEGORY_LETRAS
    term = terms.get(_id(move.get("invoice_payment_term_id")) or -1, {})
    term_name = str(term.get("name") or _name(move.get("invoice_payment_term_id")))
    configured = ruleset.category_by_term.get(channel, {}).get(normalize_key(term_name))
    if configured:
        return configured
    return (
        "CONTADO"
        if normalize_key(term.get("payment_type")) == "CONTADO"
        else CATEGORY_CREDITO
    )


def _commercial_line(
    channel: str,
    line: dict[str, Any],
    products: dict[int, dict[str, Any]],
    ruleset: Ruleset,
) -> str:
    product = products.get(_id(line.get("product_id")) or -1, {})
    product_code = str(product.get("default_code") or "")
    override = ruleset.override_for(product_code)
    if override and override.approved:
        return normalize_key(override.commercial_line)
    field = (
        "commercial_line_national_id"
        if channel == "nacional"
        else "commercial_line_international_id"
    )
    return normalize_key(
        _name(product.get(field)) or _name(product.get("line_commercial_id"))
    )


def _zone_for_line(
    line: dict[str, Any],
    sale_lines: dict[int, dict[str, Any]],
    orders: dict[int, dict[str, Any]],
) -> tuple[str, bool]:
    zones = {
        normalize_key(
            _name(
                orders.get(
                    _id(sale_lines.get(int(sale_id), {}).get("order_id")) or -1, {}
                ).get("line_commercial_zone_id")
            )
        )
        for sale_id in line.get("sale_line_ids") or []
    }
    zones.discard("")
    return (next(iter(zones)), False) if len(zones) == 1 else ("", len(zones) > 1)


def _national_rule_key(zone: str, product_name: str, commercial_line: str) -> str:
    key = normalize_key(zone)
    if key.startswith("PETMEDICA/") and "ATREVIA" in normalize_key(product_name):
        return f"{key}/ATREVIA"
    if key.startswith("AVIVET/") and commercial_line == "AGROVET":
        return f"{key}/AGROVET"
    return key


def _exception(
    key: str, code: str, detail: str, *, blocking: bool = True
) -> dict[str, Any]:
    return {"key": key, "code": code, "blocking": blocking, "detail": detail}


def _record_load_error(channel: str, period: Period, exc: Exception) -> None:
    """Deja evidencia local del fallo sin incluir credenciales ni activar fallback."""
    destination = ROOT / "var/odoo_load_errors.jsonl"
    destination.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "occurred_at": datetime.now(UTC).isoformat(),
        "channel": channel,
        "period_start": period.start.isoformat(),
        "period_end": period.end.isoformat(),
        "error_type": type(exc).__name__,
        "error": str(exc),
        "fallback_used": False,
    }
    with destination.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _extract(
    client: OdooReadOnlyClient, channel: str, period: Period
) -> tuple[str, dict[str, Any], _Bronze]:
    """Extrae relaciones por lotes y conserva solo evidencia del canal solicitado."""
    bronze = _Bronze()
    all_partials = list(
        client.search_read_paged(
            "account.partial.reconcile",
            [
                ("max_date", ">=", period.start.isoformat()),
                ("max_date", "<=", period.end.isoformat()),
            ],
            PARTIAL_FIELDS,
        )
    )
    all_line_ids = {
        relation_id
        for row in all_partials
        for relation_id in (
            _id(row.get("debit_move_id")),
            _id(row.get("credit_move_id")),
        )
        if relation_id
    }
    all_reconcile_lines = client.read_by_ids(
        "account.move.line", all_line_ids, RECONCILE_LINE_FIELDS
    )
    all_move_ids = {
        move_id for row in all_reconcile_lines if (move_id := _id(row.get("move_id")))
    }
    all_moves = client.read_by_ids("account.move", all_move_ids, MOVE_FIELDS)
    all_move_by_id = _by_id(all_moves)

    bill_form_ids = {
        bill_form_id
        for move in all_moves
        if move.get("move_type") == "out_bill"
        and (bill_form_id := _id(move.get("bill_form_id")))
    }
    bill_forms = client.read_by_ids(
        "account.bill.form",
        bill_form_ids,
        (
            "id",
            "name",
            "invoice_ids",
            "move_ids",
            "bills_qty",
            "total_bills",
            "total_invoices",
            "partner_id",
            "state",
            "write_date",
        ),
    )
    origin_invoice_ids = {
        int(invoice_id)
        for form in bill_forms
        for invoice_id in form.get("invoice_ids") or []
    }
    origin_moves = client.read_by_ids("account.move", origin_invoice_ids, MOVE_FIELDS)
    all_move_by_id.update(_by_id(origin_moves))
    form_by_id = _by_id(bill_forms)

    direct_source_ids = {
        move_id
        for move_id, move in all_move_by_id.items()
        if move.get("move_type") == "out_invoice" and _channel_matches(move, channel)
    }
    letter_source_ids = {
        move_id
        for move_id, move in all_move_by_id.items()
        if move.get("move_type") == "out_bill"
        and any(
            int(invoice_id) in direct_source_ids
            for invoice_id in form_by_id.get(
                _id(move.get("bill_form_id")) or -1, {}
            ).get("invoice_ids", [])
        )
    }
    reconcile_line_by_id = _by_id(all_reconcile_lines)
    relevant_partials: list[dict[str, Any]] = []
    relevant_reconcile_line_ids: set[int] = set()
    for partial in all_partials:
        debit_id = _id(partial.get("debit_move_id"))
        credit_id = _id(partial.get("credit_move_id"))
        partial_move_ids = {
            _id(reconcile_line_by_id.get(line_id or -1, {}).get("move_id"))
            for line_id in (debit_id, credit_id)
        }
        if partial_move_ids & (direct_source_ids | letter_source_ids):
            relevant_partials.append(partial)
            relevant_reconcile_line_ids.update(
                line_id for line_id in (debit_id, credit_id) if line_id
            )

    relevant_reconcile_lines = [
        reconcile_line_by_id[line_id] for line_id in relevant_reconcile_line_ids
    ]
    relevant_move_ids = {
        move_id
        for line in relevant_reconcile_lines
        if (move_id := _id(line.get("move_id")))
    }
    relevant_move_ids.update(direct_source_ids)
    relevant_move_ids.update(letter_source_ids)
    relevant_move_ids.update(origin_invoice_ids)
    moves = _read(client, bronze, "account.move", relevant_move_ids, MOVE_FIELDS)
    move_by_id = _by_id(moves)

    relevant_form_ids = {
        form_id
        for move_id in letter_source_ids
        if (form_id := _id(move_by_id.get(move_id, {}).get("bill_form_id")))
    }
    forms = [
        form_by_id[form_id] for form_id in relevant_form_ids if form_id in form_by_id
    ]
    bronze.add("account.bill.form", forms)
    invoice_ids = direct_source_ids | {
        int(invoice_id)
        for form in forms
        for invoice_id in form.get("invoice_ids") or []
        if int(invoice_id) in direct_source_ids
    }
    invoice_lines = _search(
        client,
        bronze,
        "account.move.line",
        [("move_id", "in", sorted(invoice_ids)), ("display_type", "=", "product")],
        INVOICE_LINE_FIELDS,
    )

    account_ids = {
        account_id
        for line in invoice_lines
        if (account_id := _id(line.get("account_id")))
    }
    product_ids = {
        product_id
        for line in invoice_lines
        if (product_id := _id(line.get("product_id")))
    }
    sale_line_ids = {
        int(sale_id)
        for line in invoice_lines
        for sale_id in line.get("sale_line_ids") or []
    }
    accounts = _read(
        client,
        bronze,
        "account.account",
        account_ids,
        ("id", "code", "name", "write_date"),
    )
    products = _read(
        client,
        bronze,
        "product.product",
        product_ids,
        (
            "id",
            "name",
            "display_name",
            "default_code",
            "commercial_line_national_id",
            "commercial_line_international_id",
            "line_commercial_id",
            "write_date",
        ),
    )
    sale_lines = _read(
        client,
        bronze,
        "sale.order.line",
        sale_line_ids,
        (
            "id",
            "order_id",
            "product_id",
            "sales_comercial_division_category_id",
            "write_date",
        ),
    )
    order_ids = {
        order_id for row in sale_lines if (order_id := _id(row.get("order_id")))
    }
    orders = _read(
        client,
        bronze,
        "sale.order",
        order_ids,
        ("id", "name", "line_commercial_zone_id", "write_date"),
    )
    partner_ids = {
        partner_id
        for move_id in invoice_ids
        for field in ("partner_id", "commercial_partner_id", "partner_shipping_id")
        if (partner_id := _id(move_by_id.get(move_id, {}).get(field)))
    }
    partners = _read(
        client,
        bronze,
        "res.partner",
        partner_ids,
        ("id", "name", "commercial_partner_id", "country_id", "write_date"),
    )
    country_ids = {
        country_id for row in partners if (country_id := _id(row.get("country_id")))
    }
    countries = _read(
        client, bronze, "res.country", country_ids, ("id", "name", "code", "write_date")
    )
    term_ids = {
        term_id
        for move_id in invoice_ids
        if (term_id := _id(move_by_id.get(move_id, {}).get("invoice_payment_term_id")))
    }
    terms = _read(
        client,
        bronze,
        "account.payment.term",
        term_ids,
        ("id", "name", "payment_type", "operation_type", "write_date"),
    )
    journal_ids = {
        journal_id for move in moves if (journal_id := _id(move.get("journal_id")))
    }
    journals = _read(
        client,
        bronze,
        "account.journal",
        journal_ids,
        ("id", "code", "name", "write_date"),
    )
    doc_type_ids = {
        doc_type_id
        for move_id in invoice_ids
        if (
            doc_type_id := _id(
                move_by_id.get(move_id, {}).get("l10n_latam_document_type_id")
            )
        )
    }
    doc_types = _read(
        client,
        bronze,
        "l10n_latam.document.type",
        doc_type_ids,
        ("id", "code", "name", "write_date"),
    )
    bronze.add("account.partial.reconcile", relevant_partials)
    bronze.add("account.move.line", relevant_reconcile_lines)

    payload = {
        "partials": relevant_partials,
        "reconcile_lines": relevant_reconcile_lines,
        "moves": moves,
        "forms": forms,
        "invoice_lines": invoice_lines,
        "accounts": accounts,
        "products": products,
        "sale_lines": sale_lines,
        "orders": orders,
        "partners": partners,
        "countries": countries,
        "terms": terms,
        "journals": journals,
        "doc_types": doc_types,
        "direct_source_ids": direct_source_ids,
        "letter_source_ids": letter_source_ids,
    }
    return client._transport.server_version, payload, bronze


def _payload_from_bronze(
    records: list[tuple[str, dict[str, Any]]], channel: str
) -> dict[str, Any]:
    """Reconstruye el input de cálculo sin volver a consultar Odoo."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for model, payload in records:
        grouped[model].append(payload)
    moves = grouped["account.move"]
    forms = grouped["account.bill.form"]
    direct_source_ids = {
        int(move["id"])
        for move in moves
        if move.get("move_type") == "out_invoice" and _channel_matches(move, channel)
    }
    form_by_id = _by_id(forms)
    letter_source_ids = {
        int(move["id"])
        for move in moves
        if move.get("move_type") == "out_bill"
        and any(
            int(invoice_id) in direct_source_ids
            for invoice_id in form_by_id.get(
                _id(move.get("bill_form_id")) or -1, {}
            ).get("invoice_ids", [])
        )
    }
    move_lines = grouped["account.move.line"]
    return {
        "partials": grouped["account.partial.reconcile"],
        "reconcile_lines": [
            row
            for row in move_lines
            if "balance" in row and "price_subtotal" not in row
        ],
        "moves": moves,
        "forms": forms,
        "invoice_lines": [row for row in move_lines if "price_subtotal" in row],
        "accounts": grouped["account.account"],
        "products": grouped["product.product"],
        "sale_lines": grouped["sale.order.line"],
        "orders": grouped["sale.order"],
        "partners": grouped["res.partner"],
        "countries": grouped["res.country"],
        "terms": grouped["account.payment.term"],
        "journals": grouped["account.journal"],
        "doc_types": grouped["l10n_latam.document.type"],
        "direct_source_ids": direct_source_ids,
        "letter_source_ids": letter_source_ids,
    }


def _calculate(
    channel: str,
    period: Period,
    snapshot_id: str,
    payload: dict[str, Any],
    ruleset: Ruleset,
) -> tuple[RunResult, list[tuple[str, str, dict[str, Any]]]]:
    maps = {
        key: _by_id(payload[key])
        for key in (
            "reconcile_lines",
            "moves",
            "forms",
            "accounts",
            "products",
            "sale_lines",
            "orders",
            "partners",
            "countries",
            "terms",
            "journals",
            "doc_types",
        )
    }
    lines_by_move: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for line in payload["invoice_lines"]:
        move_id = _id(line.get("move_id"))
        if move_id:
            lines_by_move[move_id].append(line)

    documents: dict[int, Document] = {}
    domain_lines: dict[int, DocumentLine] = {}
    for move_id in payload["direct_source_ids"]:
        move = maps["moves"].get(move_id)
        if not move:
            continue
        direct_partner = maps["partners"].get(_id(move.get("partner_id")) or -1, {})
        commercial_partner = maps["partners"].get(
            _id(move.get("commercial_partner_id")) or -1, {}
        )
        shipping_partner = maps["partners"].get(
            _id(move.get("partner_shipping_id")) or -1, {}
        )
        country_ref = (
            commercial_partner.get("country_id")
            or direct_partner.get("country_id")
            or shipping_partner.get("country_id")
        )
        country = maps["countries"].get(_id(country_ref) or -1, {})
        journal = maps["journals"].get(_id(move.get("journal_id")) or -1, {})
        doc_type = maps["doc_types"].get(
            _id(move.get("l10n_latam_document_type_id")) or -1, {}
        )
        documents[move_id] = Document(
            doc_key=str(move.get("name") or move_id),
            channel=channel,
            currency=period.currency,
            amount_total=abs(to_decimal(move.get("amount_total"))),
            amount_untaxed=abs(to_decimal(move.get("amount_untaxed"))),
            move_type=str(move.get("move_type") or ""),
            doc_type_code=str(doc_type.get("code") or ""),
            doc_type_name=str(doc_type.get("name") or ""),
            journal_code=str(journal.get("code") or ""),
            journal_name=str(journal.get("name") or ""),
            team_name=_name(move.get("team_id")),
            sale_type_name=_name(move.get("sale_type_id")),
            payment_term_name=_name(move.get("invoice_payment_term_id")),
            payment_state=str(move.get("payment_state") or ""),
            invoice_date=parse_date(move.get("invoice_date")),
            partner_ref=str(_id(move.get("commercial_partner_id")) or ""),
            partner_name=_name(move.get("partner_id")),
            country_id=_id(country_ref),
            country_code=str(country.get("code") or "") or None,
            source_keys=(f"account.move:{move_id}",),
        )
        for line in lines_by_move.get(move_id, []):
            product = maps["products"].get(_id(line.get("product_id")) or -1, {})
            account = maps["accounts"].get(_id(line.get("account_id")) or -1, {})
            zone, conflict = _zone_for_line(line, maps["sale_lines"], maps["orders"])
            domain_lines[int(line["id"])] = DocumentLine(
                doc_key=documents[move_id].doc_key,
                line_key=str(line["id"]),
                price_subtotal=abs(to_decimal(line.get("price_subtotal"))),
                price_total=abs(to_decimal(line.get("price_total"))),
                product_code=str(product.get("default_code") or "") or None,
                product_name=str(
                    product.get("name")
                    or product.get("display_name")
                    or line.get("name")
                    or ""
                ),
                commercial_line=_commercial_line(
                    channel, line, maps["products"], ruleset
                ),
                line_category=("MULTIPLE_ZONES" if conflict else zone),
                account_code=str(account.get("code") or "") or None,
                source_keys=(f"account.move.line:{line['id']}",),
            )

    allocations: list[tuple[int, int, PaymentAllocation, str]] = []
    exceptions: list[dict[str, Any]] = []
    partials_by_id = _by_id(payload["partials"])
    for partial_id, partial in partials_by_id.items():
        payment_day = parse_date(partial.get("max_date"))
        if payment_day is None:
            exceptions.append(
                _exception(str(partial_id), "MISSING_PAYMENT_DATE", "max_date vacío")
            )
            continue
        debit_line_id = _id(partial.get("debit_move_id"))
        credit_line_id = _id(partial.get("credit_move_id"))
        for source_line_id in (debit_line_id, credit_line_id):
            if source_line_id is None:
                continue
            source_reconcile_line = maps["reconcile_lines"].get(source_line_id, {})
            source_move_id = _id(source_reconcile_line.get("move_id"))
            if source_move_id is None:
                continue
            source_is_letter = source_move_id in payload["letter_source_ids"]
            if (
                source_move_id not in payload["direct_source_ids"]
                and not source_is_letter
            ):
                continue
            kind, counterpart_ref = _counterpart_kind(
                source_line_id,
                partial,
                maps["reconcile_lines"],
                maps["moves"],
                maps["journals"],
            )
            source_amount = _source_amount(partial, source_line_id, period.currency)
            if source_is_letter:
                letter = maps["moves"][source_move_id]
                form = maps["forms"].get(_id(letter.get("bill_form_id")) or -1, {})
                invoice_ids = [
                    int(invoice_id)
                    for invoice_id in form.get("invoice_ids") or []
                    if int(invoice_id) in documents
                ]
                total = sum(
                    (documents[invoice_id].amount_total for invoice_id in invoice_ids),
                    Decimal(0),
                )
                if not invoice_ids or total <= 0:
                    exceptions.append(
                        _exception(
                            str(source_move_id),
                            "LETTER_WITHOUT_SOURCE_INVOICE",
                            str(letter.get("name") or source_move_id),
                        )
                    )
                    continue
                for invoice_id in invoice_ids:
                    amount = source_amount * documents[invoice_id].amount_total / total
                    allocations.append(
                        (
                            invoice_id,
                            partial_id,
                            PaymentAllocation(
                                doc_key=documents[invoice_id].doc_key,
                                allocation_key=f"partial:{partial_id}:letter:{source_move_id}:invoice:{invoice_id}",
                                payment_date=payment_day,
                                amount=amount,
                                counterpart_kind=kind,
                                counterpart_ref=counterpart_ref,
                                source_keys=(
                                    f"account.partial.reconcile:{partial_id}",
                                    f"account.move:{source_move_id}",
                                ),
                            ),
                            CATEGORY_LETRAS,
                        )
                    )
            else:
                move = maps["moves"][source_move_id]
                allocations.append(
                    (
                        source_move_id,
                        partial_id,
                        PaymentAllocation(
                            doc_key=documents[source_move_id].doc_key,
                            allocation_key=f"partial:{partial_id}:invoice:{source_move_id}",
                            payment_date=payment_day,
                            amount=source_amount,
                            counterpart_kind=kind,
                            counterpart_ref=counterpart_ref,
                            source_keys=(f"account.partial.reconcile:{partial_id}",),
                        ),
                        _category(
                            channel,
                            False,
                            move,
                            maps["terms"],
                            ruleset,
                        ),
                    )
                )

    rows: list[GoldRow] = []
    collected: list[CollectedLine] = []
    silver: list[tuple[str, str, dict[str, Any]]] = []
    for move_id, document in documents.items():
        silver.append(("document", document.doc_key, asdict(document)))
        for line in lines_by_move.get(move_id, []):
            line_id = int(line["id"])
            if line_id in domain_lines:
                silver.append(
                    ("document_line", str(line_id), asdict(domain_lines[line_id]))
                )
    for invoice_id, partial_id, allocation, category in allocations:
        silver.append(
            (
                "payment_allocation",
                allocation.allocation_key,
                asdict(allocation),
            )
        )
        document = documents[invoice_id]
        for source_line in lines_by_move.get(invoice_id, []):
            line = domain_lines[int(source_line["id"])]
            decision = evaluate(document, line, allocation, ruleset)
            decision_key = f"{line.line_key}|{allocation.allocation_key}"
            silver.append(
                (
                    "eligibility_decision",
                    decision_key,
                    {
                        "doc_key": document.doc_key,
                        "line_key": line.line_key,
                        "allocation_key": allocation.allocation_key,
                        "category": category,
                        "eligible": decision.eligible,
                        "reason_code": decision.code,
                        "blocking": decision.blocking,
                    },
                )
            )
            if not decision.eligible:
                if decision.blocking:
                    exceptions.append(
                        _exception(decision_key, decision.code, document.doc_key)
                    )
                continue
            if allocation.amount <= 0 or line.price_subtotal <= 0:
                continue
            base, _ = payment_line_commission(
                allocation.amount,
                line.price_subtotal,
                document.amount_total,
                Decimal(0),
            )
            commercial_line = normalize_key(line.commercial_line)
            if channel == "nacional":
                if line.line_category == "MULTIPLE_ZONES":
                    exceptions.append(
                        _exception(
                            decision_key,
                            "MULTIPLE_NATIONAL_ZONES",
                            document.doc_key,
                        )
                    )
                    continue
                rule_key = _national_rule_key(
                    line.line_category or "",
                    line.product_name or "",
                    commercial_line,
                )
                rule = ruleset.nacional_rule(rule_key)
                if rule is None:
                    exceptions.append(
                        _exception(
                            decision_key,
                            "MISSING_NATIONAL_RULE",
                            rule_key or document.doc_key,
                        )
                    )
                    continue
                report_line = normalize_key(rule.commercial_line)
                collected.append(
                    CollectedLine(
                        channel=channel,
                        category=category,
                        commercial_line=report_line,
                        document=document.doc_key,
                        line=line.line_key,
                        allocation=allocation.allocation_key,
                        currency=period.currency,
                        collected_raw=base,
                        source_key=f"account.partial.reconcile:{partial_id}",
                    )
                )
                for assignment in rule.roles:
                    if not assignment.rate or assignment.rate <= 0:
                        continue
                    if not assignment.person:
                        exceptions.append(
                            _exception(
                                f"{decision_key}|{assignment.role}",
                                "MISSING_BENEFICIARY",
                                rule_key,
                            )
                        )
                        continue
                    rows.append(
                        GoldRow(
                            channel=channel,
                            category=category,
                            document=document.doc_key,
                            line=line.line_key,
                            allocation=allocation.allocation_key,
                            person=assignment.person,
                            role=assignment.role,
                            currency=period.currency,
                            base_raw=base,
                            rate=assignment.rate,
                            commission_raw=base * assignment.rate,
                            rule_id=rule.rule_id,
                            source_key=f"account.partial.reconcile:{partial_id}",
                            commercial_line=report_line,
                        )
                    )
            else:
                collected.append(
                    CollectedLine(
                        channel=channel,
                        category=category,
                        commercial_line=commercial_line,
                        document=document.doc_key,
                        line=line.line_key,
                        allocation=allocation.allocation_key,
                        currency=period.currency,
                        collected_raw=base,
                        source_key=f"account.partial.reconcile:{partial_id}",
                    )
                )
                ctx = LineContext(
                    doc_key=document.doc_key,
                    product_code=line.product_code,
                    commercial_line=commercial_line,
                    partner_ref=document.partner_ref,
                    country_code=document.country_code,
                    payment_date=allocation.payment_date,
                )
                for beneficiary in intl_beneficiaries(ruleset.intl_rules):
                    resolution = resolve_beneficiary(
                        beneficiary,
                        ruleset.intl_rules,
                        ctx,
                        ruleset.country_groups,
                    )
                    if resolution.conflict or (
                        resolution.rule
                        and resolution.rule.country_group
                        and not ruleset.country_groups[
                            resolution.rule.country_group
                        ].approved
                    ):
                        exceptions.append(
                            _exception(
                                f"{decision_key}|{beneficiary}",
                                (
                                    "INTERNATIONAL_RULE_CONFLICT"
                                    if resolution.conflict
                                    else "UNAPPROVED_COUNTRY_GROUP"
                                ),
                                resolution.reason,
                            )
                        )
                        continue
                    if (
                        resolution.excluded
                        or resolution.rate is None
                        or resolution.rate <= 0
                        or resolution.rule is None
                    ):
                        continue
                    rows.append(
                        GoldRow(
                            channel=channel,
                            category=category,
                            document=document.doc_key,
                            line=line.line_key,
                            allocation=allocation.allocation_key,
                            person=beneficiary,
                            role=resolution.rule.role,
                            currency=period.currency,
                            base_raw=base,
                            rate=resolution.rate,
                            commission_raw=base * resolution.rate,
                            rule_id=resolution.rule.rule_id,
                            source_key=f"account.partial.reconcile:{partial_id}",
                            commercial_line=commercial_line,
                        )
                    )

    # Una excepción repetida por línea conserva una sola clave estable.
    exceptions = list({str(item["key"]): item for item in exceptions}.values())
    total = sum((row.commission_raw for row in rows), Decimal(0))
    run_payload = {
        "channel": channel,
        "snapshot_id": snapshot_id,
        "engine": "0.2.0",
        "ruleset_sha256": ruleset.sha256,
    }
    run_id = hashlib.sha256(sha256_json(run_payload).encode("ascii")).hexdigest()[:24]
    result = RunResult(
        run_id=run_id,
        snapshot_id=snapshot_id,
        channel=channel,
        period_start=period.start,
        period_end=period.end,
        currency=period.currency,
        status="blocked"
        if any(item["blocking"] for item in exceptions)
        else "completed",
        expected_total=total,
        actual_total=total,
        rows=rows,
        collected_rows=collected,
        exceptions=exceptions,
        metadata={
            "bronze_origin": "odoo",
            "bronze_loader": "mvp.application.odoo_load.load_september",
            "ruleset_version": ruleset.version,
            "ruleset_sha256": ruleset.sha256,
            "engine_version": "0.2.0",
            "payable": False,
            "additional_closures_ready": False,
            "excel_validation_included": False,
        },
    )
    return result, silver


def load_september(
    channel: str,
    database: Path | str | None = None,
    *,
    repository: Any | None = None,
    page_size: int = 300,
    refresh: bool = False,
) -> RunResult:
    """Ejecuta el único load autorizado: septiembre de 2026 por canal."""
    if channel not in SEPTEMBER_PERIODS:
        raise ValueError(f"canal no soportado: {channel}")
    load_dotenv(ROOT / ".env")
    period = SEPTEMBER_PERIODS[channel]
    if repository is None:
        if database is None:
            raise ValueError("load_september necesita un repositorio o una base desechable")
        repository = MedallionRepository(database)
    snapshot_id = (
        None
        if refresh
        else repository.latest_snapshot(
            channel,
            period.start.isoformat(),
            period.end.isoformat(),
            "odoo:xmlrpc-readonly",
        )
    )
    if snapshot_id:
        payload = _payload_from_bronze(
            repository.load_snapshot_records(snapshot_id), channel
        )
        server_version = "cached-snapshot"
        odoo_call_count = 0
    else:
        transport = XmlRpcTransport(OdooCredentials.from_env())
        client = OdooReadOnlyClient(transport, page_size=page_size)
        try:
            server_version, payload, bronze = _extract(client, channel, period)
        except Exception as exc:
            _record_load_error(channel, period, exc)
            raise RuntimeError(
                f"falló la extracción Odoo de {channel}; no se usó Excel como reemplazo"
            ) from exc
        snapshot_id = store_records_snapshot(
            repository,
            channel,
            period.start,
            period.end,
            bronze.records(),
        )
        odoo_call_count = len(client.calls)
    ruleset = load_ruleset_file(RULESET_PATH)
    result, silver = _calculate(channel, period, snapshot_id, payload, ruleset)
    result.metadata.update(
        {
            "odoo_server_version": server_version,
            "bronze_row_count": repository.snapshot_counts(snapshot_id)["bronze"],
            "silver_row_count": len(silver),
            "odoo_call_count": odoo_call_count,
            "snapshot_reused": odoo_call_count == 0,
        }
    )
    repository.store_silver_records(snapshot_id, silver)
    repository.store_result(result)
    return result
