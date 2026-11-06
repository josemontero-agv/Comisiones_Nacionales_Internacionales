# -*- coding: utf-8 -*-
"""Evidencia adicional, reproducible y SOLO LECTURA, para el PRD de comisiones.

Verifica en Odoo 16:
- líneas, productos y cuentas de los documentos mostrados como evidencia;
- campos técnicos de cliente/país y línea comercial;
- resolución bulk del país del cliente internacional;
- productos/cuentas relacionados con exclusiones y Notas de Débito;
- mapeo de "Aminoplex Forte x 100 ml" y existencia de beneficiarios.

Solo invoca ``fields_get``, ``search_read`` y ``search_count``. Las lecturas se
paginan por ``id`` y siempre solicitan campos explícitos.
"""

import collections
import os
import sys
import xmlrpc.client

from dotenv import load_dotenv


PAGE_SIZE = 300
CANAL_INTERNACIONAL = 2
FECHA_DESDE = "2026-01-01"
FECHA_HASTA = "2026-11-06"


try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def conectar():
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    url = os.environ["ODOO_URL"].rstrip("/")
    db = os.environ["ODOO_DB"]
    user = os.environ["ODOO_USER"]
    password = os.environ["ODOO_PASSWORD"]
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, user, password, {})
    if not uid:
        raise SystemExit("Autenticación fallida")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
    return db, uid, password, models, common.version()


def ejecutar(ctx, modelo, metodo, args=None, **kwargs):
    db, uid, password, models = ctx
    return models.execute_kw(
        db, uid, password, modelo, metodo, args or [], kwargs
    )


def campos_disponibles(ctx, modelo, candidatos):
    definiciones = ejecutar(
        ctx,
        modelo,
        "fields_get",
        [],
        attributes=["string", "type", "relation"],
    )
    return [campo for campo in candidatos if campo in definiciones], definiciones


def buscar_paginado(ctx, modelo, dominio, campos, limite_total=None):
    """Pagina por ID para evitar offsets costosos y respuestas sin límite."""
    filas = []
    ultimo_id = 0
    while limite_total is None or len(filas) < limite_total:
        limite = PAGE_SIZE
        if limite_total is not None:
            limite = min(limite, limite_total - len(filas))
        lote = ejecutar(
            ctx,
            modelo,
            "search_read",
            [dominio + [("id", ">", ultimo_id)]],
            fields=campos,
            order="id asc",
            limit=limite,
        )
        if not lote:
            break
        filas.extend(lote)
        ultimo_id = lote[-1]["id"]
    return filas


def dominio_or_ilike(campo, textos):
    if len(textos) == 1:
        return [(campo, "ilike", textos[0])]
    return ["|"] * (len(textos) - 1) + [
        (campo, "ilike", texto) for texto in textos
    ]


def nombre_m2o(valor):
    return valor[1] if valor else "—"


def seccion_campos(ctx):
    print("\n[1] CAMPOS TÉCNICOS VERIFICADOS")
    candidatos = {
        "account.move": [
            "name", "move_type", "l10n_latam_document_type_id", "partner_id",
            "commercial_partner_id", "partner_shipping_id", "invoice_line_ids",
            "sales_channel_id", "invoice_origin", "invoice_date", "state",
        ],
        "account.move.line": [
            "move_id", "name", "display_type", "product_id", "account_id",
            "price_subtotal", "price_total", "quantity",
            "commercial_line_international_id", "commercial_line_national_id",
            "line_commercial_id", "sale_line_ids",
        ],
        "sale.order.line": [
            "order_id", "product_id", "line_commercial_zone_id",
            "commercial_line_international_id", "commercial_line_national_id",
            "line_commercial_id",
        ],
        "res.partner": [
            "name", "parent_id", "commercial_partner_id", "country_id",
            "type", "is_company",
        ],
        "res.country": ["name", "code"],
        "product.product": [
            "name", "display_name", "default_code", "product_tmpl_id",
            "commercial_line_international_id", "commercial_line_national_id",
            "line_commercial_id",
        ],
        "product.template": [
            "name", "default_code", "commercial_line_international_id",
            "commercial_line_national_id", "line_commercial_id",
            "property_account_income_id", "categ_id",
        ],
        "account.account": ["code", "name", "account_type"],
    }
    resultado = {}
    for modelo, lista in candidatos.items():
        presentes, definiciones = campos_disponibles(ctx, modelo, lista)
        resultado[modelo] = presentes
        print(f"  {modelo}:")
        for campo in presentes:
            meta = definiciones[campo]
            destino = f" -> {meta.get('relation')}" if meta.get("relation") else ""
            print(f"    {campo}: {meta.get('type')}{destino}")
        ausentes = sorted(set(lista) - set(presentes))
        if ausentes:
            print(f"    NO disponibles: {', '.join(ausentes)}")
    return resultado


