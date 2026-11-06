# -*- coding: utf-8 -*-
"""
Script de evidencia (SOLO LECTURA) para el PRD de Comisiones Nacional e Internacional.

Objetivo: reproducir, contra el Odoo real de AMAH/Agrovet Market, todas las cifras y
hallazgos citados en docs/PRD_COMISIONES_NACIONAL_INTERNACIONAL.html, para que cualquier
persona del equipo pueda auditar de dónde salió cada número del documento.

No escribe nada en Odoo: solo usa 'search', 'search_read', 'read' y 'fields_get'.

Requisitos:
    - Archivo .env en la raíz del proyecto con ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD.
    - Ejecutar forzando UTF-8 en Windows PowerShell, porque la consola cp1252 por defecto
      no puede imprimir tildes/símbolos:

        $env:PYTHONUTF8="1"; python investigation/investigacion_comisiones_odoo.py

Secciones:
    1. Conexión y versión del servidor Odoo.
    2. Catálogos de canal/sub-canal/tipo de venta/línea comercial/equipos.
    3. Volumetría por canal (Nacional / Internacional / Digital) en un periodo de referencia.
    4. Evidencia de la casuística "contado / pago adelantado" (fecha de pago vs. fecha de
       factura vs. fecha de conciliación contable).
    5. Trazabilidad de letras (account.bill.form) por canal.
    6. Vendedores "genéricos" que concentran facturas sin vendedor real identificable.
    7. Diarios contables a excluir ('Facturas Sunat', 'F060 Venta exterior') y la
       distinción entre pago vía Nota de Crédito (no comisiona) y transferencia/aplicación
       de saldo a favor (sí comisiona).
    8. Boletas (no comisionables en ningún canal), TTG verificado por sale_type Y por
       condición de pago, trazabilidad completa Letra -> Planilla -> Factura -> número de
       pedido, y el diario 'Transitory receivable and payable' (traspaso Factura->Letra,
       no es un cobro real).
"""

import os
import sys
import json
import collections
import xmlrpc.client

from dotenv import load_dotenv

# Forzar salida UTF-8 en consolas que por defecto usan cp1252 (Windows PowerShell).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

# agr.payment_term IDs clasificados como "contado" en operación de ventas (ver sección 4).
# Se obtienen dinámicamente en tiempo de ejecución; esta constante documenta la intención.
CANAL_NACIONAL = 1
CANAL_INTERNACIONAL = 2
CANAL_DIGITAL = 3


def _connect():
    env_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", ".env")
    )
    load_dotenv(env_path)

    url = os.getenv("ODOO_URL", "").rstrip("/")
    db = os.getenv("ODOO_DB")
    username = os.getenv("ODOO_USER")
    password = os.getenv("ODOO_PASSWORD")

    if not all([url, db, username, password]):
        raise SystemExit(
            "[ERROR] Faltan credenciales ODOO_URL/ODOO_DB/ODOO_USER/ODOO_PASSWORD en .env"
        )

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    version = common.version()
    uid = common.authenticate(db, username, password, {})
    if not uid:
        raise SystemExit("[ERROR] Autenticación fallida contra Odoo.")

    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
    return db, uid, password, models, version


def _x(db, uid, password, models, model, method, *args, **kwargs):
    return models.execute_kw(db, uid, password, model, method, list(args), kwargs)


def seccion_1_conexion(db, uid, models, version):
    print("=" * 90)
    print("[1] CONEXIÓN Y VERSIÓN DEL SERVIDOR ODOO")
    print("=" * 90)
    print(f"  server_version : {version.get('server_version')}")
    print(f"  protocol       : {version.get('protocol_version')}")
    print(f"  uid autenticado: {uid}")
    print(
        "  Nota: el usuario de .env NO tiene acceso a 'ir.model' (grupo "
        "Administration/Access Rights). La exploración de campos se hizo con "
        "'fields_get' directamente sobre cada modelo de negocio."
    )


