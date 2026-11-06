---
name: finanzas-observabilidad
description: Diseña e implementa observabilidad de uso (logins, page views, frecuencia, personas, horarios) y el tablero /observability en Finanzas AGV (Next.js + Flask + Supabase). Use when the user asks for observabilidad, analytics de uso, telemetría de usuarios, métricas de acceso, tablero de uso, o tracking de eventos.
---

# Observabilidad de uso — Finanzas AGV

Skill de proyecto. Guía al agente para instrumentar uso de la app y construir la pestaña Observabilidad **solo para administradores**.

## Separación con Centro de aplicaciones (`/apps`)

| Superficie | Quién | Qué muestra |
|---|---|---|
| `/observability` | **Solo `admin`** (`ADMIN_EMAILS` / override) | Telemetría de uso: personas, horarios de login, frecuencia, top usuarios/módulos |
| `/apps` | `admin` + `app_assistant` | Inventario operativo: KPIs de usuarios/plataformas, salud Odoo/Finanzas, altas de usuarios, CRUD usuarios (sin series de login por hora ni ranking de uso personal) |

**Regla dura:** el asistente de aplicaciones **nunca** recibe telemetría de personas/horarios. No reutilizar `GET /api/v1/analytics/summary` en `/apps`.

Roles JWT únicos (no mezclar): `admin` | `app_assistant` | `user`. Fuente: `app_users` + override `ADMIN_EMAILS` → siempre `admin`.

## Estado actual del repo (no reinventar)

| Existe | Notas |
|---|---|
| Google OAuth → sesión + JWT (`app/auth/oauth.py`) | Gate: dominio + `app_users` activo (fallback `ALLOWED_USERS`) |
| `ADMIN_EMAILS` + roles únicos en JWT/sesión | Override admin; no asignable vía UI |
| `require_login` / `require_role` / `require_admin` / `require_apps_operator` | `RBAC_LOG_ONLY=True` global; helpers hard-deny para rutas sensibles |
| Paleta `#714B67` / `#875A7B` | Compartida con `/apps` |
| `recharts` | Usado en `/observability` y `/apps` |
| `user_activity_logs` + `app/analytics/` + `/observability` | Product analytics v1 |
| `app_users` / `app_platforms` + `app/apps/` + `/apps` | Centro de aplicaciones (operativo) |

**v1 observabilidad = product analytics propio en Supabase.** No integrar SaaS de analytics salvo pedido explícito.

## Objetivo v1 (Observabilidad)

Mostrar a **admins**: uso de la app, frecuencia, personas, horas de entrada.

## Arquitectura

```
google_callback / logout  -->  insert user_activity_logs (Supabase)
AppShell page_view        -->  POST /api/v1/analytics/events  -->  insert
Admin /observability      -->  GET  /api/v1/analytics/summary  -->  agregados
Admin|Assistant /apps     -->  GET  /api/v1/apps/dashboard     -->  inventario (NO telemetría)
```

Persistencia: **Supabase Postgres** (no SQLite local; en Render el disco es efímero).

## Acceso (obligatorio)

- Pestaña y `GET .../analytics/summary`: solo usuarios con rol `admin`.
- `POST .../events`: cualquier usuario autenticado (`require_login`); el backend fija `user_email` desde sesión/JWT.
- Para summary: `@require_login` + `@require_admin` (bloqueo real aunque `RBAC_LOG_ONLY=True`).
- Frontend: `roles` en `/api/v1/auth/user-info`; ocultar link sidebar y redirigir no-admins desde `/observability`.
- `/apps` y APIs `/api/v1/apps/*`: `admin` o `app_assistant` vía `@require_apps_operator`.
- Allowlist proxy: `/observability` y `/apps` en `frontend/proxy.ts`.

## Taxonomía de eventos (v1)

### Obligatorios

