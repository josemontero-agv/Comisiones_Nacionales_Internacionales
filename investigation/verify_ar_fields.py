# -*- coding: utf-8 -*-
import xmlrpc.client
import os
from dotenv import load_dotenv

def verify_fields():
    # Cargar env
    env_path = '.env.produccion'
    load_dotenv(env_path)
    
    url = os.getenv('ODOO_URL')
    db = os.getenv('ODOO_DB')
    username = os.getenv('ODOO_USER')
    password = os.getenv('ODOO_PASSWORD')
    
    if not all([url, db, username, password]):
        print("[ERROR] Faltan credenciales")
        return

    print(f"Conectando a {url}...")
    try:
        common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
        uid = common.authenticate(db, username, password, {})
        models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
        
        if not uid:
            print("[ERROR] Auth fallida")
            return
        
        print("[OK] Conectado")
        
        models_to_check = ['account.move', 'account.move.line', 'res.partner', 'agr.credit.customer']
        
        fields_to_verify = [
            ('account.move', 'invoice_date', 'Fecha de Factura'),
            ('account.move', 'date', 'Fecha Contabilización'),
            ('account.move', 'invoice_date_due', 'Fecha Vencimiento'),
            ('account.move', 'l10n_latam_document_type_id', 'Tipo de Documento'),
            ('account.move', 'name', 'Numero de Documento'),
            ('account.move', 'l10n_latam_boe_number', 'Letra'),
            ('account.move', 'invoice_origin', 'Origen'),
            ('account.move.line', 'account_id', 'Cuenta (Relation)'),
            ('account.account', 'code', 'Cuenta Code'),
            ('account.account', 'name', 'Cuenta Name'),
            ('res.partner', 'vat', 'Ruc'),
            ('res.partner', 'name', 'Cliente Name'),
            ('account.move', 'currency_id', 'Moneda'),
            ('account.move', 'amount_total', 'Monto Total'),
            ('account.move', 'amount_residual', 'Monto Residual'),
            ('account.move', 'invoice_payment_term_id', 'Término de Pago'),
            ('account.move.line', 'name', 'Nombre de Línea'),
            ('account.move', 'invoice_user_id', 'Vendedor'),
            ('agr.credit.customer', 'partner_groups_ids', 'Linea Comercial'),
            ('res.partner', 'state_id', 'Provincia'),
            ('res.partner', 'l10n_pe_district', 'Distrito'),
            ('res.partner', 'country_id', 'Pais'),
            ('agr.credit.customer', 'sub_channel_id', 'Sub Canal'),
            ('account.move', 'sales_channel_id', 'Canal de Venta'),
            ('account.move', 'sales_type_id', 'Tipo de Venta'),
        ]

        print("\n" + "="*80)
        print(f"{'MODELO':<25} | {'CAMPO':<30} | {'ESTADO':<10} | {'TIPO':<10}")
        print("-" * 80)

        for model, field, description in fields_to_verify:
            try:
                field_info = models.execute_kw(db, uid, password, model, 'fields_get', [[field]], {'attributes': ['type', 'string']})
                if field in field_info:
                    print(f"{model:<25} | {field:<30} | {'EXISTE':<10} | {field_info[field]['type']:<10} ({description})")
                else:
                    # Intentar buscar variaciones si no existe
                    print(f"{model:<25} | {field:<30} | {'NO EXISTE':<10} | {'-':<10} ({description})")
            except Exception:
                print(f"{model:<25} | {field:<30} | {'ERROR':<10} | {'-':<10} ({description})")

        # Buscar variaciones comunes para los que no existen
        print("\n" + "="*80)
        print("BUSCANDO VARIACIONES PARA CAMPOS NO ENCONTRADOS O DUDOSOS")
        print("-" * 80)
        
        # Variaciones para I10nn...
        for model in ['account.move']:
            fields = models.execute_kw(db, uid, password, model, 'fields_get', [], {'attributes': ['string']})
            latam_fields = [f for f in fields if 'latam' in f.lower() or 'boe' in f.lower()]
            print(f"\nCampos Latam/BOE en {model}:")
            for f in latam_fields:
                print(f"  - {f}: {fields[f]['string']}")

        # Variaciones para ventas/canales
        sales_fields = [f for f in fields if 'sale' in f.lower() or 'channel' in f.lower() or 'team' in f.lower()]
        print(f"\nCampos de Ventas/Canales en account.move:")
        for f in sales_fields:
            print(f"  - {f}: {fields[f]['string']}")

    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == '__main__':
    verify_fields()
