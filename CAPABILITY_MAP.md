# Capability Map: MVP de Comisiones Nacional e Internacional

## Fuente de negocio

`docs/PRD_COMISIONES_NACIONAL_INTERNACIONAL.html` es la fuente de verdad para las reglas
contables, de elegibilidad y de comisiones. Este mapa no las duplica: solo delimita
capacidades, dependencias y entregables futuros.

## Módulos

| Module id | Responsabilidad | Depende de | Entregable / directorio futuro |
|---|---|---|---|
| `commission-engine` | Exponer un cálculo determinista por canal y periodo, con resultados y excepciones trazables, aplicando las reglas vigentes del PRD. | — | Motor y contratos en `mvp/`. |
| `historical-parity` | Importar los Excel históricos como *golden masters*; ejecutar 2–3 cierres reales de Nacional e Internacional; comparar factura por factura; clasificar diferencias; orientar la corrección de reglas del motor; repetir hasta 100% de paridad y conservar cada caso corregido como regresión automática. | `commission-engine` | Importadores, comparadores y regresiones en `mvp/`; pruebas en `mvp/tests/`. |
| `interfaz-minima` | Ofrecer una interfaz Streamlit local para elegir canal y periodo, ejecutar el cálculo, revisar excepciones, mostrar totales y diferencias, y descargar el Excel resultante consumiendo los contratos del MVP. | `historical-parity` | Aplicación Streamlit en `interfaz_minima/`. |

## Orden de construcción y puerta de validación

`commission-engine` → `historical-parity` (paridad histórica 100%) → `interfaz-minima`

`historical-parity` bloquea la habilitación funcional de `interfaz-minima` hasta alcanzar
100% de paridad en los cierres aprobados. Se puede prototipar antes un esqueleto visual de la
UI sobre contratos definidos, pero no podrá presentar, descargar ni marcar resultados como
pagables; ese esqueleto no se considera una entrega habilitada del módulo.

## Supuestos para aprobación

- La implementación futura será en Python.
- Los archivos Excel existentes y aprobados se usarán como *golden masters*.
- Streamlit se ejecutará localmente y sin autenticación en esta fase del MVP.
- El MVP será de solo lectura respecto de Odoo y Supabase; no escribirá datos en ninguno.
- Ningún resultado será pagable hasta lograr 100% de paridad histórica.
- No se agregarán dependencias hasta aprobar este mapa y validar cada incorporación.
- En esta Phase 0 no se crean specs, planes, tareas, código, tests ni directorios de
  implementación.

## Preguntas para aprobar y habilitar la SPEC posterior

1. ¿Cuáles son exactamente los 2–3 cierres reales de cada canal que se usarán para validar
   Nacional e Internacional, y dónde están sus Excel de entrada y resultados finales?
2. Si existen versiones o cifras distintas para un mismo cierre, ¿qué archivo y hoja se
   consideran el *golden master* autoritativo?
3. ¿Cuál es la ubicación y el nombre/formato esperado del Excel de salida para RRHH?
4. Para la paridad 100%, ¿la igualdad monetaria se evalúa después del redondeo aplicado por
   el Excel autoritativo o con igualdad decimal estricta previa al redondeo?
