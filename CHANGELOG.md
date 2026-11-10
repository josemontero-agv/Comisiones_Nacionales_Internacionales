# Historial de cambios — Comisiones Nacional e Internacional

> Documentación viva: cada cambio relevante de código o documentación en este proyecto debe
> dejar una entrada aquí, describiendo el impacto para cualquier persona del equipo.

## [2026-11-10] — requirements.txt con las librerías usadas

### Cambiado
- `requirements.txt` fija también `dbt-core==1.10.15`, `dbt-postgres==1.10.0`,
  `requests==2.34.2` y `Werkzeug==3.1.9`, además de Flask, openpyxl, psycopg, pytest,
  python-dotenv, ruff y streamlit. Las versiones son las ya instaladas en `.venv` y en
  `dbt/.venv`. No se ejecutó `pip install`.

### Impacto
- Quien recree el entorno ve el motor, la API, Streamlit, las pruebas, el script de
  investigación que usa `requests` y el staging de dbt. dbt sigue pudiendo vivir en
  `dbt/.venv`; el archivo solo declara los pines. Septiembre sigue no pagable.
- `kluster_dependency_validator` no está en esta sesión.

## [2026-11-10] — La base de trabajo pasa a Supabase

### Cambiado
- La API, la CLI (`load`, `run-parity`, `export-xlsx`) y el exportador leen y escriben
  Gold en Supabase (`yodazdangiajmjpzvtio`, región `us-west-2`). SQLite deja de ser el almacén de la aplicación.
- `copy-sqlite-gold` copia una vez el medallón local y fuerza `payable: false`.
- `project-typed-raw` llena `raw.factura`, `raw.linea_documento`, `raw.pago` y `raw.letra`
  desde lo ya guardado. dbt no calcula porcentajes ni roles.
- dbt 1.10 queda en `dbt/.venv`. El perfil local apunta al pooler `aws-1-us-west-2`.
- La página usa la paleta de `docs/PALETA_COLORES.md`, con estado de error, carga vacía
  y cifras tabulares.

### Impacto
- Septiembre sigue no pagable. La copia y `dbt test` necesitan que la contraseña de
  `DATABASE_URL` sea la del rol `postgres` del proyecto. El host directo no resuelve aquí;
  el pooler de este proyecto es `aws-1-us-west-2.pooler.supabase.com`.
- `kluster_dependency_validator` y `kluster_code_review_auto` no están en esta sesión.

## [2026-11-10] — API de lectura, página Next.js y staging dbt

### Añadido
- Página Next.js en `web/` (selector Nacional/Internacional, aviso de no pagabilidad,
  totales esperado/calculado/diferencia, persona × puesto, detalle, excepciones y
  diferencias). Como máximo muestra 80 filas por tabla; el Excel trae el libro completo.
  Paleta de `docs/PALETA_COLORES.md` en `web/app/globals.css`.
- Proyecto `dbt/` con vistas de staging sobre `raw.factura`, `raw.linea_documento`,
  `raw.pago` y `raw.letra`, tests `not_null`/`unique`, test singular de beneficiario si la
  comisión es distinta de cero, y macro `generate_schema_name` para el esquema `staging`.
- `.env.example` y `web/.env.example` con placeholders, sin secretos.
- Prueba `api/tests/test_health.py`: `/health` con un sqlite inexistente devuelve
  `payable: false` y `database_ready: false`.

### Cambiado
- README con los comandos PowerShell de Flask (`COMMISSION_DB`) y de Next.js
  (`npm install`, `npm run dev` en `web/`).
- Se instalaron Flask y psycopg en `.venv` porque faltaban. El pin de `python-dotenv`
  quedó en 1.0.0.

### Verificación
- `python -m pytest mvp/tests api/tests -q`: 21 pruebas aprobadas.
- `/health` con el `.env` actual (sin `COMMISSION_DB` ni `DATABASE_URL`): `status` ok,
  `payable` false, backend sqlite, `database_ready` true porque el SQLite del piloto existe.
- `PostgresMedallionRepository.ping()` no se llamó: no hay `DATABASE_URL` en el entorno.
- Next.js 15 compiló con `npx next build` y `npm run dev` sirvió la página en el puerto 3000.
- dbt quedó escrito y no instalado. Un dry-run de pip resuelve el paquete en Python 3.14,
  pero instalarlo subiría `python-dotenv` sobre el pin de `requirements.txt`. No se ejecutó
  `dbt run` ni `dbt compile`.
- `kluster_dependency_validator` y `kluster_code_review_auto` no existen en esta sesión; no
  se invocaron.
- No se reaplicó la migración de Supabase ni se tocó el proyecto de Finanzas.

