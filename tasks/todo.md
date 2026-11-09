# Tareas — MVP de comisiones

## commission-engine

- [x] T1: Dinero, periodos y política de comparación
  - Acceptance: `Decimal` desde texto, `ROUND_HALF_UP` a 2 decimales, tolerancia `0.01`; periodos inclusivos por canal.
  - Verify: `python -m pytest mvp/tests/unit/test_money_periods.py -q`
  - Files: `mvp/domain/money.py`, `mvp/domain/periods.py`, `mvp/application/contracts.py`
- [x] T2: Ruleset versionado y precedencia de reglas
  - Acceptance: factura > producto > línea > cliente > país > TODOS; prioridad, vigencia, exclusión gana empate; conflicto bloquea; override Aminoplex.
  - Verify: `python -m pytest mvp/tests/unit/test_rules.py -q`
  - Files: `mvp/domain/rules.py`, `mvp/rulesets/2026-09.v1.json`
- [x] T3: Elegibilidad documento/línea/cobro
  - Acceptance: boletas, TTG dual, MARKETING%/OFICINA, diarios 001/060, reversed, NC, TRP, cuentas y conceptos por línea, ND mixta, bonificación TTG por línea; desconocidos bloquean.
  - Verify: `python -m pytest mvp/tests/unit/test_eligibility.py -q`
  - Files: `mvp/domain/eligibility.py`
- [x] T4: Cálculo Nacional e Internacional
  - Acceptance: base prorrateada con impuesto real; 4 roles opcionales; beneficiario faltante bloquea; TODOS/Luis/Mayumi.
  - Verify: `python -m pytest mvp/tests/unit/test_commissions.py -q`
  - Files: `mvp/domain/commissions.py`
- [x] T5: Letras y anti-duplicado
  - Acceptance: protestada excluida; monto real; clave única impide doble pago; `emitidas = pagadas_hasta_fin + faltantes`.
  - Verify: `python -m pytest mvp/tests/unit/test_letters.py -q`
  - Files: `mvp/domain/letters.py`
- [x] T6: SQLite medallón y servicio idempotente
  - Acceptance: migración desde vacío, carga Bronze idempotente, Gold atómico, rerun mismo checksum, snapshot/ruleset distinto => run_id distinto.
  - Verify: `python -m pytest mvp/tests/integration -q`
  - Files: `mvp/infrastructure/sqlite/*`, `mvp/application/services.py`
- [x] T7: Odoo solo lectura y extractor bulk
  - Acceptance: campos explícitos, paginación por id, lotes sin N+1, métodos de escritura rechazados.
  - Verify: `python -m pytest mvp/tests/integration/test_odoo_readonly.py -q`
  - Files: `mvp/infrastructure/odoo_readonly.py`, `mvp/infrastructure/odoo_extract.py`
- [x] T8: Contratos y CLI
  - Acceptance: JSONL canónico ordenado, decimales como texto, resumen reconcilia con líneas.
  - Verify: `python -m pytest mvp/tests/contracts -q`
  - Files: `mvp/cli.py`, `mvp/application/contracts.py`

## historical-parity

- [x] P1: Importadores de entradas manuales a Bronze + enriquecimiento Odoo
- [x] P2: Importadores de golden masters
- [x] P3: Comparador y clasificador de diferencias
- [x] P4: Corrida real de septiembre y regresiones
- [x] P5: Registro de cierres para cierres adicionales

## interfaz-minima

- [x] U1: Exportación Excel RRHH/Dirección en `entrega_rrhh/`
- [x] U2: App Streamlit
- [x] U3: Smoke test headless

## additional-closures (NO completable en este repositorio)

- [ ] C1: Registrar 1–2 cierres adicionales por canal en `mvp/closures/registry.json` y alcanzar paridad.
  - Bloqueo: no existen más cierres en `Proceso_Manual/`. El mecanismo está listo.

## Verificación de cierre

- [x] Pytest completo, lint, formato y compilación.
- [x] Paridad real Nacional e Internacional persistida en SQLite.
- [x] Excel real generado y validado.
- [x] Streamlit headless respondió HTTP 200 y el listener fue cerrado.
- [x] `git diff --check` y ReadLints.
- [x] Búsqueda de `kluster_dependency_validator` y `kluster_code_review_auto`.
  - Resultado: herramientas no disponibles en esta sesión; documentado en plan y changelog.
