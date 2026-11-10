# Comisiones Nacional e Internacional

Piloto local para reproducir, comparar y revisar las comisiones de septiembre de 2026 de
Agrovet Market. El núcleo Python calcula y persiste evidencia Bronze/Gold en SQLite, la
interfaz Streamlit permite inspeccionar los resultados y el exportador genera un libro
independiente para cada canal.

> **Este piloto no es pagable.** Faltan 1–2 cierres adicionales por canal y siguen abiertas
> excepciones bloqueantes. Nacional e Internacional siempre se entregan y aprueban
> por separado.

## Cómo ejecutarlo

Desde la raíz del repositorio, con el entorno Python del proyecto ya preparado:

```powershell
python -m streamlit run interfaz_minima/app.py --server.headless true --server.port 8501
```

La CLI implementada en `mvp/cli.py` expone estos comandos de paridad y exportación:

```powershell
python -m mvp.cli run-parity --channel nacional --database var/commission-pilot.sqlite3
python -m mvp.cli run-parity --channel internacional --database var/commission-pilot.sqlite3

python -m mvp.cli export-xlsx --channel nacional `
  --database var/commission-pilot.sqlite3 `
  --output entrega_rrhh/comisiones_nacional_septiembre_2026.xlsx

python -m mvp.cli export-xlsx --channel internacional `
  --database var/commission-pilot.sqlite3 `
  --output entrega_rrhh/comisiones_internacional_septiembre_2026.xlsx
```

## Origen real de septiembre

Las dos entregas actuales se calcularon desde Excel, no desde una extracción Odoo en vivo.
`mvp/historical/runner.py::run_historical_parity` llama a `_national_rows` o
`_international_rows`, que leen con `rows_with_header` estos archivos:

- Nacional:
  `Proceso_Manual/nacional/calculo_vendedores/COMISIONES 2026 SETIEMBRE (1).xlsx`.
- Internacional:
  `Proceso_Manual/internacional/SEPTIEMBRE/COMISION EXTERIOR 20 AGOSTO 2026 AL 20 SEPTIEMBRE 2026.xlsx`.

La evidencia local en `var/commission-pilot.sqlite3`, tabla `bronze_snapshot`, registra esas
mismas rutas como `source_path`; `bronze_record` contiene 6.459 filas Excel de Nacional y
708 de Internacional. Por tanto, Internacional compara contra Excel **y su base también se
lee de ese Excel**: no se extrajo de Odoo para esta entrega. Odoo sigue siendo la fuente
operacional prevista; solo se consultó en lectura para verificar la excepción de Ivonne, sin
incorporar ni inventar un cobro fuera del archivo/ciclo.

## Reglas y aclaraciones del piloto

- Ivonne Panta tiene el override estructurado
  `OVR-IVONNE-F522-ATREVIA-2026-09`, propuesto por Sandra y aplicado por José. Exige
  simultáneamente `F F15-00000522` y el producto `31392PER00007`. La factura, fechada
  2026-09-28, no aparece en el Excel del ciclo 20-ago–20-sep; por eso esta entrega no le
  atribuye un monto por esa excepción.
- Mayumi Garcilazo existe con el puesto **Jefe Tecnico Comercial Latinoamerica Avivet** y la
  regla permanente `INTL-MAYUMI-AVIVET-LATAM-V1`: 0,5% solo AVIVET + LATAM. Luis Chávez usa
  el mismo catálogo en `INTL-LUIS-PETMEDICA-AMERICA-V1`, al 0,5% solo PETMEDICA.
- No se agrega una columna de continente ni se clasifica texto por cada línea: el país se
  guarda y compara por ISO. El catálogo único América/LATAM es:
  `MX, GT, BZ, SV, HN, NI, CR, PA, CO, VE, EC, PE, BO, BR, PY, UY, AR, CL, GY, SR, GF`;
  no incluye Caribe, Estados Unidos ni Canadá. El Excel histórico de septiembre no trae ISO,
  por lo que esa corrida diagnóstica no puede recalcular estos alcances por país.
- Cada Excel incluye `Cobrado por linea`, con línea comercial, cobrado total, comisión total
  y desglose Contado/Crédito/Letras, sin mezclar canales.
- En Nacional, S/ 74.710,24 menos la suma presentada por línea de S/ 74.510,91 da los
  S/ 199,33 visibles en la columna G. Los renglones visibles por persona suman S/ 298,06,
  pero el pivote de referencia omite a Chaman (S/ 98,73) aunque el detalle sí lo calcula. El
  resto se explica por el prorrateo por cobro real frente al atajo histórico y el redondeo
  por línea; el total crudo del motor es S/ 74.510,25. No es una exclusión por `7022101`,
  porque la corrida histórica Excel no recibe cuentas contables y usa `FILTRO`.

## Dónde está cada cosa

- PRD: `docs/PRD_COMISIONES_NACIONAL_INTERNACIONAL.html` y
  `docs/PRD_ARQUITECTURA_DATOS.html`.
- Especificaciones: `SPEC-commission-engine.md`, `SPEC-historical-parity.md`,
  `SPEC-interfaz-minima.md` y `CAPABILITY_MAP.md`.
- Motor, CLI, persistencia y pruebas: `mvp/`.
- Interfaz local: `interfaz_minima/`.
- Libros separados para RRHH: `entrega_rrhh/`.
- Evidencia y archivos del proceso manual: `Proceso_Manual/`.