### Impacto
- Septiembre sigue siendo piloto y no pagable. Flask no calcula. dbt no calcula porcentajes
  ni roles. La base `giadbtrcwhlmxkdezbyj` sigue con RLS forzado, sin políticas, y con Gold
  vacío: para ver números desde Supabase falta cargar Gold y definir `COMMISSION_DB=supabase`
  junto con `DATABASE_URL` del pooler. Mientras el interruptor no esté, la API lee el Gold
  local del SQLite del piloto.

## [2026-11-10] — Load Odoo real de septiembre

### Añadido
- `python -m mvp.cli load --channel <canal>` extrae Odoo en solo lectura, persiste
  Bronze/Silver/Gold en SQLite y exporta un libro independiente por canal.
- La extracción usa `account.partial.reconcile.max_date`, campos explícitos, paginación y
  resolución bulk de facturas, letras, planillas, productos, cuentas, pedidos y países.
- Streamlit consume el mismo Gold y muestra la pivote Puesto → Línea comercial → Nombre,
  además del cobrado por línea. “Validar contra Excel” queda como acción opcional separada.
- El snapshot cerrado se reutiliza para evitar repetir una extracción larga; `--refresh`
  permite renovarlo de forma explícita.

### Cambiado
- La matriz Nacional y las reglas Internacional quedan versionadas en el ruleset; el cálculo
  ya no lee el Excel histórico ni copia su atajo porcentaje × subtotal.
- Los Excel usan la hoja `RESUMEN COMISIONES` con CONTADO, CREDITO, LETRAS y Total. Si el
  destino está bloqueado por Windows, se escribe una copia en `var/`.

### Impacto
- Septiembre sigue bloqueado y no pagable: las cuentas distintas de las aprobadas se
  registran como excepciones, sin fallback silencioso a Excel.

## [2026-11-10] — Alcance de producción, octubre y aprobador del sistema

### Cambiado
- “Producción” queda definida como la construcción del stack técnico: extracción Odoo,
  transformación, API Flask, pantalla Next.js y PostgreSQL. No implica envío a nómina ni
  vuelve pagable un periodo.
- Octubre 2026 es el siguiente cierre de prueba después de septiembre; diciembre queda fuera
  del plan inmediato.
- La diferencia Nacional de S/ 199,33 sigue abierta. El prorrateo del PRD y el atajo histórico
  del Excel permanecen visibles para comparación; septiembre continúa no pagable.
- Dirección Comercial supervisa y valida Nacional, y Gerencia Internacional hace lo mismo
  con Internacional. El Supervisor de Proyectos de Finanzas ejecuta y registra la aprobación
  que habilita la entrega a RRHH; durante el piloto, José Montero ocupa ese rol.

### Impacto
- Se actualizó el PRD, incluidos workflow, RBAC, requisitos, modelo de aprobación, roadmap,
  riesgos y decisiones cerradas. El código actual aún no implementa roles ni estados de
  workflow, por lo que no requirió cambios.

## [2026-11-10] — Catálogo ISO único América/LATAM

### Cambiado
- Luis Chávez y Mayumi Garcilazo comparten el catálogo versionado
  `MX, GT, BZ, SV, HN, NI, CR, PA, CO, VE, EC, PE, BO, BR, PY, UY, AR, CL, GY, SR, GF`.
- Las reglas comparan el ISO persistido; Caribe, Estados Unidos y Canadá quedan fuera.
- El PRD cierra la pregunta de países y las pruebas cubren inclusión y exclusión.

### Impacto
- El catálogo ya no bloquea por estar vacío. El Excel histórico sí continúa bloqueado para
  estos alcances porque no contiene el ISO del cliente.

## [2026-11-10] — Análisis SOLID para construir el flujo por roles

### Contexto
La construcción de producción debe extraer desde Odoo y entregar a RRHH solo después de la aprobación de cada canal.

### Añadido
- En la arquitectura del PRD, una tabla SOLID aplicada a este sistema: cálculo, aprobación y exportación separados.
- Cada rol funcional queda atado a un puerto propio: Dirección Comercial valida Nacional,
  Gerencia Internacional valida Internacional y el Supervisor de Proyectos de Finanzas
  registra la aprobación en ambos canales.
- Queda escrito que el exportador del piloto todavía no exige el estado `Aprobado`; ese es el
  control que falta para habilitar una entrega a RRHH, no para construir el stack técnico.

### Impacto
- Solo documentación de construcción. No cambia el cálculo ni los Excel de septiembre.

## [2026-11-09] — Background cobrado, overrides y reconciliación Nacional

### Cambiado
- Se creó el README de equipo con comandos reales, estructura y evidencia de que ambos
  cierres Bronze de septiembre se cargan desde Excel, no desde Odoo en vivo.
- Se modeló el override temporal de Ivonne (Sandra/José, factura y producto exactos) y la
  regla permanente de Mayumi al 0,5% sobre AVIVET + LATAM; septiembre muestra Mayumi en cero.
- Gold conserva líneas de cobro sin duplicarlas por beneficiario y ambos libros añaden
  `Cobrado por linea` con cobrado/comisión por línea comercial y categoría.
