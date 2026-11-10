# Entrega RRHH

Los libros `.xlsx` de esta carpeta se generan desde Gold y están ignorados por Git porque
contienen datos reales. Nacional e Internacional nunca se mezclan en un archivo ni en una
aprobación:

```powershell
python -m mvp.cli export-xlsx --channel nacional `
  --database var/commission-pilot.sqlite3 `
  --output entrega_rrhh/comisiones_nacional_septiembre_2026.xlsx

python -m mvp.cli export-xlsx --channel internacional `
  --database var/commission-pilot.sqlite3 `
  --output entrega_rrhh/comisiones_internacional_septiembre_2026.xlsx
```

Cada libro contiene `Resumen RRHH` (persona/puesto × Contado/Crédito/Letras/Total),
`Cobrado por linea` (background cobrado y comisión por línea comercial), `Detalle`,
`Excepciones`, `Diferencias` y `Manifest` exclusivamente de su canal. Dirección Comercial
aprueba Nacional; Gerencia Internacional aprueba Internacional. El piloto sigue bloqueado y
no es pagable.
