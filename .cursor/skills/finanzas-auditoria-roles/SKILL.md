---
name: finanzas-auditoria-roles
description: Diseña e implementa el módulo de Auditoría (/auditoria) en Finanzas AGV (Next.js + Flask + Supabase) que combina gestión de roles (admin/app_assistant/user sobre app_users) con bitácora de seguridad (trazabilidad de altas/cambios de rol, logins, accesos denegados). Use when the user asks for auditoría, bitácora, trazabilidad, gestión de roles, permisos, RBAC UI, control de accesos administrativo, o quién cambió qué rol.
---

# Auditoría y gestión de roles — Finanzas AGV

Skill de proyecto. Guía al agente para construir `/auditoria`: una pantalla que combina **gestión de roles** (CRUD sobre `app_users.role`) con una **bitácora de seguridad** (quién hizo qué, cuándo, a quién). Acceso: **admin + app_assistant**.

## Separación de superficies admin (no duplicar)

| Superficie | Quién | Qué muestra | Qué NO muestra |
|---|---|---|---|
| `/observability` | Solo `admin` | Telemetría de uso: personas, horarios de login, frecuencia, top usuarios/módulos | Gestión de roles |
| `/apps` | `admin` + `app_assistant` | Inventario operativo: KPIs usuarios/plataformas, salud Odoo/Finanzas, altas de usuarios | Bitácora completa de seguridad, filtros de auditoría |
| **`/auditoria`** (nuevo) | `admin` + `app_assistant` | **Roles & Permisos** (CRUD rol de `app_users`) + **Bitácora** (filtro por actor/acción/fecha/entidad) | Telemetría de personas/horarios (eso es de `/observability`) |

**Regla dura:** `/auditoria` reutiliza las mismas reglas de rol que `/apps` (no las reimplementa). No crear una segunda fuente de verdad para "quién puede asignar qué rol".

## Reglas duras de roles (no negociables)

1. Roles válidos: `admin` \| `app_assistant` \| `user` (enum único en `app_users.role`, claim único en JWT/sesión).
2. **`admin` nunca se asigna vía UI** (ni desde `/apps` ni desde `/auditoria`). Solo vía `ADMIN_EMAILS` (override de entorno). Si el usuario pide habilitar esto, confirmar explícitamente antes de implementarlo (rompe un invariante de seguridad documentado).
3. Emails en `ADMIN_EMAILS` son protegidos: ninguna UI puede modificar su rol o desactivarlos.
4. `app_assistant` **sin** `admin` (`_is_assistant_only()`) solo puede crear/editar usuarios con `role=user`; no puede tocar otros `app_assistant` ni asignarlo.
5. Todo cambio de rol debe quedar en la bitácora (no hay cambios "silenciosos").

## Estado actual del repo a reutilizar (no reinventar)

| Pieza | Ubicación | Qué hace |
|---|---|---|
| `require_apps_operator` | `app/auth/security.py` | Bloqueo real (403) admin+app_assistant. Reusar tal cual para `/api/v1/audit/*`. |
| `get_authenticated_user_roles()` | `app/auth/security.py` | Roles en vivo (no JWT stale). |
| `_validate_user_mutation()`, `_is_admin()`, `_is_assistant_only()` | `app/apps/routes.py` | Lógica de reglas 2-4. **Extraer a helper compartido** (p. ej. `app/core/rbac_rules.py`) antes de reusarla desde `audit_bp`, en vez de copiar/pegar. |
| `apps_svc.create_user/update_user/fetch_app_user/list_users` | `app/apps/services.py` | CRUD real sobre `app_users`. Reusar desde el nuevo blueprint; no reescribir queries. |
| `log_event(...)` | `app/core/telemetry.py` | Insert en `user_activity_logs`. Ya se llama en `user_created`/`user_updated`/`user_toggled`. |
| `user_activity_logs` | `scripts/etl/supabase_schema_user_activity.sql` | Tabla fuente de la bitácora. Ya tiene `auth.*` y `users.*` events — no crear tabla nueva. |
| `GET /api/v1/analytics/summary` → `user_admin_actions`, `recent_events` | `app/analytics/routes.py` | Ya arma listas de eventos admin, pero **solo accesible por `admin`** (`require_admin`). `/auditoria` necesita su propio endpoint para `admin`+`app_assistant`, no reusar este (fuga de telemetría de personas al asistente). |

## Objetivo v1

Dar a `admin` y `app_assistant` una pantalla única para: (a) ver y cambiar roles permitidos, (b) ver quién hizo qué cambio de rol/acceso y cuándo, con filtros.

## Arquitectura

```
Frontend /auditoria
   ├─ Tab "Roles"     --> GET/PATCH /api/v1/audit/users        (delega en apps_svc, mismas reglas que /apps)
   └─ Tab "Bitácora"  --> GET /api/v1/audit/events?actor=&category=&from=&to=  (lee user_activity_logs, filtrado)
```

Persistencia: Supabase Postgres (misma tabla `user_activity_logs` + `app_users`; no SQLite, no tabla nueva salvo que se pida explícitamente).

## Acceso (obligatorio)