def seccion_2_catalogos(db, uid, password, models):
    print("\n" + "=" * 90)
    print("[2] CATÁLOGOS DE CANAL / SUB-CANAL / TIPO DE VENTA / LÍNEA COMERCIAL / EQUIPOS")
    print("=" * 90)

    canales = _x(db, uid, password, models, "agr.sales.channel", "search_read", [], fields=["id", "name"])
    print(f"\n  agr.sales.channel ({len(canales)}):")
    for c in canales:
        print(f"    {c['id']:>3}  {c['name']}")

    subcanales = _x(db, uid, password, models, "agr.sales.channel.sub", "search_read", [], fields=["id", "name"])
    print(f"\n  agr.sales.channel.sub ({len(subcanales)}):")
    for s in subcanales:
        print(f"    {s['id']:>3}  {s['name']}")

    tipos_venta = _x(db, uid, password, models, "agr.sales.type", "search_read", [], fields=["id", "name"])
    print(f"\n  agr.sales.type ({len(tipos_venta)}):")
    for t in tipos_venta:
        print(f"    {t['id']:>3}  {t['name']}")

    lineas = _x(db, uid, password, models, "agr.sales.comercial.division", "search_read", [], fields=["id", "name"])
    print(f"\n  agr.sales.comercial.division ({len(lineas)}):")
    for l in lineas:
        print(f"    {l['id']:>3}  {l['name']}")

    equipos = _x(db, uid, password, models, "crm.team", "search_read", [], fields=["id", "name", "user_id"])
    print(f"\n  crm.team ({len(equipos)}):")
    for e in equipos:
        lider = e["user_id"][1] if e.get("user_id") else "SIN LÍDER"
        print(f"    {e['id']:>3}  {e['name']:<22} líder: {lider}")


def _leer_facturas(db, uid, password, models, dominio, campos):
    ids = _x(db, uid, password, models, "account.move", "search", dominio, order="invoice_date asc")
    data = []
    for i in range(0, len(ids), 300):
        lote = ids[i : i + 300]
        data += _x(db, uid, password, models, "account.move", "read", lote, fields=campos)
    return ids, data


def seccion_3_volumetria(db, uid, password, models):
    print("\n" + "=" * 90)
    print("[3] VOLUMETRÍA POR CANAL (periodo de referencia)")
    print("=" * 90)

    campos = [
        "name", "invoice_date", "invoice_user_id", "team_id", "currency_id",
        "amount_total", "payment_state", "invoice_payment_term_id", "sale_type_id",
    ]

    periodos = [
        (CANAL_NACIONAL, "2026-09-01", "2026-09-30", "NACIONAL — septiembre 2026 (mes calendario)"),
        (CANAL_INTERNACIONAL, "2026-08-21", "2026-09-22", "INTERNACIONAL — ciclo 21-ago a 22-sep 2026"),
        (CANAL_DIGITAL, "2026-09-01", "2026-09-30", "DIGITAL — septiembre 2026 (fuera de alcance v1)"),
    ]

    resultados = {}
    for canal, desde, hasta, etiqueta in periodos:
        dominio = [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("sales_channel_id", "=", canal),
            ("invoice_date", ">=", desde),
            ("invoice_date", "<=", hasta),
        ]
        ids, data = _leer_facturas(db, uid, password, models, dominio, campos)
        resultados[canal] = (ids, data)

        print(f"\n  --- {etiqueta} ---")
        print(f"  Facturas posted: {len(data)}")

        vendedores = collections.Counter(
            d["invoice_user_id"][1] if d["invoice_user_id"] else "SIN VENDEDOR" for d in data
        )
        print(f"  Vendedores distintos: {len(vendedores)}")
        for nombre, n in vendedores.most_common(6):
            print(f"      {n:5d}  {nombre}")

        monedas = collections.Counter(d["currency_id"][1] for d in data)
        print(f"  Monedas: {dict(monedas)}")

        tipos = collections.Counter(d["sale_type_id"][1] if d["sale_type_id"] else "N/A" for d in data)
        print(f"  Tipos de venta: {dict(tipos)}")

        estados_pago = collections.Counter(d["payment_state"] for d in data)
        print(f"  payment_state: {dict(estados_pago)}")

    return resultados


