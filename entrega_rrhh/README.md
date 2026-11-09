# Entrega RRHH

Los libros `.xlsx` de esta carpeta se generan desde Gold y están ignorados por Git porque
contienen datos reales. Generación:

```powershell
python -m mvp.cli export-xlsx --database var/commission-pilot.sqlite3 `
  --output entrega_rrhh/comisiones_septiembre_2026.xlsx
```