| category | event_name | Dónde | payload |
|---|---|---|---|
| `auth` | `user_login_success` | `google_callback` tras sesión OK | `{ username }` |
| `auth` | `user_login_failure` | callback / redirect `not_allowed` o fallo Google | `{ error_code }` |
| `auth` | `user_logout` | `POST /api/v1/auth/logout` **antes** de `session.clear()` | `{}` |
| `nav` | `page_view` | frontend al cambiar ruta autenticada | `{ path, module }` |
| `users` | `user_created` | `POST /api/v1/apps/users` | `{ target_email, role, is_active }` |
| `users` | `user_updated` | `PATCH /api/v1/apps/users/<email>` | `{ target_email, fields, old, new }` |
| `users` | `user_toggled` | `PATCH` solo `is_active` | `{ target_email, is_active }` |

`module` derivado de path: `collections` \| `letters` \| `treasury` \| `dashboard` \| `diagnostics` \| `observability` \| `apps` \| `other`.

### Opcionales (módulos)

| category | event_name | payload típico |
|---|---|---|
| `collections` | `filter_applied` | `{ date_range, currency }` |
| `collections` | `excel_download_click` | `{ row_count }` |
| `letters` | `email_notification_sent` | `{ letter_count }` |
| `treasury` | `treasury_report_view` | `{ filters_present: bool }` |

No usar `odoo_db` en payloads de auth (no está en sesión de usuario).

## DDL Supabase

- Actividad: `scripts/etl/supabase_schema_user_activity.sql`
- Usuarios RBAC: `scripts/etl/supabase_schema_app_users.sql`
- Plataformas: `scripts/etl/supabase_schema_app_platforms.sql`

Escritura vía **service role** desde Flask. No exponer inserts desde el cliente con anon key.

## Backend

1. `app/core/telemetry.py` — `log_event(...)` → insert; fallos solo a logger.
2. Blueprint `analytics_bp` `/api/v1/analytics`:
   - `POST /events` — autenticado; identity del server.
   - `GET /summary` — **solo admin** (`require_admin`). Zona **America/Lima** en logins por hora/día. Incluye `failed_logins`, `logouts`, `recent_events`, `user_admin_actions`.
3. Blueprint `apps_bp` `/api/v1/apps` — inventario/CRUD (no telemetría de personas).
4. Instrumentar login/logout; registrar blueprints en `app/__init__.py`.

## Frontend

1. `frontend/lib/analytics.ts` — `track` / `trackPageView`.
2. `AppShell`: page_view + `isAdmin` / `canManageApps` al sidebar.
3. `/observability`: guard admin; KPIs + Recharts de uso.
4. `/apps`: guard admin|app_assistant; KPIs/inventario/CRUD (sin logins por hora ni top usuarios de uso).
5. Sidebar: Observabilidad solo admin; Aplicaciones admin + asistente.

## Checklist de implementación (orden)

1. DDL actividad + (si aplica) app_users/app_platforms.
2. Helper + POST events + instrumentación login/logout.
3. GET summary (admin) + test manual admin/no-admin.
4. `analytics.ts` + page_view en shell.
5. UI `/observability` + proxy + sidebar + dashboard tile.
6. Centro `/apps` separado (sin filtrar telemetría al asistente).
7. Actualizar `changelog.md` y docs.

## Fuera de alcance v1

- PostHog, Mixpanel, Sentry, OpenTelemetry.
- Que el asistente abra `/observability` o consuma summary de personas/horarios.
- Métricas de latencia API / errores Odoo / logs ETL dedicados (fase 2).

## Anti-patrones

- No usar `logs/email_audit.db` como fuente de uso de app.
- No asumir que `require_role` bloquea mientras `RBAC_LOG_ONLY=True` — usar `require_admin` / `require_apps_operator`.
- No mezclar claims `admin`+`user` en el JWT; rol primario único.
- No crear skill duplicado en `.cursor/extract-requirements-db-design/`; este `SKILL.md` es la fuente de verdad.