def seccion_4_casuistica_contado(db, uid, password, models):
    print("\n" + "=" * 90)
    print("[4] CASUÍSTICA 'CONTADO / PAGO ADELANTADO' — fecha factura vs. fecha de cobro real")
    print("=" * 90)
    print(
        "  Hipótesis a validar: en condiciones de contado o '100% PAGO ADELANTADO', el pago\n"
        "  puede registrarse ANTES de la fecha de la factura (o en un mes distinto), por lo que\n"
        "  un cruce ingenuo por mes-de-factura pierde esos pagos. Se compara contra\n"
        "  account.partial.reconcile.max_date, que es la fecha contable real de conciliación."
    )

    dominio = [
        ("move_type", "=", "out_invoice"),
        ("state", "=", "posted"),
        ("sales_channel_id", "=", CANAL_NACIONAL),
        ("invoice_date", ">=", "2026-08-15"),
        ("invoice_date", "<=", "2026-10-16"),
        ("amount_total", ">", 0),
    ]
    campos = [
        "name", "invoice_date", "payment_state", "amount_total", "amount_residual",
        "invoice_payment_term_id", "sale_type_id", "invoice_payments_widget", "currency_id",
    ]
    _, data = _leer_facturas(db, uid, password, models, dominio, campos)
    print(f"\n  Facturas NACIONAL analizadas (15-ago a 16-oct-2026): {len(data)}")

    terminos_contado = _x(
        db, uid, password, models, "account.payment.term", "search_read",
        [("payment_type", "=", "contado"), ("operation_type", "in", ["ventas", "ventascompras"])],
        fields=["id", "name"],
    )
    ids_contado = {t["id"] for t in terminos_contado}
    print("\n  Términos de pago clasificados como 'contado' (ventas):")
    for t in terminos_contado:
        print(f"      {t['id']:>4}  {t['name']}")

    def fechas_pago(inv):
        widget = inv.get("invoice_payments_widget")
        if not widget or not isinstance(widget, dict):
            return []
        return sorted({c["date"] for c in widget.get("content", [])})

    stats = collections.Counter()
    ejemplos = []
    for inv in data:
        term_id = inv["invoice_payment_term_id"][0] if inv["invoice_payment_term_id"] else None
        es_contado = term_id in ids_contado
        clave = "contado" if es_contado else "credito"
        fechas = fechas_pago(inv)

        stats[(clave, "total")] += 1
        if fechas:
            stats[(clave, "con_pago_registrado")] += 1
            mes_factura = inv["invoice_date"][:7]
            if any(f[:7] != mes_factura for f in fechas):
                stats[(clave, "pago_en_mes_distinto")] += 1
                if es_contado and len(ejemplos) < 6:
                    ejemplos.append(
                        (inv["name"], inv["invoice_date"], fechas, inv["invoice_payment_term_id"][1], inv["amount_total"])
                    )
            if any(f < inv["invoice_date"] for f in fechas):
                stats[(clave, "pago_ANTES_de_la_factura")] += 1

    print("\n  Resultados agregados (clave = (contado|credito, metrica)):")
    for clave, valor in sorted(stats.items()):
        print(f"      {clave}: {valor}")

    print("\n  Ejemplos de facturas CONTADO con pago en un mes calendario distinto al de la factura:")
    for nombre, f_factura, fechas_cobro, termino, monto in ejemplos:
        print(f"      {nombre} | factura={f_factura} | término='{termino}' | monto={monto} | pagos={fechas_cobro}")

    print(
        "\n  Conclusión: un cruce por 'mes de factura == mes de pago' pierde pagos legítimos.\n"
        "  La regla recomendada en el PRD es usar la fecha de conciliación\n"
        "  (account.partial.reconcile.max_date) como fecha efectiva de cobro, no la fecha\n"
        "  del widget de pago ni la fecha de la factura."
    )


