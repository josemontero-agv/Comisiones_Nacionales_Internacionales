# Historial de cambios de documentación

## 2026-11-10 — Librerías en requirements.txt

- `requirements.txt` declara las librerías que el proyecto ya usa: Flask, Werkzeug,
  openpyxl, psycopg, python-dotenv, streamlit, pytest, ruff, requests, dbt-core y
  dbt-postgres, con la versión instalada. No se instaló nada nuevo.
- `kluster_dependency_validator` no está en esta sesión.

## 2026-11-10 — Supabase como base de trabajo

- La aplicación deja SQLite. Flask y la CLI usan `DATABASE_URL` del pooler
  `aws-1-us-west-2` del proyecto `yodazdangiajmjpzvtio`. El host directo no resuelve en esta red.
- `copy-sqlite-gold` y `project-typed-raw` preparan Gold y las tablas que lee dbt.
- dbt está en `dbt/.venv`. La página sigue siendo un piloto no pagable.
- `kluster_dependency_validator` y `kluster_code_review_auto` no existen en esta sesión.

## 2026-11-10 — API, página y staging dbt

- README documenta el arranque de Flask con `COMMISSION_DB` y el de Next.js en `web/`.
- `.env.example` y `web/.env.example` quedan con placeholders. El `.env` local no define
  `COMMISSION_DB` ni `DATABASE_URL`; hay que exportar `COMMISSION_DB=supabase` cuando la
  URL del pooler esté en el entorno.
- `dbt/` es solo staging sobre `raw.factura`, `raw.linea_documento`, `raw.pago` y
  `raw.letra`. No calcula porcentajes ni roles. El perfil de ejemplo usa el pooler de
  sesión, puerto 5432 y `sslmode: require`, con la contraseña por variable de entorno.
- La base Supabase `giadbtrcwhlmxkdezbyj` ya tiene RLS forzado y sin políticas. No se
  reaplicó la migración. Gold sigue vacío allí. El piloto de septiembre no es pagable.
- `kluster_dependency_validator` y `kluster_code_review_auto` no existen en esta sesión.

## 2026-11-10 — Load Odoo de septiembre

- README documenta `mvp.cli load` para Nacional e Internacional, los periodos exactos y la
  reutilización del snapshot Bronze.
- El Excel histórico queda como validación opcional separada; nunca reemplaza una extracción
  Odoo fallida.
- La interfaz y ambos libros comparten la pivote Puesto → Línea comercial → Nombre y el
  background cobrado por línea. Septiembre continúa no pagable.

## 2026-11-10 — Producción técnica, octubre y aprobación

- Producción significa construir extracción Odoo, transformación, API Flask, pantalla Next.js
  y PostgreSQL; no enviar a nómina ni declarar un periodo pagable.
- Octubre es el siguiente cierre de prueba y diciembre queda fuera del plan inmediato.
- La diferencia Nacional de S/ 199,33 sigue abierta: prorrateo y atajo histórico permanecen
  visibles, y septiembre continúa no pagable.
- Dirección Comercial valida Nacional y Gerencia Internacional valida Internacional. El
  Supervisor de Proyectos de Finanzas —José Montero durante el piloto— registra la aprobación
  que habilita la entrega a RRHH.

## 2026-11-10 — Catálogo ISO América/LATAM cerrado

- El PRD elimina la pregunta abierta de países: Luis y Mayumi comparten un único catálogo
  versionado de 21 códigos ISO.
- Se documenta que Caribe, Estados Unidos y Canadá quedan fuera y que las líneas comparan ISO,
  no nombres de país.

## 2026-11-10 — SOLID y roles en la arquitectura

- La sección de arquitectura separa cálculo, validación, aprobación registrada y entrega.
- Dirección Comercial y Gerencia Internacional validan su canal; el Supervisor aprueba ambos
  en el sistema y RRHH solo recibe archivos de periodos `Aprobado`.

## 2026-11-09 — Trazabilidad y entrega RRHH ampliada

- Se documentó que los Bronze de septiembre de Nacional e Internacional provienen de los
  Excel de `Proceso_Manual`, no de una extracción Odoo en vivo.
- Se añadieron el override temporal y auditable de Ivonne Panta, y la regla permanente de
  Mayumi Garcilazo (0,5% AVIVET + LATAM, importe cero en septiembre).
- Los libros separados incluyen `Cobrado por linea`, con cobrado y comisión por línea
  comercial y categoría.
- La diferencia Nacional de S/ 199,33 queda registrada como referencia menos suma
  presentada: los deltas visibles suman S/ 298,06 y el pivote omite S/ 98,73 de Chaman;
  no se cierra ni se atribuye definitivamente al prorrateo o al atajo histórico.
- Se creó el `README.md` de raíz con comandos, estructura, límites y estado no pagable.

El historial técnico acumulado anterior permanece en `../CHANGELOG.md`.
