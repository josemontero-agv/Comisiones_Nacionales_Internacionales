# -*- coding: utf-8 -*-
"""
Script de investigación PROFUNDA sobre 'account.bill.form' y su relación con Letras.
"""

import xmlrpc.client
import os
from dotenv import load_dotenv

def investigate_bill_form():
    load_dotenv('.env')
    
    url = os.getenv('ODOO_URL')
    db = os.getenv('ODOO_DB')
    username = os.getenv('ODOO_USER')
    password = os.getenv('ODOO_PASSWORD')
    
    if not all([url, db, username, password]):
        print("[ERROR] Faltan variables de entorno")
        return

    print(f"Conectando a {url}...")
    common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
    uid = common.authenticate(db, username, password, {})
    models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
    
    if not uid:
        print("[ERROR] Auth fallida")
        return

    print("="*60)
    print("ANÁLISIS DE MODELO: account.bill.form")
    print("="*60)

    try:
        # 1. Obtener campos de account.bill.form
        fields = models.execute_kw(db, uid, password, 'account.bill.form', 'fields_get', [], {})
        print(f"\n[1] Campos encontrados ({len(fields)}):")
        print("-" * 40)
        for fname, finfo in sorted(fields.items()):
            print(f"  - {fname}: {finfo.get('type')} ({finfo.get('string')})")

        # 2. Buscar registros de ejemplo (Por cobrar y Por pagar)
        print("\n[2] Buscando registros de ejemplo...")
        print("-" * 40)
        
        # Intentamos buscar 5 registros recientes
        ids = models.execute_kw(db, uid, password, 'account.bill.form', 'search', [[]], {'limit': 5})
        
        if ids:
            data = models.execute_kw(db, uid, password, 'account.bill.form', 'read', [ids], {'fields': []}) # Leer todos
            
            for rec in data:
                print(f"\n--- ID: {rec['id']} ({rec.get('display_name')}) ---")
                # Mostrar campos clave para entender la relación
                keys_to_show = ['name', 'type', 'state', 'move_id', 'invoice_ids', 'amount_total', 'partner_id']
                for k in keys_to_show:
                    val = rec.get(k)
                    if val:
                        print(f"  {k}: {val}")
        else:
            print("No se encontraron registros en account.bill.form")

    except Exception as e:
        print(f"\n[ERROR] El modelo 'account.bill.form' podría no existir o no ser accesible: {e}")

if __name__ == '__main__':
    investigate_bill_form()