- El reporte Nacional muestra S/ 74.710,24 contra S/ 74.510,91 presentados: los deltas
  visibles por persona suman S/ 298,06, menos S/ 98,73 de Chaman que el pivote omite aunque
  el detalle calcula. La diferencia de S/ 199,33 queda abierta para iteración; no se declara
  resuelta por prorrateo/redondeo ni por el atajo histórico.

### Impacto
- Las entregas siguen separadas, bloqueadas y no pagables. La consulta puntual de la factura
  de Ivonne fue de solo lectura y no cambió el origen Excel del cierre.

## [2026-11-09] — Reglas cerradas y entregas separadas por canal

### Cambiado
- El ruleset versiona `7022101` como única cuenta elegible confirmada y excluye `7011001`,
  `7599001`, `7599006`, `7599007` y `7599009`. Digital sigue fuera del cálculo automático.
- `NO VA` deja de ser texto libre: las líneas históricas no comisionan por gasto de
  exportación (`7011001`) o interés (`7599009`).
- Los nombres de país se resuelven una vez contra `res.country` por nombre y luego código
  exactos; se persisten `country_id`/ISO. América y LATAM quedan vacíos hasta recibir nombres.
- Sandra propone cambios y valida Internacional; Dirección Comercial valida Nacional.
  Durante el piloto José Montero aplica los cambios y, como Supervisor de Proyectos de
  Finanzas, registra la aprobación sin permitir edición de periodos cerrados.
- `REGV` permanece incluido como regularización de ventas hasta decisión contraria de
  Contabilidad.
- Streamlit, CLI y exportador generan/descargan un solo canal por vez. RRHH recibe
  `comisiones_nacional_septiembre_2026.xlsx` y
  `comisiones_internacional_septiembre_2026.xlsx`, cada uno con resumen, detalle,
  excepciones, diferencias y manifest propios.

### Verificación
- Se actualizó la suite para comprobar cuentas, exclusión de Digital, resolución de país y
  ausencia de mezcla entre libros.
- `python -m pytest mvp/tests -q`: 16 pruebas aprobadas. Ruff, compilación, JSON,
  `git diff --check` y diagnósticos del editor sin errores.
- `kluster_code_review_auto` no está disponible en las herramientas de esta sesión.

## [2026-11-07] — MVP local, paridad real y Streamlit

### Añadido
- SPECs aprobadas de paridad e interfaz, plan/tareas recuperados y registro de cierres.
- Núcleo Python con dinero `Decimal`, periodos, elegibilidad, reglas, comisiones, letras,
  contratos canónicos, cliente Odoo estrictamente de lectura y extractor paginado.
- Arquitectura medallón SQLite (`bronze_*`, `silver_*`, `gold_*`) con cargas idempotentes,
  resultados trazables y hashes.
- Importadores/comparador de los cierres reales de septiembre, clasificación de diferencias
  y pruebas de regresión contra ambos golden masters.
- Interfaz Streamlit que consume Gold y exportador único para RRHH/Dirección con hojas de
  resumen, detalle, excepciones, diferencias y manifest.

### Verificado
- Nacional: golden `S/ 74.710,24`; rama prorrateada del motor `S/ 74.510,25`; 828 diferencias de base,
  principalmente por usar monto real de letra en lugar del atajo por cantidad del Excel.
- Internacional: golden `USD 12.339,38`; motor `USD 12.605,76`; 704 diferencias de
  elegibilidad por aplicar la regla actual de beneficiarios sobre TODOS en vez de las marcas
  históricas parciales.
- El resultado permanece bloqueado/no pagable por beneficiario faltante, falta de catálogos
  ISO América/LATAM, dependencia histórica de `FILTRO` y una inconsistencia entre detalle y
  resumen del golden Nacional.
- Suite, lint/formato, compilación, paridad por CLI, XLSX y Streamlit headless HTTP 200.

### Dependencias y límites
- `requirements.txt` fija solo `openpyxl`, `pytest`, `python-dotenv`, `ruff` y `streamlit`;
  `.venv` ya las contenía y no se ejecutó instalación.
- Se buscó `kluster_dependency_validator` antes del cambio y
  `kluster_code_review_auto` al cierre; ninguna herramienta estuvo disponible.
- `additional-closures` queda preparado pero pendiente: solo existe septiembre.

## [2026-11-06] — SPEC del motor determinista para aprobación

### Añadido
- `SPEC-commission-engine.md`: Phase 1 Specify del módulo `commission-engine`, con contratos
  deterministas, arquitectura medallón local Bronze/Silver/Gold en SQLite, extracción Odoo
  de solo lectura y separación estricta respecto de Streamlit.
- Se definieron contratos canónicos para que `historical-parity` consuma claves, importes
  crudos/presentados y tolerancia monetaria de `0,01`, sin implementar importación de Excel
  ni comparación de *golden masters* dentro del motor.