def seccion_5_evidencia_conciliacion(db, uid, password, models):
    print("\n" + "=" * 90)
    print("[5] EVIDENCIA DETALLADA: widget de pago vs. account.partial.reconcile.max_date")
    print("    (incluye move_type real de cada conciliación: NUNCA inferir por nombre de diario)")
    print("=" * 90)

    nombres = ["F F01-00007416", "F F01-00007452", "F F01-00007706"]
    for nombre in nombres:
        encontrados = _x(
            db, uid, password, models, "account.move", "search_read",
            [("name", "=", nombre)],
            fields=["name", "invoice_date", "amount_total", "invoice_payments_widget", "payment_state"],
        )
        if not encontrados:
            print(f"\n  {nombre}: no encontrada (puede haber cambiado desde la investigación original).")
            continue
        inv = encontrados[0]
        print(
            f"\n  {inv['name']} | fecha_factura={inv['invoice_date']} | total={inv['amount_total']} "
            f"| estado={inv['payment_state']}"
        )
        widget = inv.get("invoice_payments_widget") or {}
        move_types = []
        for c in widget.get("content", []):
            partial = _x(
                db, uid, password, models, "account.partial.reconcile", "read",
                [c["partial_id"]], fields=["max_date", "amount", "create_date"],
            )[0]
            move_type = None
            if c.get("move_id"):
                mv = _x(db, uid, password, models, "account.move", "read", [c["move_id"]], fields=["move_type"])
                move_type = mv[0]["move_type"] if mv else None
                move_types.append(move_type)
            print(
                f"      widget.date={c['date']}  monto={c['amount']}  "
                f"| partial.max_date={partial['max_date']}  diario={c['journal_name']}  move_type={move_type}"
            )
        if move_types and all(mt == "out_refund" for mt in move_types):
            print(
                "      >>> ALERTA: el 100% de las conciliaciones son 'out_refund' (Nota de Crédito).\n"
                "          Esta factura NO es comisionable (ver regla de exclusión por NC)."
            )
        elif "out_refund" in move_types:
            pct_nc = 100 * move_types.count("out_refund") / len(move_types)
            print(f"      >>> AVISO: {pct_nc:.0f}% de las conciliaciones son NC; solo comisiona el resto.")


def seccion_6_trazabilidad_letras(db, uid, password, models, resultados_vol):
    print("\n" + "=" * 90)
    print("[6] TRAZABILIDAD DE LETRAS (account.bill.form) POR CANAL")
    print("=" * 90)
    print(
        "  Las letras (account.move con move_type='out_bill') NO tienen sales_channel_id ni\n"
        "  sale_type_id propios. La única forma de saber a qué canal pertenece una letra es\n"
        "  trazarla hacia su(s) factura(s) origen vía account.bill.form.invoice_ids."
    )

    for canal, etiqueta in ((CANAL_NACIONAL, "NACIONAL"), (CANAL_INTERNACIONAL, "INTERNACIONAL")):
        ids_facturas, _ = resultados_vol[canal]
        if not ids_facturas:
            continue
        planillas = _x(
            db, uid, password, models, "account.bill.form", "search_read",
            [("invoice_ids", "in", ids_facturas)],
            fields=["name", "invoice_ids", "bills_qty"],
        )
        facturas_con_letra = set()
        for p in planillas:
            facturas_con_letra.update(set(p["invoice_ids"]) & set(ids_facturas))

        pct = 100 * len(facturas_con_letra) / max(1, len(ids_facturas))
        print(
            f"\n  {etiqueta}: {len(facturas_con_letra)} de {len(ids_facturas)} facturas tienen "
            f"planilla de letras asociada ({pct:.1f}%). Planillas encontradas: {len(planillas)}."
        )

    print("\n  Estados de letra (account.move.state) observados en 2026 y su frecuencia:")
    for st in ["to_accept", "collection", "portfolio", "discount", "protested"]:
        n = _x(
            db, uid, password, models, "account.move", "search_count",
            [("move_type", "=", "out_bill"), ("state", "=", st), ("date", ">=", "2026-01-01")],
        )
        print(f"      state={st:<12}: {n}")


def seccion_7b_diarios_excluidos(db, uid, password, models, resultados_vol):
    print("\n" + "=" * 90)
    print("[7b] DIARIOS CONTABLES A EXCLUIR: 'Facturas Sunat' (001) y 'F060 Venta exterior' (060)")
    print("=" * 90)
    print(
        "  Confirmado por el solicitante: estas facturas NO son comisionables,\n"
        "  independientemente del canal, tipo de venta o vendedor."
    )

    for canal, etiqueta in ((CANAL_NACIONAL, "NACIONAL"), (CANAL_INTERNACIONAL, "INTERNACIONAL")):
        ids_facturas, _ = resultados_vol[canal]
        if not ids_facturas:
            continue
        data = []
        for i in range(0, len(ids_facturas), 300):
            lote = ids_facturas[i : i + 300]
            data += _x(db, uid, password, models, "account.move", "read", lote, fields=["journal_id"])
        diarios = collections.Counter(d["journal_id"][1] if d["journal_id"] else "N/A" for d in data)
        total = len(data)
        print(f"\n  {etiqueta}: distribución de diarios ({total} facturas)")
        for nombre, n in diarios.most_common():
            marca = "  <-- EXCLUIR" if nombre in ("Facturas Sunat", "F060 (Venta exterior)") else ""
            print(f"      {n:5d} ({100 * n / max(1, total):5.1f}%)  {nombre}{marca}")


