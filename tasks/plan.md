# Plan de implementación — MVP de comisiones

Fuentes: `CAPABILITY_MAP.md`, `SPEC-commission-engine.md`, `SPEC-historical-parity.md`,
`SPEC-interfaz-minima.md` y `docs/PRD_COMISIONES_NACIONAL_INTERNACIONAL.html`.

Estado recuperado el 2026-11-07: el intento previo solo dejó implementados dinero, periodos,
modelos, resolución parcial de reglas y el cliente Odoo de lectura. Las marcas de tareas
anteriores no reflejaban el workspace y se corrigieron en `tasks/todo.md`. Se conserva ese
trabajo válido y se completa incrementalmente.

## Dependencias

Se buscó `kluster_dependency_validator` antes de modificar dependencias y no está disponible
en esta sesión. No se ejecutará un gestor de paquetes: `.venv` ya contiene las versiones
requeridas. `requirements.txt` se limita a fijar las dependencias mínimas reproducibles.

## 1. Módulo `commission-engine`

### Componentes y dependencias

```text
domain/money, domain/periods                (sin dependencias)
domain/models                               (Silver tipado)
domain/rules  -> models                     (ruleset versionado, precedencia, catálogos)
domain/eligibility -> rules, models         (decisiones documento/línea/cobro)
domain/letters -> models                    (estados, anti-duplicado, seguimiento)
domain/commissions -> eligibility, rules    (base prorrateada y beneficiarios)
application/contracts                       (request/result/policy, JSON canónico)
infrastructure/sqlite (schema, repos)       (Bronze/Silver/Gold, transacciones)
infrastructure/odoo_readonly                (XML-RPC solo lectura, paginado por id)
infrastructure/odoo_extract                 (extracción bulk a Bronze)
infrastructure/sources/manual_reports       (Bronze de reportes -> Silver)
application/services                        (snapshot -> Silver -> Gold, idempotente)
cli                                         (adaptador)
```

### Orden de implementación
1. Dinero, periodos, contratos y política de comparación (unitarias primero).
2. Ruleset versionado (`mvp/rulesets/*.json`) y resolución de reglas con precedencia.
3. Elegibilidad por documento, línea y asignación de cobro.
4. Cálculo Nacional (4 roles por Línea+Zona) e Internacional (beneficiario+alcance).
5. Letras: estados, monto real, anti-duplicado y seguimiento.
6. Esquema SQLite medallón, repositorios y servicio transaccional idempotente.
7. Cliente Odoo de solo lectura y extractor bulk (pruebas con transporte simulado).
8. CLI `extract-odoo`, `calculate`, `export-contract`.

### Decisiones de implementación (desviaciones documentadas respecto de la SPEC)
- Bronze usa una tabla genérica `bronze_record` con `source_model` en lugar de una tabla por
  entidad; conserva las mismas columnas mínimas (`snapshot_id`, `source_model`, clave fuente,
  `write_date`, `loaded_at`, `payload_json`, `payload_sha256`). Simplifica la carga
  idempotente sin perder trazabilidad.
- La base de cada línea es `monto_cobrado × subtotal_línea / total_documento`, que equivale a
  `(monto/1,18) × proporción neta` cuando todo el documento lleva IGV 18% y no aplica 1,18 a
  líneas exoneradas (impuesto real por línea).
- Catálogos aún no aprobados por negocio (cuentas, América/LATAM, familia ATREVIA) se usan
  marcados como `provisional`; cada uso genera una excepción bloqueante a nivel corrida.

### Riesgos
| Riesgo | Mitigación |
|---|---|
| Odoo vivo no reproduce el estado al cierre | Snapshot Bronze inmutable con hash; Excel de entrada como evidencia del cierre |
| Catálogos pendientes de aprobación | Excepción bloqueante; el piloto no es pagable |
| Dependencias en Python 3.14 | Versiones fijadas e instaladas en `.venv` |

## 2. Módulo `historical-parity`
1. Importadores de entradas manuales (SEP/SEPTIEMBRE) a Bronze con origen explícito.
2. Enriquecimiento Odoo de solo lectura por nombre de documento (atributos estables).
3. Importadores de golden masters (Nacional e Internacional).
4. Comparador por factura/línea/persona y totales, con política `0,01`.
5. Clasificador de diferencias y reporte de paridad persistido en Gold.
6. Registro de cierres (`mvp/closures/registry.json`) para incorporar cierres nuevos.

## 3. Módulo `interfaz-minima`
1. Servicio de exportación Excel (`mvp/export/rrhh_excel.py`) sobre contratos Gold.
2. App Streamlit `interfaz_minima/app.py` (solo consume Gold y servicios de `mvp`).
3. Smoke test headless.

## Puntos de verificación
- Tras cada módulo: `python -m pytest mvp/tests -q`, `python -m ruff check mvp interfaz_minima`,
  `python -m compileall -q mvp interfaz_minima`, `git diff --check`.
- E2E: paridad real por canal, exportación XLSX y Streamlit headless con `/healthz` HTTP 200
  y cierre explícito del proceso.