def seccion_documentos_imagenes(ctx, campos):
    print("\n[2] DOCUMENTOS DE LAS IMÁGENES: LÍNEAS, PRODUCTOS Y CUENTAS")
    move_fields = [
        c for c in [
            "name", "move_type", "l10n_latam_document_type_id", "partner_id",
            "invoice_date", "invoice_line_ids", "sales_channel_id",
        ] if c in campos["account.move"]
    ]
    documentos = buscar_paginado(
        ctx,
        "account.move",
        [("name", "in", ["F F15-00000495", "F F15-00000492"])],
        move_fields,
    )
    ids = [d["id"] for d in documentos]
    line_fields = [
        c for c in [
            "move_id", "name", "display_type", "product_id", "account_id",
            "price_subtotal", "price_total", "quantity",
            "commercial_line_international_id", "line_commercial_id",
        ] if c in campos["account.move.line"]
    ]
    lineas = buscar_paginado(
        ctx,
        "account.move.line",
        [("move_id", "in", ids), ("display_type", "=", "product")],
        line_fields,
    ) if ids else []
    por_move = collections.defaultdict(list)
    for linea in lineas:
        por_move[linea["move_id"][0]].append(linea)
    for documento in documentos:
        print(
            f"  {documento['name']} | tipo={documento.get('move_type')} "
            f"| doc={nombre_m2o(documento.get('l10n_latam_document_type_id'))} "
            f"| cliente={nombre_m2o(documento.get('partner_id'))}"
        )
        for linea in por_move[documento["id"]]:
            print(
                "    "
                f"etiqueta={linea.get('name')!r} | "
                f"producto={nombre_m2o(linea.get('product_id'))} | "
                f"cuenta={nombre_m2o(linea.get('account_id'))} | "
                f"subtotal={linea.get('price_subtotal')} | "
                f"línea={nombre_m2o(linea.get('commercial_line_international_id') or linea.get('line_commercial_id'))}"
            )


def seccion_catalogos_exclusion(ctx, campos):
    print("\n[3] PRODUCTOS Y CUENTAS CANDIDATOS A EXCLUSIÓN")
    conceptos_verificados = [
        "GASTOS EXPO", "FLETE DE EXPORTACION", "TRIBUTOS - INTERESES",
        "FLETE_EXP",
    ]
    product_fields = [
        c for c in [
            "name", "default_code", "commercial_line_international_id",
            "commercial_line_national_id", "line_commercial_id",
            "property_account_income_id", "categ_id",
        ] if c in campos["product.template"]
    ]
    productos = buscar_paginado(
        ctx,
        "product.template",
        dominio_or_ilike("name", conceptos_verificados),
        product_fields,
        limite_total=50,
    )
    print(f"  Productos coincidentes: {len(productos)}")
    for p in productos:
        print(
            f"    id={p['id']} | {p.get('default_code') or 's/código'} | {p['name']} "
            f"| ingreso={nombre_m2o(p.get('property_account_income_id'))} "
            f"| línea-int={nombre_m2o(p.get('commercial_line_international_id'))}"
        )

    account_fields = [
        c for c in ["code", "name", "account_type"]
        if c in campos["account.account"]
    ]
    codigos_cuenta_verificados = [
        "6593002", "7011001", "7012101", "7022101",
        "7599001", "7599006", "7599009", "7722001",
    ]
    cuentas = buscar_paginado(
        ctx,
        "account.account",
        [("code", "in", codigos_cuenta_verificados)],
        account_fields,
        limite_total=50,
    )
    print(f"  Cuentas coincidentes: {len(cuentas)}")
    for cuenta in cuentas:
        print(
            f"    id={cuenta['id']} | {cuenta.get('code')} {cuenta.get('name')} "
            f"| tipo={cuenta.get('account_type')}"
        )


