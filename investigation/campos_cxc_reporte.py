# -*- coding: utf-8 -*-
import xmlrpc.client
import os
from dotenv import load_dotenv

def test_data():
    # Cargar env
    env_path = '.env.produccion'
    load_dotenv(env_path)
    
    url = os.getenv('ODOO_URL')
    db = os.getenv('ODOO_DB')
    username = os.getenv('ODOO_USER')
    password = os.getenv('ODOO_PASSWORD')
    
    print(f"Conectando a {url}...")
    try:
        common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
        uid = common.authenticate(db, username, password, {})
        models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
        
        if not uid:
            print("[ERROR] Auth fallida")
            return
        
        print("[OK] Conectado")
        
        # 1. Buscar una línea de CxC reciente (cuenta 12)
        line_domain = [('account_id.code', '=like', '12%'), ('parent_state', '=', 'posted'), ('move_id.move_type', '=', 'out_invoice')]
        lines = models.execute_kw(db, uid, password, 'account.move.line', 'search_read', 
            [line_domain], 
            {'fields': ['id', 'move_id', 'partner_id', 'account_id', 'name', 'date', 'date_maturity'], 'limit': 1}
        )
        
        if not lines:
            print("No se encontraron líneas de CxC")
            return
            
        line = lines[0]
        move_id = line['move_id'][0]
        partner_id = line['partner_id'][0]
        account_id = line['account_id'][0]
        
        print(f"\n--- DATOS ENCONTRADOS PARA MOVE {move_id} ---")
        
        # 2. Leer Move
        move_fields = [
            'name', 'invoice_date', 'date', 'invoice_date_due', 
            'l10n_latam_document_type_id', 'l10n_latam_boe_number', 
            'invoice_origin', 'amount_total', 'amount_residual', 
            'invoice_payment_term_id', 'invoice_user_id', 
            'sales_channel_id', 'sale_type_id'
        ]
        move_data = models.execute_kw(db, uid, password, 'account.move', 'read', [[move_id]], {'fields': move_fields})[0]
        
        # 3. Leer Partner
        partner_fields = ['name', 'vat', 'state_id', 'l10n_pe_district', 'country_id']
        partner_data = models.execute_kw(db, uid, password, 'res.partner', 'read', [[partner_id]], {'fields': partner_fields})[0]
        
        # 4. Leer Account
        account_data = models.execute_kw(db, uid, password, 'account.account', 'read', [[account_id]], {'fields': ['code', 'name', 'currency_id']})[0]
        
        # 5. Leer agr.credit.customer
        credit_data = {}
        try:
            credit_records = models.execute_kw(db, uid, password, 'agr.credit.customer', 'search_read', 
                [[('partner_id', '=', partner_id)]], 
                {'fields': ['partner_groups_ids', 'sub_channel_id']}
            )
            if credit_records:
                credit_data = credit_records[0]
        except:
            pass

        print("\nVerificación de campos solicitados:")
        print(f"1. move_id/invoice_date (Fecha Factura): {move_data.get('invoice_date')}")
        print(f"2. account.move/invoice_date (Fecha Contabilización?): {move_data.get('date')} (Note: user said invoice_date, but date is more likely)")
        print(f"3. account.move/invoice_date_due (Fecha Vencimiento): {move_data.get('invoice_date_due')}")
        print(f"4. account.move/l10n_latam_document_type_id (Tipo Doc): {move_data.get('l10n_latam_document_type_id')}")
        print(f"5. account.move/name (Número Doc): {move_data.get('name')}")
        print(f"6. account.move/l10n_latam_boe_number (Letra): {move_data.get('l10n_latam_boe_number')}")
        print(f"7. account.move/invoice_origin (Origen): {move_data.get('invoice_origin')}")
        print(f"8. account_id/code (Cuenta): {account_data.get('code')}")
        print(f"9. account_id/name (Nombre Cuenta): {account_data.get('name')}")
        print(f"10. partner_id/vat (Ruc): {partner_data.get('vat')}")
        print(f"11. partner_id (Cliente): {partner_data.get('name')}")
        print(f"12. account_id/currency_id: {account_data.get('currency_id')}")
        print(f"13. account.move/amount_total: {move_data.get('amount_total')}")
        print(f"14. account.move/amount_residual: {move_data.get('amount_residual')}")
        print(f"15. account.move/invoice_payment_term_id: {move_data.get('invoice_payment_term_id')}")
        print(f"16. account.move.line/name: {line.get('name')}")
        print(f"17. account.move/invoice_user_id (Vendedor): {move_data.get('invoice_user_id')}")
        print(f"18. agr.credit.customer/partner_groups_ids: {credit_data.get('partner_groups_ids')}")
        print(f"19. partner_id/state_id (Provincia): {partner_data.get('state_id')}")
        print(f"20. partner_id/l10n_pe_district (Distrito): {partner_data.get('l10n_pe_district')}")
        print(f"21. partner_id/country_id (Pais): {partner_data.get('country_id')}")
        print(f"22. agr.credit.customer/sub_channel_id: {credit_data.get('sub_channel_id')}")
        print(f"23. account.move/sales_channel_id: {move_data.get('sales_channel_id')}")
        print(f"24. account.move/sale_type_id: {move_data.get('sale_type_id')}")

    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == '__main__':
    test_data()