def seccion_7c_nc_vs_transferencia(db, uid, password, models):
    print("\n" + "=" * 90)
    print("[7c] DISTINGUIR 'PAGADO CON NOTA DE CRÉDITO' (no comisiona) DE 'TRANSFERENCIA O")
    print("     APLICACIÓN DE SALDO A FAVOR' (sí comisiona)")
    print("=" * 90)
    print(
        "  Cada conciliación de una factura apunta, vía invoice_payments_widget.content[].move_id,\n"
        "  al asiento que la canceló. Si ese asiento es una Nota de Crédito (move_type='out_refund'),\n"
        "  la factura NO debe comisionar; si es una transferencia bancaria o la aplicación de un\n"
        "  saldo a favor (diario 'Aplicación'), SÍ debe comisionar."
    )

    dominio = [
        ("move_type", "=", "out_invoice"),
        ("state", "=", "posted"),
        ("sales_channel_id", "=", CANAL_NACIONAL),
        ("invoice_date", ">=", "2026-07-01"),
        ("invoice_date", "<=", "2026-09-30"),
        ("payment_state", "in", ["paid", "partial", "in_payment"]),
    ]
    ids = _x(db, uid, password, models, "account.move", "search", dominio, limit=400)
    data = _x(
        db, uid, password, models, "account.move", "read", ids,
        fields=["name", "invoice_date", "payment_state", "invoice_payments_widget"],
    )
    print(f"\n  Facturas analizadas: {len(data)}")

    move_ids_pago = set()
    for inv in data:
        widget = inv.get("invoice_payments_widget") or {}
        for c in widget.get("content", []):
            if c.get("move_id"):
                move_ids_pago.add(c["move_id"])

    print(f"  Asientos de pago/conciliación distintos referenciados: {len(move_ids_pago)}")
    pagos = _x(
        db, uid, password, models, "account.move", "read", list(move_ids_pago),
        fields=["name", "move_type", "journal_id"],
    )
    tipos = collections.Counter(p["move_type"] for p in pagos)
    print(f"  Tipos de asiento que generaron la conciliación: {dict(tipos)}")

    diarios = collections.Counter(p["journal_id"][1] if p["journal_id"] else "N/A" for p in pagos)
    print("\n  Diarios de esos asientos (origen de cada conciliación):")
    for nombre, n in diarios.most_common(15):
        marca = "  <-- NC, NO comisiona" if nombre == "F110 (Venta nacional)" else ""
        print(f"      {n:4d}  {nombre}{marca}")

    ejemplos_nc = [p for p in pagos if p["move_type"] == "out_refund"][:5]
    print("\n  Ejemplos de conciliación vía Nota de Crédito (move_type='out_refund', NO comisiona):")
    for e in ejemplos_nc:
        print(f"      {e['name']} | diario={e['journal_id'][1] if e['journal_id'] else 'N/A'}")

    pct_nc = 100 * sum(1 for p in pagos if p["move_type"] == "out_refund") / max(1, len(pagos))
    print(f"\n  % de asientos de pago que son Nota de Crédito: {pct_nc:.1f}%")


def seccion_7a_catalogo_zonas(db, uid, password, models):
    print("\n" + "=" * 90)
    print("[7a] CATÁLOGO DE ZONAS (agr.sales.comercial.division.zone) — clave real de la")
    print("     matriz de comisiones Nacional (Línea Comercial + Zona)")
    print("=" * 90)
    print(
        "  Confirmado con los Excel reales de Proceso_Manual/nacional/Porcentajes/: la\n"
        "  comisión Nacional se busca por la combinación 'Línea Comercial/Zona'\n"
        "  (ej. 'PETMEDICA/LIMA 1/ATREVIA'), no solo por línea comercial como en Internacional."
    )
    zonas = _x(db, uid, password, models, "agr.sales.comercial.division.zone", "search_read", [], fields=["id", "name"])
    print(f"\n  Total de zonas en Odoo: {len(zonas)}")
    for z in zonas:
        print(f"      {z['id']:>3}  {z['name']}")


