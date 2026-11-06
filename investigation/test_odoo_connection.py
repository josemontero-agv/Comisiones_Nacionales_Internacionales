import xmlrpc.client
import os  # Importamos la librería del sistema operativo para leer variables de entorno
from dotenv import load_dotenv  # Importamos la función para cargar el archivo .env

# --- 1. CARGAR VARIABLES DE ENTORNO ---
# Esta función busca un archivo .env en la misma carpeta y carga sus variables.
load_dotenv()

# Leemos las credenciales desde las variables de entorno que cargamos.
# os.getenv() obtiene el valor de la variable especificada.
url = os.getenv('ODOO_URL')
db = os.getenv('ODOO_DB')
username = os.getenv('ODOO_USER')
password = os.getenv('ODOO_PASSWORD')

# Verificamos que todas las variables necesarias se hayan cargado correctamente.
if not all([url, db, username, password]):
    print("❌ Error: Asegúrate de que las variables ODOO_URL, ODOO_DB, ODOO_USER y ODOO_PASSWORD estén definidas en tu archivo .env")
    exit()

# --- 2. AUTENTICACIÓN ---
# El resto del código funciona exactamente igual, pero ahora usa las variables cargadas.
common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')

try:
    uid = common.authenticate(db, username, password, {})
    if uid:
        print(f"✅ ¡Conexión exitosa! Tu ID de usuario es: {uid}")
    else:
        print("❌ Error de autenticación. Revisa las credenciales en tu archivo .env.")
        exit()
except Exception as e:
    print(f"❌ No se pudo conectar al servidor en la URL '{url}'. Error: {e}")
    exit()

# --- 3. EJECUTAR UNA ACCIÓN (LEER DATOS) ---
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

print("\nBuscando los primeros 5 productos...")

try:
    product_ids = models.execute_kw(db, uid, password, 'product.product', 'search', [[]], {'limit': 5})

    if not product_ids:
        print("No se encontraron productos.")
    else:
        products = models.execute_kw(db, uid, password, 'product.product', 'read', [product_ids], {'fields': ['id', 'name', 'default_code']})
        
        print("✅ Productos encontrados:")
        for product in products:
            print(f"  - ID: {product.get('id')}, Código: {product.get('default_code', 'N/A')}, Nombre: {product.get('name')}")

except Exception as e:
    print(f"❌ Ocurrió un error al consultar los productos: {e}")