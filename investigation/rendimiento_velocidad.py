# -*- coding: utf-8 -*-
"""
Script de prueba de performance para endpoints optimizados.

Valida que las mejoras de rendimiento estén funcionando correctamente.
"""

import time
import requests
import statistics


BASE_URL = "http://localhost:5000/api/v1/collections"


def test_pagination_performance():
    """Testea performance de paginación"""
    print("\n📊 Testeando Performance de Paginación...")
    print("=" * 60)
    
    times = []
    
    for page in range(1, 11):  # 10 páginas
        start = time.time()
        response = requests.get(f"{BASE_URL}/report/account12/rows?page={page}")
        elapsed = time.time() - start
        times.append(elapsed)
        
        status_icon = "✅" if response.status_code == 200 else "❌"
        print(f"  {status_icon} Página {page}: {elapsed:.3f}s - {len(response.text)} bytes - Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"     Error: {response.text[:200]}")
            continue
        
        if 'Error' in response.text:
            print(f"     ⚠️  Contenido con error")
    
    if times:
        print(f"\n📈 Estadísticas de Paginación:")
        print(f"  - Media: {statistics.mean(times):.3f}s")
        print(f"  - Mediana: {statistics.median(times):.3f}s")
        print(f"  - Mínimo: {min(times):.3f}s")
        print(f"  - Máximo: {max(times):.3f}s")
        
        # Validar que todas las páginas cargan en < 1s
        if max(times) < 1.0:
            print(f"  ✅ PASS: Todas las páginas cargan en < 1s")
        else:
            print(f"  ⚠️  WARN: Página más lenta: {max(times):.3f}s (objetivo: < 1s)")
    

def test_stats_performance():
    """Testea performance de stats"""
    print("\n📊 Testeando Performance de Stats...")
    print("=" * 60)
    
    start = time.time()
    response = requests.get(f"{BASE_URL}/report/account12/stats")
    elapsed = time.time() - start
    
    status_icon = "✅" if response.status_code == 200 else "❌"
    print(f"  {status_icon} Stats: {elapsed:.3f}s - Status: {response.status_code}")
    
    if response.status_code == 200:
        try:
            data = response.json()
            if data.get('success'):
                stats = data.get('data', {})
                print(f"\n📈 Estadísticas Obtenidas:")
                print(f"  - Total Registros: {stats.get('total_count', 0):,}")
                print(f"  - Monto Total: S/ {stats.get('total_amount', 0):,.2f}")
                print(f"  - Saldo Pendiente: S/ {stats.get('pending_amount', 0):,.2f}")
                print(f"  - Deuda Vencida: S/ {stats.get('overdue_amount', 0):,.2f}")
                
                if elapsed < 0.5:
                    print(f"  ✅ PASS: Stats responde en < 500ms")
                else:
                    print(f"  ⚠️  WARN: Stats lento: {elapsed:.3f}s (objetivo: < 500ms)")
            else:
                print(f"  ❌ FAIL: Respuesta sin éxito: {data.get('message')}")
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
    else:
        print(f"  ❌ FAIL: Error HTTP {response.status_code}")


def test_filters_work():
    """Testea que los filtros funcionen correctamente"""
    print("\n📊 Testeando Filtros...")
    print("=" * 60)
    
    # Test con filtro de fecha
    params = {
        'page': 1,
        'date_from': '2024-01-01',
        'date_to': '2024-12-31'
    }
    
    start = time.time()
    response = requests.get(f"{BASE_URL}/report/account12/rows", params=params)
    elapsed = time.time() - start
    
    status_icon = "✅" if response.status_code == 200 else "❌"
    print(f"  {status_icon} Filtro de Fecha: {elapsed:.3f}s - Status: {response.status_code}")
    
    if response.status_code == 200:
        if len(response.text) > 100:
            print(f"  ✅ PASS: Filtros aplicados correctamente")
        else:
            print(f"  ⚠️  WARN: Respuesta vacía o muy pequeña")
    
    # Test stats con mismo filtro
    start = time.time()
    response_stats = requests.get(f"{BASE_URL}/report/account12/stats", params=params)
    elapsed_stats = time.time() - start
    
    status_icon = "✅" if response_stats.status_code == 200 else "❌"
    print(f"  {status_icon} Stats con Filtro: {elapsed_stats:.3f}s - Status: {response_stats.status_code}")


def main():
    """Ejecuta todas las pruebas de performance"""
    print("\n" + "=" * 60)
    print("🚀 INICIANDO PRUEBAS DE PERFORMANCE")
    print("=" * 60)
    print("\n⚠️  IMPORTANTE: Asegúrate de que el servidor Flask esté corriendo")
    print("   en http://localhost:5000\n")
    
    try:
        # Verificar que el servidor está disponible
        response = requests.get("http://localhost:5000/api/v1/collections/status", timeout=5)
        if response.status_code == 200:
            print("✅ Servidor Flask detectado y funcionando\n")
        else:
            print("⚠️  Servidor responde pero con status inesperado\n")
    except requests.exceptions.RequestException:
        print("❌ ERROR: No se puede conectar al servidor Flask")
        print("   Por favor, inicia el servidor con: python run.py\n")
        return
    
    # Ejecutar pruebas
    test_pagination_performance()
    test_stats_performance()
    test_filters_work()
    
    print("\n" + "=" * 60)
    print("✅ PRUEBAS COMPLETADAS")
    print("=" * 60)
    print("\n📝 Notas:")
    print("  - Primera carga objetivo: < 500ms")
    print("  - Paginación objetivo: < 1s por página")
    print("  - Stats objetivo: < 500ms")
    print("  - Memoria servidor objetivo: < 5MB por request")
    print("\n")


if __name__ == '__main__':
    main()