def seccion_7_vendedores_genericos(resultados_vol):
    print("\n" + "=" * 90)
    print("[7] VENDEDORES 'GENÉRICOS' QUE CONCENTRAN FACTURAS (sin vendedor comisionable real)")
    print("    Confirmado: MARKETING (incl. 'MARKETING INT') y OFICINA se excluyen en AMBOS canales")
    print("=" * 90)
    for canal, etiqueta in ((CANAL_NACIONAL, "NACIONAL"), (CANAL_INTERNACIONAL, "INTERNACIONAL")):
        _, data = resultados_vol[canal]
        equipos = collections.Counter(d["team_id"][1] if d["team_id"] else "N/A" for d in data)
        print(f"\n  Facturas {etiqueta} agrupadas por equipo (crm.team):")
        for equipo, n in equipos.most_common():
            pct = 100 * n / max(1, len(data))
            excluir = equipo.upper().startswith("MARKETING") or equipo.upper() == "OFICINA"
            marca = "  <-- EXCLUIR (no comisiona)" if excluir else ""
            print(f"      {n:5d} ({pct:5.1f}%)  {equipo}{marca}")


def seccion_7d_boletas(db, uid, password, models):
    print("\n" + "=" * 90)
    print("[7d] TIPOS DE DOCUMENTO: BOLETAS NO SON COMISIONABLES EN NINGÚN CANAL")
    print("=" * 90)
    for canal, etiqueta, fdesde, fhasta in (
        (CANAL_NACIONAL, "NACIONAL", "2026-09-01", "2026-09-30"),
        (CANAL_INTERNACIONAL, "INTERNACIONAL", "2026-08-21", "2026-09-22"),
    ):
        dominio = [
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("state", "=", "posted"),
            ("sales_channel_id", "=", canal),
            ("invoice_date", ">=", fdesde),
            ("invoice_date", "<=", fhasta),
        ]
        ids = _x(db, uid, password, models, "account.move", "search", dominio)
        data = _x(db, uid, password, models, "account.move", "read", ids, fields=["l10n_latam_document_type_id"])
        tipos = collections.Counter(
            d["l10n_latam_document_type_id"][1] if d["l10n_latam_document_type_id"] else "N/A" for d in data
        )
        print(f"\n  {etiqueta} ({len(data)} documentos):")
        for nombre, n in tipos.most_common():
            excluir = "Boleta" in nombre
            marca = "  <-- EXCLUIR (no comisiona)" if excluir else ""
            print(f"      {n:5d} ({100 * n / max(1, len(data)):5.1f}%)  {nombre}{marca}")


def seccion_7e_ttg_doble_campo(db, uid, password, models):
    print("\n" + "=" * 90)
    print("[7e] TTG: VERIFICAR POR AMBOS CAMPOS (sale_type_id Y condición de pago)")
    print("=" * 90)
    dominio = [
        ("move_type", "=", "out_invoice"),
        ("state", "=", "posted"),
        ("sales_channel_id", "=", CANAL_NACIONAL),
        ("invoice_date", ">=", "2026-09-01"),
        ("invoice_date", "<=", "2026-09-30"),
    ]
    ids = _x(db, uid, password, models, "account.move", "search", dominio)
    data = _x(db, uid, password, models, "account.move", "read", ids, fields=["sale_type_id", "invoice_payment_term_id"])

    def es_ttg_sale_type(d):
        return bool(d["sale_type_id"] and d["sale_type_id"][1] == "TTG - TRANS TÍT GRAT")

    def es_ttg_term(d):
        return bool(d["invoice_payment_term_id"] and "TTG" in d["invoice_payment_term_id"][1])

    solo_sale_type = sum(1 for d in data if es_ttg_sale_type(d) and not es_ttg_term(d))
    solo_term = sum(1 for d in data if es_ttg_term(d) and not es_ttg_sale_type(d))
    ambos = sum(1 for d in data if es_ttg_sale_type(d) and es_ttg_term(d))
    print(f"  Solo sale_type_id=TTG (sin término TTG): {solo_sale_type}  <-- se perdería si solo se filtra por término")
    print(f"  Solo invoice_payment_term_id=TTG (sin sale_type TTG): {solo_term}")
    print(f"  Ambos campos en TTG a la vez: {ambos}")
    print(f"  Total a excluir (OR de ambos campos): {solo_sale_type + solo_term + ambos}")


