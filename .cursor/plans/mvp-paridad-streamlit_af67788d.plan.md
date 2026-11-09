---
name: mvp-paridad-streamlit
overview: "Construir un piloto local de septiembre con arquitectura medallón, paridad monetaria tolerante contra los Excel existentes y una interfaz Streamlit mínima. El trabajo seguirá las puertas SDD: SPEC de cada módulo, aprobación, plan/tareas e implementación."
todos:
  - id: spec-engine
    content: Redactar y someter a aprobación la SPEC de `commission-engine` con arquitectura medallón SQLite y contratos deterministas.
    status: completed
  - id: engine
    content: Planificar por tareas e implementar el motor en `mvp/` con pruebas unitarias.
    status: completed
  - id: historical-parity
    content: Especificar e implementar la paridad de septiembre contra los golden masters Nacional e Internacional.
    status: completed
  - id: streamlit-ui
    content: Especificar e implementar `interfaz_minima/` y la exportación `.xlsx` en `entrega_rrhh/`.
    status: completed
  - id: additional-closures
    content: Incorporar 1–2 cierres adicionales por canal antes de declarar aptitud productiva.
    status: pending
isProject: false
---

# MVP de paridad e interfaz mínima

## Decisiones cerradas
- El piloto usa los únicos cierres completos disponibles:
  - Nacional: septiembre 2026, con entradas en [`Proceso_Manual/nacional/SEP`](Proceso_Manual/nacional/SEP) y tabla de reglas en [`Proceso_Manual/nacional/Porcentajes/Tabla de Comisiones.xlsx`](Proceso_Manual/nacional/Porcentajes/Tabla%20de%20Comisiones.xlsx).
  - Internacional: ciclo 20-ago–20-sep 2026, con entradas en [`Proceso_Manual/internacional/SEPTIEMBRE`](Proceso_Manual/internacional/SEPTIEMBRE).
- Golden masters:
  - Nacional: [`COMISIONES 2026 SETIEMBRE (1).xlsx`](Proceso_Manual/nacional/calculo_vendedores/COMISIONES%202026%20SETIEMBRE%20(1).xlsx), hoja `RESUMEN COMISIONES` para totales; `CONTADO - CREDITO`, `LETRAS` y `CONSOLIDADO` para trazabilidad.
  - Internacional: [`COMISION EXTERIOR 20 AGOSTO 2026 AL 20 SEPTIEMBRE 2026.xlsx`](Proceso_Manual/internacional/SEPTIEMBRE/COMISION%20EXTERIOR%2020%20AGOSTO%202026%20AL%2020%20SEPTIEMBRE%202026.xlsx), hoja `DETALLE DE COBRANZA` para importes finales y `COMISIONES` para porcentajes/alcances.
- Paridad no será decimal estricta: se compararán importes monetarios redondeados a 2 decimales, aceptando diferencia absoluta de hasta S/ o USD 0,01. Las claves, inclusiones y exclusiones sí deben coincidir exactamente; se conservarán el valor crudo y la diferencia para diagnóstico.
- Septiembre habilita el piloto, pero 1–2 cierres adicionales por canal siguen siendo obligatorios antes de considerar el cálculo apto para producción.
- La salida se generará en `entrega_rrhh/` como `.xlsx`, con el mismo resumen persona/puesto × Contado/Crédito/Letras/Total para RRHH y Dirección Comercial, más hojas de detalle, excepciones y diferencias.

## Arquitectura manejable
- `mvp/`: núcleo Python independiente de Streamlit.
- Medallón local en SQLite para evitar infraestructura prematura:
  - Bronze: extractos Odoo y Excel importados sin alterar, con origen, periodo y fecha de carga.
  - Silver: facturas, líneas, pagos, letras, clientes/países y reglas normalizados.
  - Gold: comisión por línea/persona, seguimiento de letras, resumen RRHH y resultados de paridad.
- `interfaz_minima/`: Streamlit consume solo contratos Gold; permite elegir canal/periodo, ejecutar, revisar excepciones, ver totales/diferencias y descargar Excel.
- La extracción Odoo será solo lectura, paginada, con campos explícitos y sin consultas N+1.

## Flujo SDD y archivos
1. Redactar y aprobar [`SPEC-commission-engine.md`](SPEC-commission-engine.md), incluyendo comandos, estructura, estilo, pruebas, límites y contratos Bronze/Silver/Gold. No implementar antes de esa aprobación.
2. Tras aprobar la SPEC, crear `tasks/plan.md` y `tasks/todo.md`, luego implementar el motor en `mvp/` con pruebas unitarias.
3. Redactar/aprobar `SPEC-historical-parity.md`; implementar importadores y comparadores de septiembre en `mvp/`, convirtiendo cada diferencia corregida en regresión bajo `mvp/tests/`.
4. Redactar/aprobar `SPEC-interfaz-minima.md`; implementar la aplicación en `interfaz_minima/` y la exportación en `entrega_rrhh/`.
5. Registrar en [`docs/CHANGELOG.md`](docs/CHANGELOG.md) cada fase y mantener trazabilidad con el [`PRD`](docs/PRD_COMISIONES_NACIONAL_INTERNACIONAL.html).

## Verificación
- Tests unitarios de reglas, exclusiones, redondeo y seguimiento anti-duplicado de letras.
- Comparación por factura/línea/persona y resumen contra cada golden master.
- Clasificación de diferencias: dato fuente, mapeo, elegibilidad, base, porcentaje, beneficiario, redondeo o excepción manual.
- Paridad visible en Streamlit y Excel descargable; el piloto no se marca como pagable mientras existan diferencias no justificadas.
- Lint, sintaxis, `git diff --check` y revisión automática Kluster si la herramienta está disponible.