def seccion_notas_debito(ctx, campos):
    print("\n[4] NOTAS DE DÉBITO: MUESTRA Y CLASIFICACIÓN POR LÍNEA")
    tipos = buscar_paginado(
        ctx,
        "l10n_latam.document.type",
        dominio_or_ilike("name", ["Nota de Débito", "Nota de Debito"]),
        ["name", "code"],
        limite_total=30,
    )
    print(f"  Tipos encontrados: {[(t['id'], t['name'], t.get('code')) for t in tipos]}")
    if not tipos:
        return
    move_fields = [
        c for c in [
            "name", "move_type", "l10n_latam_document_type_id", "partner_id",
            "invoice_date", "sales_channel_id",
        ] if c in campos["account.move"]
    ]
    documentos = buscar_paginado(
        ctx,
        "account.move",
        [
            ("state", "=", "posted"),
            ("l10n_latam_document_type_id", "in", [t["id"] for t in tipos]),
            ("invoice_date", ">=", FECHA_DESDE),
            ("invoice_date", "<=", FECHA_HASTA),
            ("sales_channel_id", "in", [1, 2]),
        ],
        move_fields,
        limite_total=80,
    )
    ids = [d["id"] for d in documentos]
    line_fields = [
        c for c in [
            "move_id", "name", "display_type", "product_id", "account_id",
            "price_subtotal", "commercial_line_international_id",
            "commercial_line_national_id", "line_commercial_id",
        ] if c in campos["account.move.line"]
    ]
    lineas = buscar_paginado(
        ctx,
        "account.move.line",
        [("move_id", "in", ids), ("display_type", "=", "product")],
        line_fields,
    ) if ids else []
    print(f"  Documentos ND 2026 (muestra acotada): {len(documentos)}; líneas: {len(lineas)}")
    resumen = collections.Counter()
    for linea in lineas:
        cuenta = nombre_m2o(linea.get("account_id"))
        producto = nombre_m2o(linea.get("product_id"))
        resumen[(cuenta, producto)] += 1
    for (cuenta, producto), cantidad in resumen.most_common(30):
        print(f"    {cantidad:>3} | cuenta={cuenta} | producto={producto}")