def seccion_7f_letra_a_pedido(db, uid, password, models):
    print("\n" + "=" * 90)
    print("[7f] TRAZABILIDAD COMPLETA: Letra -> Planilla -> Factura -> invoice_origin (Nº de pedido)")
    print("=" * 90)
    letras = _x(
        db, uid, password, models, "account.move", "search_read",
        [("move_type", "=", "out_bill"), ("state", "in", ["portfolio", "collection", "discount"])],
        fields=["name", "bill_form_id", "l10n_latam_boe_number", "invoice_origin"], limit=3, order="id desc",
    )
    for lt in letras:
        print(f"\n  Letra: {lt['name']} | BOE={lt.get('l10n_latam_boe_number')} | invoice_origin propio={lt.get('invoice_origin')!r}")
        bf_ref = lt.get("bill_form_id")
        if not bf_ref:
            print("     (sin bill_form_id)")
            continue
        bf = _x(db, uid, password, models, "account.bill.form", "read", [bf_ref[0]], fields=["name", "invoice_ids"])[0]
        print(f"     Planilla: {bf['name']}")
        inv_ids = bf.get("invoice_ids") or []
        if inv_ids:
            invs = _x(db, uid, password, models, "account.move", "read", inv_ids, fields=["name", "invoice_origin"])
            for inv in invs:
                print(f"       Factura: {inv['name']} | invoice_origin (Nº de pedido/OV): {inv.get('invoice_origin')!r}")

    letras2 = _x(db, uid, password, models, "account.move", "search_read", [("move_type", "=", "out_bill")], fields=["invoice_origin"], limit=500)
    con_origin = sum(1 for l in letras2 if l.get("invoice_origin"))
    print(f"\n  De {len(letras2)} letras muestreadas, {con_origin} ({100*con_origin/len(letras2):.0f}%) tienen "
          f"invoice_origin propio (contiene el nombre de la Planilla, ej. 'FLC-02726', no el pedido directamente).")


def seccion_7g_transitory_receivable(db, uid, password, models):
    print("\n" + "=" * 90)
    print("[7g] DIARIO 'Transitory receivable and payable' (TRP): traspaso Factura->Letra, NO cobro real")
    print("=" * 90)
    j = _x(db, uid, password, models, "account.journal", "search_read", [("name", "=", "Transitory receivable and payable")], fields=["id", "name", "code", "type"])
    print(f"  Diario: {j}")
    moves = _x(db, uid, password, models, "account.move", "search_read", [("journal_id", "=", j[0]["id"])], fields=["name", "move_type", "ref"], limit=5, order="id desc")
    print("\n  Asientos recientes de este diario (nótese 'Redeem Bill of Exchange' en la referencia):")
    for mv in moves:
        print(f"      {mv['name']} | move_type={mv['move_type']} | ref={mv.get('ref')}")


def main():
    db, uid, password, models, version = _connect()
    seccion_1_conexion(db, uid, models, version)
    seccion_2_catalogos(db, uid, password, models)
    resultados_vol = seccion_3_volumetria(db, uid, password, models)
    seccion_4_casuistica_contado(db, uid, password, models)
    seccion_5_evidencia_conciliacion(db, uid, password, models)
    seccion_6_trazabilidad_letras(db, uid, password, models, resultados_vol)
    seccion_7a_catalogo_zonas(db, uid, password, models)
    seccion_7_vendedores_genericos(resultados_vol)
    seccion_7b_diarios_excluidos(db, uid, password, models, resultados_vol)
    seccion_7c_nc_vs_transferencia(db, uid, password, models)
    seccion_7d_boletas(db, uid, password, models)
    seccion_7e_ttg_doble_campo(db, uid, password, models)
    seccion_7f_letra_a_pedido(db, uid, password, models)
    seccion_7g_transitory_receivable(db, uid, password, models)

    print("\n" + "=" * 90)
    print("FIN — todas las cifras anteriores son las que respaldan")
    print("docs/PRD_COMISIONES_NACIONAL_INTERNACIONAL.html")
    print("=" * 90)


if __name__ == "__main__":
    main()
