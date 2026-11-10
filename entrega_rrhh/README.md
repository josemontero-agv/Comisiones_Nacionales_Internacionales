# Entrega RRHH

Los libros `.xlsx` de esta carpeta se generan desde Gold Odoo y están ignorados por Git porque
contienen datos reales. Nacional e Internacional nunca se mezclan en un archivo ni en una
aprobación:

```powershell
python -m mvp.cli load --channel nacional
python -m mvp.cli load --channel internacional
```

Cada libro contiene `RESUMEN COMISIONES`
(Puesto → Línea comercial → Nombre × Contado/Crédito/Letras/Total),
`Cobrado por linea` (background cobrado y comisión por línea comercial), `Detalle`,
`Excepciones`, `Diferencias` y `Manifest` exclusivamente de su canal. Dirección Comercial
aprueba Nacional; Gerencia Internacional aprueba Internacional. El piloto sigue bloqueado y
no es pagable.