def seccion_paises_internacional(ctx, campos):
    print("\n[5] CLIENTE Y PAÍS EN INTERNACIONAL: RESOLUCIÓN BULK")
    move_fields = [
        c for c in [
            "name", "partner_id", "commercial_partner_id", "partner_shipping_id",
            "invoice_date", "sales_channel_id", "state",
        ] if c in campos["account.move"]
    ]
    facturas = buscar_paginado(
        ctx,
        "account.move",
        [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("sales_channel_id", "=", CANAL_INTERNACIONAL),
            ("invoice_date", ">=", FECHA_DESDE),
            ("invoice_date", "<=", FECHA_HASTA),
        ],
        move_fields,
    )
    partner_ids = set()
    for factura in facturas:
        for campo in ("partner_id", "commercial_partner_id", "partner_shipping_id"):
            valor = factura.get(campo)
            if valor:
                partner_ids.add(valor[0])
    partner_fields = [
        c for c in [
            "name", "parent_id", "commercial_partner_id", "country_id",
            "type", "is_company",
        ] if c in campos["res.partner"]
    ]
    partners = buscar_paginado(
        ctx,
        "res.partner",
        [("id", "in", list(partner_ids))],
        partner_fields,
    ) if partner_ids else []
    por_id = {p["id"]: p for p in partners}
    country_ids = {
        p["country_id"][0] for p in partners if p.get("country_id")
    }
    country_fields = [
        c for c in ["name", "code"] if c in campos["res.country"]
    ]
    countries = buscar_paginado(
        ctx,
        "res.country",
        [("id", "in", list(country_ids))],
        country_fields,
    ) if country_ids else []
    country_by_id = {c["id"]: c for c in countries}
    paises = collections.Counter()
    origen = collections.Counter()
    faltantes = []
    for factura in facturas:
        directo = por_id.get(factura["partner_id"][0], {}) if factura.get("partner_id") else {}
        comercial_ref = factura.get("commercial_partner_id") or directo.get("commercial_partner_id")
        comercial = por_id.get(comercial_ref[0], {}) if comercial_ref else {}
        envio_ref = factura.get("partner_shipping_id")
        envio = por_id.get(envio_ref[0], {}) if envio_ref else {}
        if comercial.get("country_id"):
            country_id, country_name = comercial["country_id"]
            fuente = "commercial_partner_id.country_id"
        elif directo.get("country_id"):
            country_id, country_name = directo["country_id"]
            fuente = "partner_id.country_id"
        elif envio.get("country_id"):
            country_id, country_name = envio["country_id"]
            fuente = "partner_shipping_id.country_id (fallback)"
        else:
            country_id, country_name = None, "SIN PAÍS"
            fuente = "sin país"
            faltantes.append(factura["name"])
        codigo = country_by_id.get(country_id, {}).get("code") if country_id else None
        paises[(codigo or "—", country_name)] += 1
        origen[fuente] += 1
    print(f"  Facturas internacionales {FECHA_DESDE}..{FECHA_HASTA}: {len(facturas)}")
    print(f"  Fuente usada: {dict(origen)}")
    print("  Países:")
    for (codigo, pais), cantidad in paises.most_common():
        print(f"    {cantidad:>4} | {codigo} | {pais}")
    print(f"  Facturas sin país (primeras 20): {faltantes[:20]}")