- Se documentaron stack del piloto, comandos futuros completos, estructura, estilo, pruebas,
  límites, criterios verificables, supuestos y las preguntas abiertas heredadas del PRD.

### Impacto
- Solo documentación de Phase 1. No se crearon `mvp/`, planes, tareas, código, tests ni
  dependencias. La SPEC queda detenida en la puerta de aprobación humana.

## [2026-11-06] — Mapa de capacidades previo a especificaciones

### Añadido
- `CAPABILITY_MAP.md`: delimita `commission-engine`, `historical-parity` e
  `interfaz-minima`, con el motor y la paridad en `mvp/` y la aplicación Streamlit en
  `interfaz_minima/`, según las carpetas aprobadas.
- Se fijaron IDs estables, dependencias unidireccionales, orden de construcción, supuestos y
  decisiones pendientes de aprobación, incluida la puerta obligatoria de paridad histórica
  al 100%.

### Impacto
- Solo documentación de Phase 0. No se crearon specs, planes, tareas, código, tests,
  dependencias ni directorios de implementación.

## [2026-11-06] — Exclusiones contables, reglas Internacional y seguimiento de letras

### Verificado en Odoo (solo lectura)
- Nuevo script reproducible y paginado `investigation/investigacion_reglas_adicionales_odoo.py`.
  Confirmó los campos técnicos de factura/línea/cuenta/producto/partner/país; la factura de
  interés moratorio `F F15-00000495` en `7599009`; cuentas reales de recupero de exportación,
  flete y seguro; y la composición por línea de una muestra de 80 Notas de Débito.
- Las 372 facturas Internacional posted de 2026 analizadas resolvieron país mediante
  `commercial_partner_id.country_id`, sin faltantes. Se documentó la estrategia bulk y el
  fallback controlado.
- El SKU `31018PER00002 AMINOPLEX FORTE (X 100 ML, STD)` está facturado y Odoo lo clasifica
  hoy como AGROVET, en conflicto con la decisión de negocio PETMEDICA; se modeló un override
  versionado y auditable, no una corrección silenciosa.

### Cambiado en el PRD
- Exclusión por línea de intereses, flete, seguro, gastos de exportación,
  administrativos/financieros y reajustes; Notas de Débito solo por venta real de producto,
  validando cuenta contable y artículo/concepto.
- Internacional queda definido por experiencia y alcance: Ariana, Vanessa, Sandra, Umberto e
  Ivonne sobre TODOS; Luis sobre América + PETMEDICA; Mayumi al 0,5% sobre AVIVET + LATAM.
- Reglas permanentes y overrides de periodo con vigencia, prioridad, evidencia, aprobación,
  precedencia determinista, audit log e inmutabilidad de periodos cerrados.
- RRHH y Dirección Comercial usan el mismo resumen persona/puesto con Contado, Crédito,
  Letras y Total, pero con permisos y trazabilidad distintos.
- Letras incorporan mart de seguimiento por factura/planilla: emitidas, pagadas históricas,
  pagadas en periodo, faltantes, monto/estado y control anti-duplicado.
- La base usa impuestos reales: `1,18` solo cuando existe IGV 18%, nunca para exportación
  exonerada. CI pasa a ser agnóstico; GitHub Actions es opcional.
- El brochure Data Engineer respalda Python/SQL/ETL/DataOps/DAG, pero no acredita Dagster/dbt;
  se añadió spike/capacitación y alternativa pragmática sin cambiar la arquitectura por
  marketing.

### Impacto
- Solo documentación y scripts de investigación de lectura. No se modificaron credenciales ni
  datos remotos.

## [2026-11-03] — Flujo AS-IS de setiembre escrito; arquitectura confirmada

### Contexto
Se leyó `COMISIONES 2026 SETIEMBRE (1).xlsx` (hojas, fórmulas, tabla dinámica y valores
guardados) y se cruzó con los reportes de `Proceso_Manual/nacional/SEP` y con la tabla de
porcentajes. El PRD describía quién hace cada paso, no el recorrido de los archivos ni la
fórmula que realmente produce el monto a pagar.

### Añadido en el PRD
- AS-IS Nacional: recorrido SEP → tabla de porcentajes → libro de setiembre, hoja por hoja,
  con las dos fórmulas reales (`% × subtotal` en facturas, `% × subtotal / Cant LT` en
  letras), la columna `FILTRO` y el total de la tabla dinámica (S/ 74.710,24).
- Nota en la evidencia de agosto: el ejemplo pagado al 100% coincide con el prorrateo y
  también con el atajo del libro. Ambos quedan visibles para comparación; no se elige una
  fórmula definitiva hasta iterar la diferencia con octubre.
- Arquitectura: el stack no cambia. Se deja escrito qué decisión cubre cada hallazgo del
  libro, y se explicita el test de beneficiario obligatorio (el 2% de gerente de PET
  NUTRISCIENCE quedó a nombre `0`).

