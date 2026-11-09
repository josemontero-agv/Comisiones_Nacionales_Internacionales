# SPEC: Interfaz mínima Streamlit (`interfaz-minima`)

Estado: aprobado para implementación por autorización expresa del usuario.

## Objetivo

Entregar una interfaz local para inspeccionar resultados Gold, ejecutar la paridad de los
cierres registrados y descargar un único Excel para RRHH/Dirección. Streamlit no recalcula
comisiones ni lee Bronze/Silver: consume servicios y vistas Gold del núcleo.

## Stack y comandos

- `streamlit==1.67.0`, `openpyxl==3.1.5`, Python 3.12+.

```powershell
python -m streamlit run interfaz_minima/app.py --server.headless true --server.port 8501
python -m mvp.cli export-xlsx --database var/commission-pilot.sqlite3 `
  --output entrega_rrhh/comisiones_septiembre_2026.xlsx
```

## Estructura

- `interfaz_minima/app.py`: selección de canal/cierre, ejecución, KPIs, diferencias,
  excepciones y descarga.
- `mvp/export/rrhh_excel.py`: exportador puro desde contratos Gold.
- `entrega_rrhh/`: ubicación de salida; los `.xlsx` con datos quedan ignorados por Git.

## Contrato visual

- Estado general y advertencia de no pagabilidad.
- Totales esperado/calculado/diferencia por moneda y canal.
- Resumen persona × puesto con Contado, Crédito, Letras y Total.
- Detalle Gold, excepciones y diferencias clasificadas.
- Botón de descarga del mismo archivo generado por CLI.

La aplicación debe mostrar explícitamente que septiembre habilita el piloto, pero no la
producción mientras `additional-closures` siga pendiente.

## Excel de entrega

El libro contiene `Resumen RRHH`, `Detalle`, `Excepciones`, `Diferencias` y `Manifest`.
Importes se escriben como números con formato de dos decimales; identificadores se preservan
como texto. RRHH y Dirección consumen exactamente el mismo resumen.

## Pruebas

- Unitarias del exportador: hojas, encabezados, fórmulas ausentes y conciliación.
- Smoke de Streamlit headless: proceso inicia, `/healthz` responde HTTP 200 y cierra limpio.
- Sintaxis, lint y prueba de exportación real.

## Límites

- Siempre: consumir Gold, impedir etiqueta pagable si hay bloqueos/diferencias/cierres faltantes.
- Preguntar: autenticación, despliegue, cambios de layout oficial.
- Nunca: credenciales en UI, escritura remota, lógica de cálculo o acceso directo a Odoo.

## Criterios de éxito

1. La UI arranca headless y responde por HTTP.
2. Nacional e Internacional se pueden ejecutar/inspeccionar.
3. El Excel real se genera en `entrega_rrhh/` y reconcilia con Gold.
4. Las limitaciones y diferencias permanecen visibles.
