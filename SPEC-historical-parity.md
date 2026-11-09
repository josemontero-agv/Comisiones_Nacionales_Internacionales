# SPEC: Paridad histórica (`historical-parity`)

Estado: aprobado para implementación por autorización expresa del usuario.

## Objetivo

Importar los cierres reales disponibles de septiembre de 2026, ejecutar el motor
determinista con la regla de negocio correcta y comparar sus resultados con los libros
autoritativos. La comparación monetaria se hace después de redondear a dos decimales con
`ROUND_HALF_UP` y tolerancia absoluta `0.01`; claves y pertenencia se comparan exactamente.

La paridad no transforma defectos del Excel en reglas. En particular, el atajo de letras
`subtotal / cantidad de letras` se conserva solo como valor esperado histórico; el motor usa
el monto real de la letra. Toda diferencia se clasifica como `dato_fuente`, `mapeo`,
`elegibilidad`, `base`, `porcentaje`, `beneficiario`, `redondeo` o `excepcion_manual`.
La marca histórica `NO VA` tampoco se usa como texto libre: sus líneas son no comisionables
por cuenta (`7011001` para gastos de exportación o `7599009` para intereses).

## Entradas aprobadas

- Nacional: `Proceso_Manual/nacional/SEP/**`, tabla de porcentajes y
  `COMISIONES 2026 SETIEMBRE (1).xlsx`.
- Internacional: ciclo 20-ago–20-sep de `Proceso_Manual/internacional/SEPTIEMBRE/**` y
  `COMISION EXTERIOR 20 AGOSTO 2026 AL 20 SEPTIEMBRE 2026.xlsx`.
- No existe otro cierre completo; `additional-closures` permanece pendiente.

## Stack y comandos

- Python 3.12+, `openpyxl==3.1.5`, SQLite de biblioteca estándar y contratos del motor.

```powershell
python -m mvp.cli run-parity --channel nacional --database var/commission-pilot.sqlite3
python -m mvp.cli run-parity --channel internacional --database var/commission-pilot.sqlite3
python -m mvp.cli export-xlsx --channel nacional --database var/commission-pilot.sqlite3 `
  --output entrega_rrhh/comisiones_nacional_septiembre_2026.xlsx
python -m mvp.cli export-xlsx --channel internacional --database var/commission-pilot.sqlite3 `
  --output entrega_rrhh/comisiones_internacional_septiembre_2026.xlsx
python -m pytest mvp/tests -q
```

## Estructura

- `mvp/historical/importers.py`: lectura tabular y normalización de Excel.
- `mvp/historical/parity.py`: comparación y clasificación.
- `mvp/historical/runner.py`: corrida real, persistencia Bronze/Gold y manifiesto.
- `mvp/closures/registry.json`: cierres disponibles y pendientes.
- `mvp/tests/`: unitarias, integración y regresiones del cierre.

## Contrato de salida

Cada corrida entrega `manifest`, líneas Gold, resumen por persona/puesto/categoría,
excepciones y diferencias. Registra conteos de pares, faltantes, extras y discrepancias
monetarias, total esperado, total calculado, diferencia y estado:

- `parity`: sin diferencias fuera de tolerancia;
- `explained_differences`: solo diferencias clasificadas;
- `blocked`: falta dato/regla obligatoria o existe diferencia no clasificada.

El resultado solo es pagable con estado `parity`, sin excepciones bloqueantes y con cierres
adicionales completados.

La entrega de RRHH se materializa en dos libros independientes. Nacional va a Dirección
Comercial e Internacional a Gerencia Internacional; ni el detalle ni los totales se
consolidan en un mismo archivo o aprobación.

## Estrategia de pruebas

- Comparador: redondeo, tolerancia, faltantes, extras y clasificación.
- Importadores: encabezados, tipos, filas vacías y decimales desde texto.
- Regresión real: ambos libros abren, generan resultados no vacíos y reconcilian sus
  resúmenes con sus líneas.
- Persistencia: Bronze es inmutable/idempotente y Gold referencia corrida/snapshot.

## Límites

- Siempre: solo lectura de archivos/Odoo; conservar evidencia y hashes; usar `Decimal`.
- Preguntar: nuevos cierres, cambios de tolerancia o de golden master.
- Nunca: escribir en Odoo/Supabase, ocultar diferencias o copiar atajos defectuosos al motor.

## Criterios de éxito

1. Nacional e Internacional se ejecutan realmente sobre septiembre.
2. Los totales y diferencias son reproducibles y quedan en SQLite y JSON.
3. Las diferencias del atajo de letras y de reglas históricas quedan visibles y clasificadas.
4. El registro deja explícito que faltan 1–2 cierres adicionales por canal.
