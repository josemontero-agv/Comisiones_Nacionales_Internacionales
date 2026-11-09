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
