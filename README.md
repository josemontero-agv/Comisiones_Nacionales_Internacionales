# Comisiones Nacional e Internacional

Piloto local para reproducir, comparar y revisar las comisiones de septiembre de 2026 de
Agrovet Market. El núcleo Python calcula y persiste Bronze/Gold en Supabase. Streamlit
sigue como inspector local. El exportador genera un libro independiente por canal.

> **Este piloto no es pagable.** Faltan 1–2 cierres adicionales por canal y siguen abiertas
> excepciones bloqueantes. Nacional e Internacional siempre se entregan y aprueban
> por separado.

## Cómo ejecutarlo

Desde la raíz del repositorio, con el entorno Python del proyecto ya preparado:

```powershell
python -m streamlit run interfaz_minima/app.py --server.headless true --server.port 8501
```

## API Flask y página Next.js

La API en `api/` solo lee Gold. No calcula porcentajes, no elige roles y no escribe en
Odoo. Septiembre 2026 sigue siendo piloto y no pagable. Nacional e Internacional no se
mezclan.

El `.env` local no se commitea. El ejemplo sin secretos está en `.env.example`. La base
de trabajo es el proyecto Supabase `Comisiones_Nacionales_Internacionales`
(`yodazdangiajmjpzvtio`), región `us-west-2`. `DATABASE_URL` usa el pooler de sesión
`aws-1-us-west-2.pooler.supabase.com`, puerto 5432, usuario
`postgres.yodazdangiajmjpzvtio` y `sslmode=require`. El host directo
`db.<ref>.supabase.co` no resuelve en esta red. La API ya no abre SQLite.

```powershell
.\.venv\Scripts\python.exe -m api
```

La API escucha en `http://127.0.0.1:5000`. `/health` responde `status: ok` y
`payable: false`. Sin `DATABASE_URL`, `database_ready` es false. Con Gold cargado, el
resumen de un canal sale de Supabase y sigue sin ser pagable. Si la contraseña del rol
`postgres` no es la del panel (Database → Reset database password), la conexión responde
`password authentication failed` y no se copia ni se calcula nada.

La página está en `web/` (App Router). Copie `web/.env.example` a `web/.env.local` si
quiere fijar la URL; el valor de ejemplo ya es el de la API local.

```powershell
Set-Location web
npm install
npm run dev
```

`npm run dev` publica `http://127.0.0.1:3000`.

## dbt, solo staging

`dbt/` declara vistas sobre `raw.factura`, `raw.linea_documento`, `raw.pago` y `raw.letra`.
No calcula porcentajes ni roles. La macro `generate_schema_name` deja el esquema en
`staging`. dbt está instalado en `dbt/.venv` para no mover el pin de `python-dotenv` del
entorno de la API. Ese entorno usa Python 3.11: en 3.14 dbt no arranca. `dbt/profiles.yml` está en `.gitignore`.

```powershell
$env:COMMISSION_DB_PASSWORD = "<contraseña del rol postgres, solo en la sesión>"
dbt\.venv\Scripts\dbt.exe run --project-dir dbt --profiles-dir dbt
dbt\.venv\Scripts\dbt.exe test --project-dir dbt --profiles-dir dbt
```

Antes de `dbt run`, el Gold tiene que estar en Supabase y las tablas tipadas llenas:

```powershell
.\.venv\Scripts\python.exe -m mvp.cli copy-sqlite-gold
.\.venv\Scripts\python.exe -m mvp.cli project-typed-raw
```

`copy-sqlite-gold` lee `var/commission-pilot.sqlite3` una sola vez y marca `payable` en
false. No inventa filas si el archivo no está. La CLI de cálculo (`load`, `run-parity`,
`export-xlsx`) escribe en Supabase, no en SQLite. Las pruebas de dominio siguen usando una
base desechable y no tocan el proyecto compartido.

## CLI del motor

La CLI ejecuta el load Odoo completo de septiembre por canal:

```powershell
python -m mvp.cli load --channel nacional
python -m mvp.cli load --channel internacional
```

Cada comando extrae Odoo en solo lectura, persiste Bronze/Silver/Gold en
`var/commission-pilot.sqlite3` y genera el Excel separado en `entrega_rrhh/`. Si ya existe
un snapshot Odoo cerrado del mismo canal y periodo, lo reutiliza; `--refresh` fuerza una
nueva extracción. La paridad histórica permanece disponible solo como validación:

```powershell
python -m mvp.cli run-parity --channel nacional --database var/commission-pilot.sqlite3
python -m mvp.cli run-parity --channel internacional --database var/commission-pilot.sqlite3
```

## Origen real de septiembre

El cálculo real usa exclusivamente conciliaciones, facturas, letras, productos, cuentas,
pedidos, clientes y países extraídos de Odoo con campos explícitos, paginación y relaciones
bulk. Nacional usa `2026-09-01..2026-09-30`; Internacional usa
`2026-08-20..2026-09-20`. La cuenta elegible es `7022101`; las demás cuentas no aprobadas
quedan como excepciones bloqueantes.

Los libros de `Proceso_Manual` no alimentan este cálculo. `run-parity` conserva la
comparación histórica separada y opcional; una falla de Odoo nunca activa un fallback a
Excel.

## Reglas y aclaraciones del piloto

- Ivonne Panta tiene el override estructurado
  `OVR-IVONNE-F522-ATREVIA-2026-09`, propuesto por Sandra y aplicado por José. Exige
  simultáneamente `F F15-00000522` y el producto `31392PER00007`. La factura, fechada
  2026-09-28, queda fuera del ciclo Internacional de este load.
- Mayumi Garcilazo existe con el puesto **Jefe Tecnico Comercial Latinoamerica Avivet** y la
  regla permanente `INTL-MAYUMI-AVIVET-LATAM-V1`: 0,5% solo AVIVET + LATAM. Luis Chávez usa
  el mismo catálogo en `INTL-LUIS-PETMEDICA-AMERICA-V1`, al 0,5% solo PETMEDICA.
- No se agrega una columna de continente ni se clasifica texto por cada línea: el país se
  guarda y compara por ISO. El catálogo único América/LATAM es:
  `MX, GT, BZ, SV, HN, NI, CR, PA, CO, VE, EC, PE, BO, BR, PY, UY, AR, CL, GY, SR, GF`;
  no incluye Caribe, Estados Unidos ni Canadá. El Excel histórico de septiembre no trae ISO,
  por lo que esa corrida diagnóstica no puede recalcular estos alcances por país.
- Cada Excel incluye `RESUMEN COMISIONES`, con jerarquía Puesto → Línea comercial → Nombre,
  y `Cobrado por linea`, sin mezclar canales.
- En la validación Excel Nacional, S/ 74.710,24 menos la suma presentada por línea de
  S/ 74.510,91 da los
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
- API de lectura: `api/`. No calcula.
- Página Next.js: `web/`.
- Staging dbt, sin porcentajes ni roles: `dbt/`.
- Interfaz local: `interfaz_minima/`.
- Libros separados para RRHH: `entrega_rrhh/`.
- Evidencia y archivos del proceso manual: `Proceso_Manual/`.