### Impacto
- Solo documentación. No cambia código, modelo de datos ni la elección de Dagster, dbt y Flask.
- Quien implemente el motor debe conservar la base prorrateada y el atajo histórico como
  resultados comparables hasta que negocio cierre la diferencia.

## [2026-10-27] — Reglas de transformación ampliadas: boletas, TTG dual-campo, MARKETING en ambos canales, y 2 correcciones a ejemplos previos del PRD

### Contexto
El solicitante revisó la versión anterior del PRD y señaló correcciones puntuales y reglas
nuevas que debían aplicarse en la **etapa de transformación** (no solo en la extracción, que
ya tenía las condiciones de filtrado de Odoo). Todas se verificaron de solo lectura antes de
documentarlas.

### Corregido (hallazgos de la propia auditoría)
- **`F F01-00007416` y `F F01-00007452` eran ejemplos incorrectos.** La versión anterior del
  PRD las usaba como casos válidos de "pago adelantado" comisionable. Al agregar verificación
  explícita de `move_type` en `seccion_5_evidencia_conciliacion` (en vez de inferir por nombre
  de diario), se descubrió que **ambas están 100% pagadas con Nota de Crédito**
  (`move_type='out_refund'`: 7/7 y 3/3 conciliaciones respectivamente) — ninguna de las dos es
  comisionable. Solo `F F01-00007706` quedó confirmada como ejemplo real y válido. Esto
  confirma textualmente la observación del solicitante: *"el ejemplo que pusiste de
  F F01-00007416 está totalmente pagada en NC la cual no entraría comisión"*.
- **Lección de diseño:** un diario de ventas (ej. `F110 Venta nacional`) puede alojar tanto
  facturas como Notas de Crédito — nunca inferir el tipo de conciliación por el nombre del
  diario, siempre verificar `move_type` del asiento.

### Añadido — nuevas reglas de exclusión confirmadas
- **Boletas no son comisionables en ningún canal.** Hallazgo de alto impacto: el
  `l10n_latam_document_type_id` "(03) Boleta" representa el **45,8% de los documentos
  Nacional** de la muestra (422 de 922) — casi la mitad del volumen que el PRD venía contando
  como "facturas". También se excluye "(07) Nota de Crédito Boleta".
- **TTG se verifica por 2 campos, no 1.** `sale_type_id = TTG` y `invoice_payment_term_id` con
  "TTG" casi siempre coinciden (378 casos), pero hay 5 facturas adicionales con solo
  `sale_type_id=TTG` que se perderían si el filtro solo revisara la condición de pago. La
  regla ahora es un `OR` entre ambos campos.
- **MARKETING/OFICINA se excluyen en Nacional e Internacional por igual.** Se verificó que
  Internacional también tiene el equipo `MARKETING INT` (2 de 53 facturas en el ciclo
  analizado) — el filtro del ETL debe matchear por patrón (`team_id.name ILIKE 'MARKETING%'`
  o `= 'OFICINA'`), no asumir que la regla es exclusiva de un canal.
- **El diario "Transitory receivable and payable" (TRP) no es un cobro real.** Se verificó con
  un asiento real (`PTRP/2025/14187`, ref. "Redeem Bill of Exchange FLC-02713") que este
  diario traspasa el saldo de la cuenta `1212001 Facturas por cobrar` a `1051099 Cuenta
  transitoria de pagos de letras` — es el momento en que una factura se convierte en letra,
  no un cobro. Representaba el 23,4% de la muestra de conciliaciones y antes quedaba "a
  confirmar en Fase 0"; ahora queda **confirmado como excluido** (el cobro real se reconoce
  después, al pagarse la letra).
- **Trazabilidad Letra → Pedido confirmada end-to-end.** Corrección sobre una afirmación
  anterior ("no se puede trazar hasta el pedido"): sí se puede, con 2 saltos —
  `Letra.invoice_origin` → nombre de la Planilla (ej. `FLC-02726`) → `Planilla.invoice_ids` →
  `Factura.invoice_origin` = número de pedido real (ej. `S24241`), verificado con un ejemplo
  real completo.

### Cambiado en el PRD
- Nueva subsección "Dos etapas: extracción vs. transformación" con diagrama Mermaid ampliado
  de 7 criterios de exclusión (antes 5), reflejando el rol de la columna `FILTRO` de los
  Excel reales.
- Tabla de "Volumetría real por canal" ahora incluye una advertencia explícita de que esos
  conteos son de extracción (incluyen boletas/TTG/NC) y no de transformación.
- Tabla de "NC vs. transferencia" corregida: el diario `F110 (Venta nacional)` no es una
  categoría aparte de "Nota de Crédito" — es el mismo diario, lo que generaba doble conteo en
  la versión anterior.