- Blueprint `audit_bp` en `/api/v1/audit`: **todas** las rutas con `@require_login` + `@require_apps_operator` (igual criterio que `/apps`).
- Mutaciones de rol: pasar siempre por la validación compartida (regla "Reglas duras de roles"); nunca un PATCH directo a Supabase que la salte.
- Página `/auditoria`: guard `admin`+`app_assistant` en frontend (igual patrón que `/apps`), + allowlist en `frontend/proxy.ts`.
- Sidebar: mostrar "Auditoría" junto a "Aplicaciones" cuando `canManageApps` (no crear un tercer flag de permiso salvo que el usuario lo pida).

## Taxonomía de eventos

Reusar `category='users'` existente (`user_created`, `user_updated`, `user_toggled`) para la bitácora de roles. Agregar solo lo que falta para que la auditoría sea completa:

| category | event_name | Dónde | payload |
|---|---|---|---|
| `security` | `role_assignment_denied` | En `_validate_user_mutation` / checks de `admin`-vía-UI, cuando se bloquea un intento | `{ actor_email, target_email, attempted_role, reason }` |
| `security` | `access_denied` | En `require_apps_operator`/`require_admin` cuando el hard-deny dispara (403 real) | `{ path, required_roles, actual_roles }` |

Estos dos eventos son los que hacen que `/auditoria` sea un módulo de **seguridad**, no solo un CRUD: permiten responder "¿alguien intentó escalar privilegios?".

## Backend

1. Extraer `_validate_user_mutation`, `_is_admin`, `_is_assistant_only` de `app/apps/routes.py` a un módulo compartido (p. ej. `app/core/rbac_rules.py`) si `/auditoria` las necesita; actualizar `app/apps/routes.py` para importarlas desde ahí (sin duplicar lógica).
2. Blueprint `audit_bp` en `app/audit/` (`__init__.py`, `routes.py`):
   - `GET /users` — lista `app_users` (reusa `apps_svc.list_users`).
   - `PATCH /users/<email>` — cambia rol; reusa reglas compartidas + `apps_svc.update_user`; loguea `user_updated` (ya existe) y `role_assignment_denied` cuando la regla bloquea.
   - `GET /events` — lee `user_activity_logs` con filtros `actor_email`, `category`, `event_name`, `from`, `to`, paginación; serializa igual que `_serialize_event` en `app/analytics/routes.py` (reusar esa función si es practico moverla a `app/core/telemetry.py`).
3. Registrar `audit_bp` en `app/__init__.py` junto a `apps_bp`/`analytics_bp`.
4. Instrumentar `role_assignment_denied` y `access_denied` donde ya existen los checks (no agregar checks nuevos solo para loguear).

## Frontend

1. `frontend/app/auditoria/page.tsx`: guard `admin`+`app_assistant` (mismo patrón que `/apps`); dos tabs: "Roles" y "Bitácora".
2. Tab Roles: tabla de `app_users` con selector de rol limitado a `user`/`app_assistant` (sin opción `admin` en el UI, nunca).
3. Tab Bitácora: tabla paginada de eventos con filtros (actor, categoría, rango de fechas); destacar en rojo `role_assignment_denied`/`access_denied`.
4. Sidebar (`frontend/components/sidebar.tsx`): nuevo `SidebarLink` a `/auditoria` bajo `canManageApps` (junto al de "Aplicaciones").
5. `frontend/proxy.ts`: agregar `/auditoria` al allowlist.

## Checklist de implementación (orden)

1. Extraer reglas de rol compartidas (`app/core/rbac_rules.py`) desde `app/apps/routes.py`; actualizar imports.
2. Instrumentar `role_assignment_denied` y `access_denied` (reusan `log_event`, sin tabla nueva).
3. Blueprint `audit_bp`: `GET/PATCH /users`, `GET /events`; registrar en `app/__init__.py`.
4. Frontend `/auditoria` con tabs Roles/Bitácora + guard de roles.
5. Sidebar + `frontend/proxy.ts` + tile en dashboard si aplica.
6. Probar: admin ve todo; `app_assistant` solo puede tocar `role=user`; intento de asignar `admin` vía UI queda bloqueado y logueado.
7. Actualizar `changelog.md` y docs.

## Fuera de alcance v1

- Tabla de permisos granulares por módulo (hoy el rol es único por usuario; no crear sistema de permisos ARBAC/ABAC salvo pedido explícito).
- Permitir asignar `admin` vía UI (requiere decisión explícita del usuario antes de tocar esta regla).
- Reusar `GET /api/v1/analytics/summary` para la bitácora (filtraría telemetría de personas al `app_assistant`).

## Anti-patrones

- No dupliques `_validate_user_mutation` ni las queries de `apps_svc` dentro de `app/audit/`; impórtalas.
- No crear una tabla nueva para la bitácora: `user_activity_logs` ya es la fuente de verdad.
- No usar `require_role`/`RBAC_LOG_ONLY` para proteger `/auditoria`; usar `require_apps_operator` (bloqueo real).
- No mezclar el flag de acceso a `/auditoria` con uno nuevo si `canManageApps` (admin+app_assistant) ya cubre el caso.