def seccion_aminoplex_y_personas(ctx, campos):
    print("\n[6] AMINOPLEX Y BENEFICIARIOS")
    product_fields = [
        c for c in [
            "name", "default_code", "commercial_line_international_id",
            "commercial_line_national_id", "line_commercial_id",
            "property_account_income_id",
        ] if c in campos["product.template"]
    ]
    productos = buscar_paginado(
        ctx,
        "product.template",
        [("name", "ilike", "Aminoplex Forte")],
        product_fields,
        limite_total=100,
    )
    for p in productos:
        print(
            f"  Producto id={p['id']} | código={p.get('default_code')} | {p['name']} "
            f"| línea-int={nombre_m2o(p.get('commercial_line_international_id'))} "
            f"| línea-gen={nombre_m2o(p.get('line_commercial_id'))}"
        )

    facturas = buscar_paginado(
        ctx,
        "account.move",
        [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("sales_channel_id", "=", CANAL_INTERNACIONAL),
            ("invoice_date", ">=", FECHA_DESDE),
            ("invoice_date", "<=", FECHA_HASTA),
        ],
        ["name"],
    )
    line_fields = [
        c for c in [
            "move_id", "name", "product_id", "account_id", "sale_line_ids",
            "price_subtotal",
        ] if c in campos["account.move.line"]
    ]
    lineas = buscar_paginado(
        ctx,
        "account.move.line",
        [
            ("move_id", "in", [f["id"] for f in facturas]),
            ("display_type", "=", "product"),
            ("name", "ilike", "AMINOPLEX FORTE"),
        ],
        line_fields,
    ) if facturas else []
    sale_line_ids = {
        sale_line_id
        for linea in lineas
        for sale_line_id in (linea.get("sale_line_ids") or [])
    }
    sale_fields = [
        c for c in [
            "order_id", "product_id", "line_commercial_zone_id",
            "commercial_line_international_id", "line_commercial_id",
        ] if c in campos["sale.order.line"]
    ]
    sale_lines = buscar_paginado(
        ctx,
        "sale.order.line",
        [("id", "in", list(sale_line_ids))],
        sale_fields,
    ) if sale_line_ids else []
    sale_by_id = {linea["id"]: linea for linea in sale_lines}
    product_ids = {
        linea["product_id"][0] for linea in lineas if linea.get("product_id")
    }
    variant_fields = [
        c for c in [
            "name", "display_name", "default_code", "product_tmpl_id",
            "commercial_line_international_id", "commercial_line_national_id",
            "line_commercial_id",
        ] if c in campos["product.product"]
    ]
    variants = buscar_paginado(
        ctx,
        "product.product",
        [("id", "in", list(product_ids))],
        variant_fields,
    ) if product_ids else []
    variant_by_id = {variant["id"]: variant for variant in variants}
    template_ids = {
        variant["product_tmpl_id"][0]
        for variant in variants
        if variant.get("product_tmpl_id")
    }
    templates = buscar_paginado(
        ctx,
        "product.template",
        [("id", "in", list(template_ids))],
        product_fields,
    ) if template_ids else []
    template_by_id = {template["id"]: template for template in templates}
    print("  Líneas facturadas de Aminoplex Forte en Internacional durante 2026:")
    for linea in lineas:
        enlaces = [sale_by_id[i] for i in linea.get("sale_line_ids", []) if i in sale_by_id]
        alcance = [
            {
                campo: nombre_m2o(sale.get(campo))
                for campo in (
                    "line_commercial_zone_id",
                    "commercial_line_international_id",
                    "line_commercial_id",
                )
                if campo in sale
            }
            for sale in enlaces
        ]
        variant = variant_by_id.get(linea["product_id"][0], {}) if linea.get("product_id") else {}
        template_ref = variant.get("product_tmpl_id")
        template = template_by_id.get(template_ref[0], {}) if template_ref else {}
        linea_producto = (
            variant.get("commercial_line_international_id")
            or variant.get("line_commercial_id")
            or template.get("commercial_line_international_id")
            or template.get("line_commercial_id")
        )
        print(
            f"    {nombre_m2o(linea.get('move_id'))} | {linea.get('name')} "
            f"| producto={nombre_m2o(linea.get('product_id'))} "
            f"| cuenta={nombre_m2o(linea.get('account_id'))} "
            f"| línea-producto={nombre_m2o(linea_producto)} "
            f"| pedido/línea={alcance}"
        )

    nombres = [
        "Ariana Carmona", "Vanessa Parker", "Sandra Meneses",
        "Umberto Calderón", "Luis Chávez", "Mayumi Garcilazo", "Ivonne Panta",
    ]
    usuarios = buscar_paginado(
        ctx,
        "res.users",
        dominio_or_ilike("name", nombres),
        ["name", "active", "partner_id"],
        limite_total=50,
    )
    encontrados = {u["name"]: u for u in usuarios}
    print("  Usuarios Odoo encontrados:")
    for nombre in nombres:
        coincidencias = [u for n, u in encontrados.items() if nombre.lower() in n.lower()]
        print(f"    {nombre}: {[(u['id'], u['name'], u['active']) for u in coincidencias] or 'no encontrado por nombre'}")


def main():
    db, uid, password, models, version = conectar()
    ctx = (db, uid, password, models)
    print(f"Odoo {version.get('server_version')} | uid={uid} | SOLO LECTURA")
    campos = seccion_campos(ctx)
    seccion_documentos_imagenes(ctx, campos)
    seccion_catalogos_exclusion(ctx, campos)
    seccion_notas_debito(ctx, campos)
    seccion_paises_internacional(ctx, campos)
    seccion_aminoplex_y_personas(ctx, campos)


if __name__ == "__main__":
    main()