### Añadido en el script de evidencia
- `investigation/investigacion_comisiones_odoo.py`: 5 secciones nuevas, todas reproducibles de
  solo lectura — `[7d]` boletas por canal, `[7e]` TTG por doble campo, `[7f]` trazabilidad
  letra→pedido, `[7g]` diario TRP, y verificación de `move_type` agregada a `[5]` (con alerta
  automática si una factura resulta 100% NC). `[7]` (vendedores genéricos) ahora cubre ambos
  canales.

### Impacto
- Ningún código de producción fue modificado; todo solo lectura contra Odoo.
- Estas correcciones son significativas: sin ellas, el futuro motor de reglas habría
  comisionado boletas (≈46% del volumen Nacional) y traspasos contables a letras (23% de las
  conciliaciones) que no corresponden a cobros reales, y habría usado 2 ejemplos de referencia
  con la regla de Nota de Crédito invertida.

## [2026-10-21] — Hallazgos de seguridad corregidos

### Contexto
El PRD decía que el repositorio no tenía `.gitignore` y describía la falta de acceso a
`ir.model` sin dejar explícito que la cuenta no es el usuario master.

### Cambiado en el PRD
- El aviso de “sin archivo `.gitignore`” pasa a resuelto: `.gitignore` está versionado,
  excluye `.env`, y ese archivo no está en el índice ni en el historial de commits.
- El hallazgo de permisos queda confirmado: la cuenta de `.env` no es el usuario master de
  Odoo y no tiene el grupo "Administration/Access Rights". La exploración de modelos sigue
  por `fields_get`.
- El párrafo de cierre ya no trata los tres puntos como pendientes. Abierto queda solo el
  de credenciales personales en texto plano.

### Impacto
- Solo documentación. No cambia código, credenciales ni el alcance del ETL.

## [2026-10-20 · tarde] — Lógica de comisión de Nacional completamente confirmada

