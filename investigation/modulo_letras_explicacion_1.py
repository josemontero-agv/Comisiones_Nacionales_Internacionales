# -*- coding: utf-8 -*-
"""
Script independiente para investigar el modelo de letras de cambio en Odoo.
No depende de la app Flask para evitar problemas de importación.
"""

import xmlrpc.client
import os
from dotenv import load_dotenv

def investigate_letters_model():
    """Investiga el modelo de letras de cambio en Odoo."""
    
    # Cargar variables de entorno manualmente
    load_dotenv('.env')
    
    url = os.getenv('ODOO_URL')
    db = os.getenv('ODOO_DB')
    username = os.getenv('ODOO_USER')
    password = os.getenv('ODOO_PASSWORD')
    
    if not all([url, db, username, password]):
        print("[ERROR] Faltan variables de entorno en .env.desarrollo")
        return

    print(f"Conectando a {url}...")
    
    try:
        common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
        uid = common.authenticate(db, username, password, {})
        
        if not uid:
            print("[ERROR] Autenticación fallida")
            return
            
        models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
        print("[OK] Conectado exitosamente")
        
        print("=" * 80)
        print("INVESTIGACIÓN DEL MODELO DE LETRAS DE CAMBIO")
        print("=" * 80)
        
        # 1. Obtener todos los campos de account.move
        print("\n[1] Campos disponibles en account.move:")
        print("-" * 80)
        
        fields_info = models.execute_kw(db, uid, password, 'account.move', 'fields_get', [], {})
        
        if fields_info:
            # Filtrar campos relacionados con letras de cambio
            boe_fields = {k: v for k, v in fields_info.items() 
                         if any(x in k.lower() for x in ['boe', 'letter', 'bill'])}
            
            print(f"Total de campos en account.move: {len(fields_info)}")
            print(f"Campos relacionados con letras: {len(boe_fields)}")
            print("\nCampos encontrados:")
            for field_name, field_info in sorted(boe_fields.items()):
                print(f"  - {field_name}: {field_info.get('type')} ({field_info.get('string')})")
        
        # 3. Buscar registros de ejemplo
        print("\n[2] Analizando registros de ejemplo:")
        print("-" * 80)
        
        # Buscar facturas que tengan algún valor en campos tipo boe/letter
        domain = []
        if 'l10n_latam_boe_number' in fields_info:
            domain = [('l10n_latam_boe_number', '!=', False)]
        
        sample_moves = models.execute_kw(db, uid, password, 'account.move', 'search_read', 
            [domain], 
            {'fields': ['id', 'name', 'state', 'move_type'], 'limit': 5}
        )
        
        if sample_moves:
            print(f"Encontrados {len(sample_moves)} registros con letras:")
            for move in sample_moves:
                print(f"  ID: {move['id']}, Name: {move['name']}, Type: {move['move_type']}")
                
                # Inspeccionar detalle completo del primero
                if move == sample_moves[0]:
                    print("\n  Detalle del primer registro (campos relevantes):")
                    detail = models.execute_kw(db, uid, password, 'account.move', 'read', 
                        [[move['id']]], 
                        {'fields': list(boe_fields.keys()) + ['state', 'move_type']}
                    )
                    for k, v in detail[0].items():
                        if v: print(f"    {k}: {v}")

    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == '__main__':
    investigate_letters_model()

