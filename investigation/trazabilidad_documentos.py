# -*- coding: utf-8 -*-
"""
Investigacion de trazabilidad de documentos en letras.

Flujo objetivo:
Pedido -> Factura origen -> Planilla -> Letra(s) por estado.

Estados clave a revisar en letras:
- to_accept (por aceptar)
- collection (cobranza)
- portfolio (cartera)
- discount (descuento)
- protested (protesto)
"""

import os
import xmlrpc.client
from collections import defaultdict
from dotenv import load_dotenv


LETTER_STATES = ["to_accept", "collection", "portfolio", "discount", "protested"]


def _connect():
    env_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../.env.produccion")
    )
    load_dotenv(env_path)

    url = os.getenv("ODOO_URL")
    db = os.getenv("ODOO_DB")
    username = os.getenv("ODOO_USER")
    password = os.getenv("ODOO_PASSWORD")

    if not all([url, db, username, password]):
        raise ValueError("Faltan credenciales Odoo en .env.produccion")

    print(f"Conectando a {url} ...")
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    if not uid:
        raise ValueError("Autenticacion fallida")

    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    print("[OK] Conexion establecida")
    return db, uid, password, models


def _search_read(db, uid, password, models, model, domain, fields, limit=80, order="id desc"):
    return models.execute_kw(
        db,
        uid,
        password,
        model,
        "search_read",
        [domain],
        {"fields": fields, "limit": limit, "order": order},
    )


def _read(db, uid, password, models, model, ids, fields):
    if not ids:
        return []
    return models.execute_kw(db, uid, password, model, "read", [ids], {"fields": fields})


def _first_many2one_name(value):
    if isinstance(value, list) and len(value) >= 2:
        return value[1]
    return ""


def trace_flow():
    db, uid, password, models = _connect()

    print("=" * 84)
    print("TRAZABILIDAD DE LETRAS POR ESTADO")
    print("=" * 84)

    # 1) Buscar letras (account.move out_bill) para cada estado.
    letters_by_state = {}
    all_letter_ids = set()
    print("\n[1] Muestreo de letras por estado")
    for state in LETTER_STATES:
        rows = _search_read(
            db,
            uid,
            password,
            models,
            "account.move",
            [("move_type", "=", "out_bill"), ("state", "=", state)],
            [
                "id",
                "name",
                "state",
                "bill_form_id",
                "l10n_latam_boe_number",
                "invoice_origin",
                "invoice_payment_term_id",
                "sales_channel_id",
                "sale_type_id",
                "team_id",
                "bill_form_invoices_order_sales_line_commercial_zone_id",
                "invoice_user_id",
            ],
            limit=40,
        )
        letters_by_state[state] = rows
        all_letter_ids.update(r["id"] for r in rows)
        print(f"  - {state}: {len(rows)} letras (muestra)")

    if not all_letter_ids:
        print("\nNo se encontraron letras en los estados objetivo.")
        return

    # 2) Reunir planillas asociadas.
    bill_form_ids = {
        r["bill_form_id"][0]
        for rows in letters_by_state.values()
        for r in rows
        if isinstance(r.get("bill_form_id"), list) and len(r["bill_form_id"]) >= 1
    }
    bill_forms = _read(
        db,
        uid,
        password,
        models,
        "account.bill.form",
        list(bill_form_ids),
        ["id", "name", "state", "invoice_ids", "move_ids"],
    )
    bill_form_map = {bf["id"]: bf for bf in bill_forms}

    # 3) Reunir facturas origen de planilla para trazabilidad.
    invoice_ids = set()
    for bf in bill_forms:
        invoice_ids.update(bf.get("invoice_ids") or [])
    source_invoices = _read(
        db,
        uid,
        password,
        models,
        "account.move",
        list(invoice_ids),
        [
            "id",
            "name",
            "state",
            "move_type",
            "invoice_origin",
            "invoice_payment_term_id",
            "sales_channel_id",
            "sale_type_id",
            "team_id",
            "bill_form_invoices_order_sales_line_commercial_zone_id",
            "invoice_user_id",
            "amount_total",
        ],
    )
    source_invoice_map = {inv["id"]: inv for inv in source_invoices}

    # 4) Reporte de trazabilidad por estado.
    print("\n[2] Trazabilidad por estado (letra -> planilla -> factura origen)")
    missing_stats = defaultdict(lambda: defaultdict(int))

    fields_to_check = {
        "invoice_payment_term_id": "Condicion de pago",
        "sales_channel_id": "Canal de venta",
        "sale_type_id": "Tipo de venta",
        "bill_form_invoices_order_sales_line_commercial_zone_id": "Linea comercial",
    }

    for state in LETTER_STATES:
        rows = letters_by_state.get(state, [])
        if not rows:
            continue

        print("\n" + "-" * 84)
        print(f"ESTADO: {state} | Letras analizadas: {len(rows)}")

        for letter in rows[:10]:
            bf_ref = letter.get("bill_form_id")
            bf_id = bf_ref[0] if isinstance(bf_ref, list) and bf_ref else None
            bf = bill_form_map.get(bf_id, {})
            inv_ids = bf.get("invoice_ids") or []
            src = source_invoice_map.get(inv_ids[0], {}) if inv_ids else {}

            letter_name = letter.get("name", "")
            bf_name = bf.get("name", "") if bf else ""
            src_name = src.get("name", "") if src else ""

            print(f"\n  Letra: {letter_name} | BOE: {letter.get('l10n_latam_boe_number') or '-'}")
            print(f"    Planilla: {bf_name or '-'} | Factura origen: {src_name or '-'}")

            for fkey, flabel in fields_to_check.items():
                letter_val = _first_many2one_name(letter.get(fkey))
                src_val = _first_many2one_name(src.get(fkey))
                if not letter_val:
                    missing_stats[state][fkey] += 1
                resolved = letter_val or src_val or "-"
                print(
                    f"    {flabel}: letra='{letter_val or '-'}' | origen='{src_val or '-'}' | trazado='{resolved}'"
                )

    # 5) Resumen de vacios por estado.
    print("\n[3] Resumen de campos vacios en la letra (por estado)")
    print("-" * 84)
    for state in LETTER_STATES:
        rows = letters_by_state.get(state, [])
        if not rows:
            continue
        total = len(rows)
        print(f"\nEstado {state} (muestra={total})")
        for fkey, flabel in fields_to_check.items():
            missing = missing_stats[state][fkey]
            pct = (missing / total * 100) if total else 0
            print(f"  - {flabel}: {missing}/{total} vacios ({pct:.1f}%)")

    print("\n[4] Nota")
    print(
        "Si ves vacios altos en estados de letras, confirma que la UI use fallback desde factura origen "
        "via bill_form_id -> invoice_ids."
    )


if __name__ == "__main__":
    trace_flow()