### Contexto
El solicitante aportó 2 Excel adicionales: `Proceso_Manual/nacional/Porcentajes/Tabla de
Comisiones.xlsx` y `Proceso_Manual/nacional/calculo_vendedores/COMISIONES 2026 AGOSTO.xlsx`.
Esto cierra la última pregunta mayor que quedaba abierta ("¿Cuál es la lógica de cálculo
exacta que hoy aplica Nacional?" — respuesta anterior: "Aún no lo tengo").

### Descubierto y confirmado
- **Nacional usa la misma lógica de jerarquía de % fijo que Internacional**, pero con **4
  roles** (Representante de Venta, Jefe Técnico, Jefe Comercial, Gerente) en vez de 1, y con
  una clave de búsqueda más granular: **Línea Comercial + Zona** (27 combinaciones reales),
  no solo Línea Comercial.
- Fórmula verificada celda a celda contra un ejemplo real (factura `F F01-00007214`,
  PETMEDICA/LIMA 2 Y CENTRO): `Comision_rol = (Monto_Pagado/1.18) × (Subtotal_linea/
  Subtotal_FT) × %_rol`. Las 4 comisiones calculadas (4,751175 / 0,87714 / 1,096425 / 1,4619)
  coinciden de forma exacta con las celdas reales del Excel.
- La misma fórmula aplica a letras usando `ValorLT` (el monto de la letra específica
  reconocida en el periodo) en vez de `Monto_Pagado` — verificado también con un segundo
  ejemplo real.
- El campo "Zona" se confirmó en Odoo como el catálogo real
  `agr.sales.comercial.division.zone` (27 registros), accesible vía
  `sale.order.line.line_commercial_zone_id` — cierra la trazabilidad técnica completa desde
  el Excel hasta el modelo de datos de Odoo.
- Algunos roles pueden quedar sin porcentaje asignado para ciertas líneas (ej. AVIVET no
  tiene Jefe Técnico; EQUESTRIA no tiene Representante de Venta con %) — el motor de reglas
  debe soportar roles opcionales por combinación, no asumir que los 4 siempre aplican.
- La columna `Dias Atrasadas` del Excel real de Nacional reconfirma, de forma independiente,
  el hallazgo de pagos registrados antes de la fecha de factura (valores negativos reales:
  `-1`, `-3`, `-4`), ahora también con datos de agosto 2026.

### Cambiado en el PRD
- "Reglas de negocio" ya no distingue Nacional como pendiente; ambos canales se documentan
  bajo un mismo patrón de "jerarquía de roles con % fijo", con una tabla comparativa de
  granularidad (Nacional: Línea+Zona, 4 roles · Internacional: Línea, 1 rol).
- Sección de evidencia: nueva subsección "Matriz real de comisiones — Nacional" con tabla de
  ejemplo (6 de las 27 combinaciones reales) y la fórmula verificada paso a paso.
- Banner ejecutivo, bullets de alcance, roadmap (Fase 0) y riesgos actualizados: la Fase 0 de
  reglas de cálculo queda prácticamente cerrada; solo falta el formato del layout de RRHH y la
  ambigüedad SI/TODOS de Internacional.
- "Preguntas abiertas" pasó de 5 a 1 pregunta genuinamente pendiente sobre lógica de cálculo
  (el formato del layout de RRHH); la pregunta de Nacional se movió a la tabla de "respondidas
  y confirmadas".
- Modelo de datos: `regla_comision` ahora incluye `rol` y `zona` (nullable, solo Nacional).
- RBAC: el rol "Vendedor" se amplía explícitamente para cubrir los 4 roles comisionables de
  Nacional (Representante, Jefe Técnico, Jefe Comercial, Gerente de línea).

### Añadido
- `investigation/investigacion_comisiones_odoo.py`: nueva sección `[7a]` que verifica el
  catálogo real de zonas en Odoo (`agr.sales.comercial.division.zone`, 27 registros),
  reproducible de solo lectura.

### Impacto
- Ningún código de producción fue modificado. La inspección del nuevo Excel se hizo con un
  script temporal de solo lectura (`openpyxl`), eliminado al finalizar esta sesión.
- La Fase 0 de levantamiento de reglas de cálculo queda, en la práctica, cerrada para ambos
  canales — el motor de reglas del TO-BE ya tiene toda la información de negocio necesaria
  para implementarse, salvo el formato final del archivo de RRHH.

## [2026-10-20] — Corrección de roles, reglas confirmadas con Excel reales y stack revisado

### Contexto
El solicitante aportó: (1) correcciones sobre quién ejecuta cada paso del proceso AS-IS,
(2) respuestas confirmadas a casi todas las preguntas abiertas del PRD anterior, y (3) los 9
Excel reales del proceso manual de septiembre 2026 (`Proceso_Manual/`), que permitieron
verificar con fórmulas de celda reales — no solo con datos de Odoo — exactamente cómo se
calcula hoy la base de comisión.

### Cambiado
- **Proceso AS-IS corregido: son 2 personas en serie en Nacional, no 1.** El Supervisor de
  Proyectos de Finanzas (días 8-10 del mes siguiente) hace la extracción y el primer cálculo;
  la Jefa de Aplicaciones (días 11-15) procesa y valida ese cálculo antes de pasarlo a
  Dirección Comercial (hasta el día 20).
- **Ruta de aprobación de Internacional corregida:** el Supervisor calcula directamente con la
  matriz de % por vendedor/línea comercial y envía el resultado a la **Gerencia de Ventas
  Internacional** — el cálculo de Internacional **nunca pasa por Dirección Comercial**.
- **Reglas de negocio pasaron de "propuestas a validar" a "confirmadas"**, con fórmulas
  exactas verificadas contra celdas reales de los Excel de `Proceso_Manual/`:
  - Base de cálculo: `Monto Pagado ÷ 1,18 (sin IGV) × (Subtotal línea / Subtotal factura)`,
    igual en ambos canales.
  - Letras: la comisión se reconoce sobre las letras pagadas **en el periodo** (no acumulado
    hasta el 100% de la factura) — `Total General × (Letras pagadas del periodo / Letras
    totales)`. Protestada no comisiona; descontada sí comisiona (igual que cartera/cobranza).
  - Internacional: `Pago por artículo USD = Pago USD × (Monto venta línea / Total factura)`,
    con el tipo de cambio del día exacto de pago (`TC FECHA DE PAGO`).
  - Matriz real de % por colaborador × línea comercial (AGROVET/PETMEDICA/AVIVET) documentada
    con cifras reales del ciclo 20-ago al 20-sep 2026.
- **Roles y RBAC actualizados:** se separan "Supervisor de Proyectos de Finanzas", "Jefa de
  Aplicaciones", "Dirección Comercial" (solo Nacional) y "Gerencia de Ventas Internacional"
  (solo Internacional) como roles distintos.
- **Sección técnica reescrita:** se aclara explícitamente que Finanzas AGV es solo una
  referencia de lecciones aprendidas, no una plantilla a copiar. Se responde la pregunta del
  solicitante sobre Flask (sigue siendo adecuado para la API, dado el volumen bajo) y se
  recomienda incorporar prácticas de ingeniería de datos open source: **dbt-core** para
  transformaciones versionadas y testeadas (reemplaza las fórmulas de Excel sin control de
  versiones), **Dagster** como orquestador más liviano que Celery+Redis+Beat para este
  volumen, **dbt tests/Great Expectations** para bloquear inconsistencias automáticamente, y
  **pytest + CI** desde el día 1 (ausente en Finanzas AGV según su propia auditoría).
- **Preguntas abiertas recortadas:** de 9 preguntas, 7 quedaron respondidas y confirmadas en
  esta iteración (documentadas en una tabla de trazabilidad). Solo quedan abiertas: el %/lógica
  de Nacional, el formato exacto del layout de RRHH, la base exacta de atribución "SI/TODOS" en
  Internacional, posibles diarios adicionales a excluir, y el criterio de "NO VA" para pagos
  menores.

### Añadido
- Hallazgo nuevo: diarios contables **"Facturas Sunat"** (código `001`) y **"F060 (Venta
  exterior)"** (código `060`) deben excluirse del cálculo — confirmado con volumetría real
  (9,7%-11,3% de las facturas en ambos canales).
- Hallazgo nuevo: forma programática de distinguir una factura pagada con Nota de Crédito
  (excluida) de una pagada por transferencia o aplicación de saldo a favor (sí comisiona),
  verificada con `invoice_payments_widget` y el `move_type` del asiento de conciliación (6,6%
  de los pagos de una muestra real fueron vía NC).
- Nuevas secciones de evidencia en el PRD con los campos técnicos exactos de las 3 plantillas
  de exportación manual de Odoo (`Creditos_Comi_Nacional_Pagos`,
  `Creditos_Reporte_Internacional_Comi_V1`, `Creditos_Pago_LE_CO_DES_CAR`).
- `investigation/investigacion_comisiones_odoo.py`: 2 secciones nuevas (diarios excluidos,
  NC vs. transferencia), reproducibles de solo lectura contra Odoo.

### Impacto
- Ningún código de producción fue modificado. La revisión de los 9 Excel de `Proceso_Manual/`
  se hizo con un script temporal de solo lectura (`openpyxl`), eliminado al finalizar esta
  sesión — no forma parte del entregable porque referencia archivos con datos de clientes
  reales.
- El PRD ahora refleja con mucha mayor fidelidad el proceso real (2 personas, ruta de
  aprobación distinta por canal) y reduce el riesgo de que el futuro motor de reglas calcule
  distinto a como lo hace hoy el negocio.

## [2026-10-16] — PRD inicial de Comisiones Nacional e Internacional

### Añadido
- `docs/PRD_COMISIONES_NACIONAL_INTERNACIONAL.html`: primer PRD del proyecto. Documenta el
  proceso AS-IS 100% manual de los canales Nacional (PEN) e Internacional (USD), las 9 mejoras
  solicitadas (dashboards, RBAC, workflow de aprobación, SSO/2FA, motor de reglas, ETL
  automatizado, auditoría, disputas y exportación a RRHH), la arquitectura técnica propuesta
  (reutilizando el stack ya validado de Finanzas AGV: Flask + Next.js + Supabase/RLS + Render),
  el modelo de datos, el roadmap por fases (Fase 0 de levantamiento de reglas → Fase 4 de
  expansión) y las preguntas abiertas pendientes de validar con Dirección Comercial.
- `investigation/investigacion_comisiones_odoo.py`: script nuevo de solo lectura que conecta
  contra el Odoo real de Agrovet Market (usando `.env`) y reproduce todas las cifras citadas en
  el PRD: catálogos de canal/tipo de venta/línea comercial, volumetría por canal, la casuística
  de pagos "contado/100% pago adelantado" con fecha de pago distinta a la fecha de factura, la
  evidencia de que `account.partial.reconcile.max_date` es la fecha efectiva de cobro correcta,
  la trazabilidad de letras hacia su factura origen, y la concentración de facturas bajo equipos
  administrativos (MARKETING, OFICINA) que requieren una regla de atribución de vendedor.

### Hallazgos relevantes de esta investigación
- El servidor Odoo real responde `server_version: "16.0+e"` (Odoo 16 Enterprise SaaS). Otros
  informes de `auditoria/` indicaban Odoo 17 para el proyecto de Finanzas AGV; para este
  proyecto de Comisiones se confirma 16, dato que debe usarse al definir compatibilidad de API.
- El usuario de integración definido en `.env` es una cuenta de correo personal
  (`jose.montero@agrovetmarket.com`) con contraseña en texto plano, y el repositorio no tiene
  `.gitignore` que excluya `.env`. Ambos puntos quedaron registrados como hallazgos de
  seguridad en el PRD (sección "Hallazgos de seguridad detectados") y como riesgo a mitigar
  antes de la Fase 1 del roadmap.
- Decisión de alcance confirmada con el solicitante: el canal **Digital** (ecommerce/
  marketplaces, ~330 facturas/mes, 1 solo vendedor) queda fuera de la v1 y las reglas exactas de
  cálculo (porcentajes de Internacional, lógica de Nacional) quedan como **Fase 0** de
  levantamiento, no como parte de este primer PRD.

### Impacto
- Ningún código de producción fue modificado. Todas las consultas a Odoo durante esta sesión
  fueron de solo lectura (`search`, `search_read`, `read`, `fields_get`).
- Este PRD es la base para iniciar la Fase 0 (levantamiento de reglas de negocio) antes de
  cualquier desarrollo del motor de cálculo o del ETL.
