# SPEC: Motor determinista de comisiones (`commission-engine`)

Estado: aprobado e implementado para el piloto local — Phase 4 Implement
Módulo del mapa: `commission-engine`
Fuentes: `CAPABILITY_MAP.md`, `docs/PRD_COMISIONES_NACIONAL_INTERNACIONAL.html`,
`.cursor/plans/mvp-paridad-streamlit_af67788d.plan.md` y scripts reproducibles de
`investigation/`.

## Supuestos declarados

1. El piloto se ejecutará localmente con Python y un único archivo SQLite por corrida o
   conjunto de corridas; no requiere Supabase, PostgreSQL, Dagster, dbt, Flask ni servicios
   remotos adicionales.
2. Odoo 16 Enterprise SaaS seguirá siendo la fuente operacional y se consultará
   exclusivamente en modo lectura mediante XML-RPC.
3. El motor recibirá o extraerá snapshots de entrada y reglas versionadas; no ofrecerá UI,
   workflow de aprobación, exportación Excel ni escritura en Odoo.
4. Los importes se representarán con `Decimal` desde su ingreso al dominio. No se usarán
   `float` para bases, porcentajes, tipos de cambio, comisiones ni comparaciones monetarias.
5. Una línea con catálogo, mapeo o regla pendiente no se adivina ni se descarta
   silenciosamente: produce una excepción bloqueante y no se considera pagable.
6. La zona horaria de negocio será `America/Lima`; los periodos se expresarán como fechas
   inclusivas y la fecha efectiva de cobro será
   `account.partial.reconcile.max_date`.
7. La implementación vive en `mvp/` y mantiene la separación respecto de Streamlit.

## Objetivo

Construir un núcleo Python independiente de Streamlit que calcule comisiones de forma
determinista, trazable y repetible para los canales Nacional (PEN) e Internacional (USD).
El usuario primario del módulo es el Supervisor de Proyectos de Finanzas; sus consumidores
son `historical-parity` y, posteriormente, `interfaz-minima`.

El piloto queda acotado a los cierres ya aprobados:

- Nacional: septiembre de 2026, mes calendario.
- Internacional: ciclo del 20 de agosto al 20 de septiembre de 2026.

El motor debe convertir snapshots Bronze en datos normalizados Silver y resultados Gold,
aplicando las reglas confirmadas del PRD. Debe producir comisiones por
documento/línea/cobro/beneficiario, seguimiento de letras, resumen por persona y puesto, y
excepciones explícitas. Un resultado solo es reproducible si conserva la identidad del
snapshot fuente, la versión del conjunto de reglas y la versión del motor.

### Determinismo exigido

Para una solicitud canónica `R`, un snapshot SQLite inmutable `S`, un conjunto de reglas
versionado `V` y una versión de motor `E`:

```text
calculate(R, S, V, E) -> mismo conjunto ordenado de filas Gold,
                         mismos importes Decimal,
                         mismas excepciones,
                         mismo manifest y mismo checksum
```

El determinismo requiere:

- orden total explícito en toda salida;
- claves naturales estables de Odoo y claves derivadas documentadas;
- fechas y zona horaria explícitas;
- `Decimal` construido desde texto, nunca desde binario `float`;
- reglas con vigencia, versión, prioridad y precedencia resueltas;
- ausencia de dependencia del reloj del sistema dentro del cálculo;
- ausencia de llamadas a Odoo desde la fase de transformación/cálculo;
- hash SHA-256 de inputs canónicos, reglas y resultados;
- rerun idempotente: repetir una corrida no duplica Bronze, Silver ni Gold.

## Stack del piloto

- Python 3.12 o superior como runtime objetivo. La compatibilidad con Python 3.14 se
  verificará, pero no se asumirá hasta ejecutar la futura suite.
- Biblioteca estándar: `dataclasses`, `decimal`, `datetime`, `hashlib`, `json`, `sqlite3`,
  `typing` y `xmlrpc.client`.
- SQLite 3, en modo local, con claves foráneas activas y transacciones atómicas.
- `pytest` para pruebas unitarias, de integración y contratos.
- `ruff` para lint y formato.
- `openpyxl` pertenecerá al módulo futuro `historical-parity`, no al motor.
- Streamlit pertenecerá a `interfaz-minima`; el motor no lo importará.

Las versiones exactas de dependencias de desarrollo se fijarán en la fase de
planificación/implementación, previa aprobación. Esta SPEC no instala ni modifica
dependencias.

## Comandos completos

Estos son los contratos de ejecución que la implementación deberá habilitar desde la raíz
del repositorio. No deben ejecutarse hasta que exista `mvp/` y sus dependencias hayan sido
aprobadas.

```powershell
# Ejecutar toda la suite del motor
python -m pytest mvp/tests -q

# Ejecutar unitarias, integración o contratos por separado
python -m pytest mvp/tests/unit -q
python -m pytest mvp/tests/integration -q
python -m pytest mvp/tests/contracts -q

# Lint y comprobación de formato
python -m ruff check mvp
python -m ruff format --check mvp

# Comprobación de sintaxis
python -m compileall -q mvp

# Crear un snapshot Bronze local desde Odoo, siempre en modo solo lectura
python -m mvp.cli extract-odoo `
  --channel nacional `
  --period-start 2026-09-01 `
  --period-end 2026-09-30 `
  --database var/commission-pilot.sqlite3 `
  --page-size 300 `
  --read-only

# Calcular Nacional sobre un snapshot ya cerrado
python -m mvp.cli calculate `
  --channel nacional `
  --period-start 2026-09-01 `
  --period-end 2026-09-30 `
  --database var/commission-pilot.sqlite3 `
  --source-snapshot-id "<snapshot-id>" `
  --ruleset-version "<version>"

# Calcular Internacional sobre el ciclo aprobado
python -m mvp.cli calculate `
  --channel internacional `
  --period-start 2026-08-20 `
  --period-end 2026-09-20 `
  --database var/commission-pilot.sqlite3 `
  --source-snapshot-id "<snapshot-id>" `
  --ruleset-version "<version>"

# Emitir el contrato canónico que consumirán otros módulos
python -m mvp.cli export-contract `
  --run-id "<run-id>" `
  --database var/commission-pilot.sqlite3 `
  --output var/contracts/<run-id>.jsonl

# Validaciones de repositorio antes de commit
git diff --check
git status --short
```

No habrá un comando que escriba en Odoo. `extract-odoo` fallará si no recibe
`--read-only`.

## Estructura futura del proyecto

La estructura se define como contrato, no se crea en esta fase:

```text
mvp/
  __init__.py
  cli.py                         # Adaptador CLI; no contiene reglas de negocio
  application/
    contracts.py                 # Request/result, puertos y errores públicos
    services.py                  # Orquesta snapshot -> Silver -> Gold
  domain/
    money.py                     # Decimal, monedas y política de cuantización
    periods.py                   # Ventanas inclusivas por canal
    rules.py                     # Vigencia, alcance, precedencia y conflictos
    commissions.py               # Cálculo puro de base y comisión
    letters.py                   # Seguimiento y anti-duplicado
  infrastructure/
    odoo_readonly.py             # XML-RPC de lectura, paginado y bulk
    sqlite/
      connection.py              # PRAGMA, transacciones y migraciones
      schema.sql                 # Tablas Bronze/Silver/Gold y restricciones
      repositories.py            # Persistencia, sin lógica de negocio
  tests/
    unit/                        # Funciones puras y reglas
    integration/                 # SQLite real temporal y transacciones
    contracts/                   # Esquemas/orden/checksums consumibles
    fixtures/                    # Datos sintéticos mínimos, sin secretos
var/                             # Artefactos locales ignorados por Git
```

### Arquitectura medallón local en SQLite

#### Bronze: evidencia inmutable

Bronze conserva la respuesta fuente sin aplicar reglas de negocio. Cada tabla incluye como
mínimo `snapshot_id`, `source_model`, `odoo_id`, `write_date`, `loaded_at`,
`payload_json` canónico y `payload_sha256`.

Entidades mínimas:

- `bronze_account_move`;
- `bronze_account_move_line`;
- `bronze_partial_reconcile`;
- `bronze_bill_form`;
- `bronze_partner`;
- `bronze_product`;
- `bronze_account`;
- `bronze_journal`;
- `bronze_rule_source`;
- `bronze_snapshot_manifest`.

La extracción:

- usa `fields_get`, `search_count`, `search_read` y, cuando sea imprescindible, `read`;
- pagina por `id` ascendente con tamaño configurable, sin offsets costosos;
- declara campos explícitos y dominios por canal/periodo;
- resuelve relaciones en lotes y prohíbe N+1;
- hace upsert por `(snapshot_id, source_model, odoo_id)`;
- no ejecuta `create`, `write`, `unlink` ni métodos de negocio;
- cierra el snapshot solo después de validar conteos y hashes.

#### Silver: dominio normalizado

Silver contiene filas tipadas y relaciones resueltas, sin depender del JSON original para
calcular:

- `silver_document`;
- `silver_document_line`;
- `silver_payment_allocation`;
- `silver_letter`;
- `silver_letter_payment`;
- `silver_customer_country`;
- `silver_commission_rule`;
- `silver_rule_scope`;
- `silver_period_override`;
- `silver_eligibility_decision`.

Cada decisión de elegibilidad conserva `eligible`, `reason_code`, `rule_id`,
`source_keys` y evidencia. Las exclusiones se aplican por línea cuando corresponda. País se
resuelve en bulk por `commercial_partner_id`, luego `partner_id` y finalmente
`partner_shipping_id`; un país faltante genera excepción, no inferencia.

#### Gold: contrato de consumo

Gold es la única capa consumida por `historical-parity` y `interfaz-minima`:

- `gold_commission_line`: una fila por
  `run/documento/línea/cobro/beneficiario/regla`;
- `gold_letter_tracking`: emitidas, pagadas antes, pagadas en periodo, faltantes, montos,
  estados y clave anti-duplicado;
- `gold_person_summary`: persona, puesto, Contado, Crédito, Letras y Total;
- `gold_exception`: código, severidad, bloqueo, entidad, evidencia y acción requerida;
- `gold_run_manifest`: request, versiones, hashes, conteos, estado y timestamps;
- `gold_contract_row`: proyección canónica y ordenada para consumidores externos.

Toda tabla Gold referencia `run_id`, `snapshot_id`, `ruleset_version` y
`engine_version`. Los resultados de una corrida completada son inmutables.

## Contratos públicos

### Solicitud de cálculo

`CommissionRunRequest` debe exigir:

- `channel`: `nacional` o `internacional`;
- `period_start` y `period_end`, ambas inclusivas;
- `source_snapshot_id`;
- `ruleset_version`;
- `engine_version`;
- `business_timezone = "America/Lima"`;
- `requested_at`, solo para auditoría y excluido de la lógica monetaria.

El request se serializa como JSON canónico UTF-8, con claves ordenadas y fechas ISO-8601.
Su `request_sha256` forma parte del manifest.

### Resultado de cálculo

`CommissionRunResult` debe exponer:

- `run_id` derivado de los hashes de request, snapshot, reglas y motor;
- estado `completed`, `blocked` o `failed`;
- conteos Bronze/Silver/Gold;
- totales por moneda y canal;
- excepciones ordenadas por severidad, código y clave de entidad;
- checksums de cada dataset Gold;
- ubicación o iterador de las filas Gold, sin objetos Streamlit.

Una excepción bloqueante da estado `blocked`; nunca se devuelve un total “pagable” parcial
como si fuera definitivo.

### Contrato para `historical-parity`

El motor proveerá únicamente:

1. filas canónicas Gold con claves exactas de
   documento/línea/cobro/persona/categoría;
2. importes crudos `Decimal` serializados como texto;
3. importes de presentación cuantizados a dos decimales;
4. moneda y escala;
5. `comparison_policy` con tolerancia absoluta `0.01` después de cuantizar a dos decimales;
6. hashes, reglas aplicadas, inclusiones/exclusiones y trazabilidad.

`historical-parity` será responsable de importar Excel, leer golden masters, emparejar
filas, comparar, clasificar diferencias y declarar paridad. Este módulo no conocerá hojas de
Excel ni implementará comparadores. Las claves, inclusiones y exclusiones se compararán de
forma exacta por el consumidor; la tolerancia aplica solo al importe monetario.

La política expuesta será:

```json
{
  "scale": 2,
  "rounding": "ROUND_HALF_UP",
  "absolute_tolerance": "0.01",
  "keys_must_match_exactly": true,
  "membership_must_match_exactly": true
}
```

### Contrato para Streamlit

El motor no importará Streamlit ni administrará estado de sesión. La UI futura podrá:

- solicitar una corrida mediante el puerto de aplicación o la CLI;
- leer únicamente `CommissionRunResult` y tablas/vistas Gold;
- mostrar excepciones y totales sin recalcular reglas;
- impedir presentación pagable cuando el resultado esté `blocked`.

## Reglas funcionales específicas

### Base, impuestos y cobros

- La base usa importes netos e impuestos reales de Odoo.
- Dividir entre `1.18` solo es equivalente cuando toda la operación tiene IGV 18%; nunca se
  aplica a una exportación exonerada.
- Cada pago parcial se reconoce en el periodo de su `max_date`.
- La base del cobro se prorratea por la proporción neta de cada línea.
- Internacional usa el tipo de cambio del día exacto del pago.

### Elegibilidad y exclusiones

- Boletas y Nota de Crédito-Boleta quedan excluidas en ambos canales.
- TTG se detecta con `sale_type_id OR invoice_payment_term_id`.
- Equipos cuyo nombre coincide con `MARKETING%` u `OFICINA` quedan excluidos sin
  reatribución.
- Diarios `001` Facturas Sunat y `060` F060 Venta exterior quedan excluidos.
- `payment_state = reversed` queda excluido.
- Una conciliación `out_refund` no comisiona; si la NC es parcial, solo continúa la porción
  cobrada por medio válido.
- El diario TRP representa traslado a letra y no un cobro.
- Interés, flete, seguro, gasto de exportación, gasto administrativo/financiero y reajuste se
  excluyen por línea.
- La única cuenta de venta de producto confirmada para este piloto es `7022101`, con
  independencia del canal del asiento. `7011001`, `7599001`, `7599006`, `7599007` y
  `7599009` quedan excluidas; cualquier otra cuenta bloquea por desconocida.
- Una Nota de Débito se decide línea por línea: debe ser producto real y usar una cuenta
  permitida. La marca histórica `NO VA` no es una regla: esas filas no comisionan porque
  corresponden a gastos de exportación en `7011001` o intereses en `7599009`.
- Cuenta, concepto o diario desconocido generan excepción bloqueante hasta aprobación; no se
  agregan a una lista implícita.
- `REGV` (regularización de ventas en Odoo) permanece incluido hasta que Contabilidad indique
  lo contrario; no forma parte de los diarios excluidos.

### Letras

- El enlace es Letra → Planilla → Factura → pedido; el canal se hereda de la factura.
- Protestada no comisiona; descuento, cartera y cobranza sí pueden comisionar.
- Se reconoce el monto real cobrado de cada letra dentro del periodo.
- Una clave única de letra/conciliación impide pagar dos veces entre periodos.
- El control por cantidad del Excel de septiembre es evidencia de paridad, no reemplaza el
  monto real cuando las letras difieren.

### Reglas de beneficiarios

- Nacional resuelve hasta cuatro roles por Línea Comercial + Zona:
  Representante de Venta, Jefe Técnico, Jefe Comercial y Gerente. Un rol puede no aplicar,
  pero una comisión distinta de cero sin beneficiario es excepción bloqueante.
- Internacional aplica porcentajes por beneficiario y experiencia:
  Ariana, Vanessa, Sandra, Umberto e Ivonne sobre TODOS; Luis sobre América + PETMEDICA;
  Mayumi al `0.5%` sobre AVIVET + LATAM.
- Los catálogos América y LATAM permanecen vacíos hasta que el usuario entregue nombres de
  país. Cada nombre se resuelve una sola vez, por coincidencia exacta de `res.country.name` y
  luego por `res.country.code`, y se persiste como `country_id`/ISO. Sin coincidencia exacta
  se bloquea para revisión; no se compara texto por cada línea ni se usa coincidencia difusa.
- Aminoplex Forte x 100 ml usa un override versionado a PETMEDICA mientras Odoo informe
  AGROVET.
- La precedencia es factura > producto > línea > cliente > país > TODOS. A igual alcance,
  gana mayor prioridad y luego la versión vigente más reciente. Una exclusión gana a una
  inclusión de igual alcance/prioridad; un empate no resoluble bloquea.
- Las reglas permanentes y overrides de periodo son datos versionados y auditables. Un
  override expira con su periodo.

## Estilo de código

- Nombres de módulos, funciones y variables en `snake_case`; clases y protocolos en
  `PascalCase`; constantes en `UPPER_SNAKE_CASE`.
- Funciones de dominio puras, pequeñas y con tipos completos.
- Puertos en `application/`; adaptadores Odoo/SQLite en `infrastructure/`.
- Sin `print()` de depuración, estado global mutable, importaciones de UI ni SQL dentro de
  funciones de dominio.
- Excepciones de dominio con códigos estables; los textos humanos no se usan como claves.
- Docstrings explican invariantes y decisiones, no repiten la firma.

Snippet canónico del estilo esperado:

```python
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

MONEY_QUANTUM = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class CommissionAmount:
    raw: Decimal
    currency: str

    def presented(self) -> Decimal:
        """Cuantiza solo en la frontera de presentación/comparación."""
        return self.raw.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def calculate_commission(base: Decimal, rate: Decimal) -> Decimal:
    if base < Decimal("0") or rate < Decimal("0"):
        raise ValueError("base and rate must be non-negative")
    return base * rate
```

## Estrategia de pruebas

### Unitarias

Cubren funciones puras y tablas de decisión:

- neto con IGV 18% y exportación exonerada;
- pago parcial y prorrateo por línea;
- tipo de cambio por fecha efectiva;
- exclusiones por documento, TTG dual, equipo, diario, NC, TRP, cuenta y concepto;
- Nota de Débito mixta;
- precedencia, vigencia, prioridad, exclusión y conflicto de reglas;
- roles opcionales Nacional y alcances Internacional;
- override de Aminoplex;
- estados de letras y anti-duplicado;
- `Decimal`, cuantización `ROUND_HALF_UP` y política de tolerancia expuesta.

### Integración

Usan un SQLite temporal real:

- migración desde base vacía;
- carga idempotente de Bronze;
- normalización Silver con claves foráneas;
- transacción atómica: un fallo no deja Gold parcial;
- rerun con los mismos inputs produce los mismos hashes y filas;
- snapshot o ruleset distinto produce un `run_id` distinto;
- restricciones únicas de letra/conciliación y de claves Gold;
- extracción Odoo simulada verifica campos explícitos, paginación por `id`, bulk y rechazo
  de métodos de escritura.

### Contratos

- JSON/JSONL canónico, esquema estable, orden total y decimales como texto;
- `gold_person_summary` reconcilia con la suma de `gold_commission_line`;
- toda comisión no cero tiene beneficiario, regla y trazabilidad;
- `total_emitidas = pagadas_hasta_fin + faltantes`;
- pagadas del periodo no intersectan pagadas históricas;
- RRHH recibe dos entregas independientes: Nacional para Dirección Comercial e Internacional
  para Gerencia Internacional; cada archivo conserva el mismo contrato de resumen sin mezclar
  canales ni aprobaciones;
- la interfaz de paridad publica crudo, presentado y política `0.01`, sin importar Excel.

### Golden masters

Los dos libros de septiembre sirven como datos de aceptación del módulo
`historical-parity`, no como fixtures unitarios del motor. En esta SPEC solo se exige que el
motor entregue las claves, importes y metadatos necesarios para compararlos. La suite del
motor usará fixtures sintéticos, pequeños y anonimizados.

No se fija un porcentaje de cobertura como sustituto de los casos de negocio. Todos los
criterios y ramas anteriores deben tener al menos una prueba positiva y una negativa.

## Boundaries

### Siempre

- Mantener Odoo en solo lectura y usar campos explícitos, paginación y consultas bulk.
- Separar dominio, aplicación e infraestructura.
- Persistir trazabilidad desde Gold hasta las claves de Odoo y la regla aplicada.
- Usar `Decimal`, transacciones SQLite, constraints e idempotencia.
- Bloquear resultados con datos o reglas ambiguos.
- Ejecutar unitarias, integración, contratos, lint, formato, sintaxis y
  `git diff --check` antes de proponer un cambio del motor.

### Preguntar primero

- Agregar o actualizar dependencias.
- Cambiar esquema SQLite o contratos Gold ya aprobados.
- Cambiar redondeo, escala, tolerancia o definición de periodo.
- Incorporar nuevas cuentas, diarios, países o exclusiones.
- Cambiar precedencia de reglas o comportamiento ante conflictos.
- Ampliar el piloto a otros cierres o canales.

### Nunca

- Escribir, crear, actualizar o eliminar datos en Odoo.
- Leer credenciales desde código, versionarlas o registrarlas en logs.
- Importar Streamlit o implementar lógica de UI dentro del motor.
- Leer golden masters, importar Excel o decidir paridad dentro de `commission-engine`.
- Usar `float` para dinero, porcentajes o tipo de cambio.
- Inferir país, cuenta, concepto, beneficiario o elegibilidad desde texto libre cuando falta
  un catálogo aprobado.
- Ocultar excepciones, devolver un resultado bloqueado como pagable o modificar una corrida
  completada.
- Incluir el canal Digital en este piloto.

## Criterios específicos de éxito

1. El mismo request, snapshot, ruleset y versión de motor produce byte a byte el mismo
   contrato canónico y los mismos checksums en dos corridas limpias.
2. Repetir extracción y cálculo no duplica registros y conserva las restricciones de
   trazabilidad y anti-duplicado.
3. Nacional septiembre 2026 e Internacional 20-ago–20-sep 2026 pueden representarse con los
   periodos, monedas y contratos definidos, sin lógica especial en Streamlit.
4. Cada línea Gold identifica documento, línea fuente, cobro o letra, beneficiario, puesto,
   regla, decisión de elegibilidad, snapshot y corrida.
5. La suma de líneas Gold reconcilia exactamente, antes de presentación, con los resúmenes
   Gold por persona/puesto y categoría Contado/Crédito/Letras/Total.
6. Las reglas de base neta, pagos parciales, impuestos reales, tipo de cambio, exclusiones,
   letras y beneficiarios descritas en esta SPEC quedan cubiertas por pruebas automáticas.
7. Una comisión distinta de cero sin beneficiario, una cuenta/país/regla desconocidos o un
   conflicto de precedencia bloquean la corrida con excepción trazable.
8. Odoo no recibe ninguna llamada de escritura y la prueba de adaptador rechaza métodos no
   permitidos.
9. El contrato de `historical-parity` expone claves exactas, valor crudo, valor a dos
   decimales y tolerancia `0.01`, pero el motor no importa Excel ni compara golden masters.
10. El núcleo se ejecuta y prueba sin instalar ni importar Streamlit.
11. El piloto de septiembre no se declara apto para producción: esa decisión exige además
    `historical-parity` y 1–2 cierres adicionales por canal.

## Decisiones operativas cerradas

1. `7022101` es la cuenta elegible versionada; `7011001`, `7599001`, `7599006`, `7599007`
   y `7599009` son exclusiones contables explícitas.
2. `NO VA` deja de ser texto libre: identifica ND por gasto de exportación (`7011001`) o
   facturas de intereses (`7599009`), ambas no comisionables.
3. Sandra propone cambios Internacional y aprueba ese canal. Durante el piloto José Montero
   los aplica; Sandra no edita periodos cerrados. Dirección Comercial aprueba Nacional.
4. `REGV` queda incluido hasta una decisión contraria de Contabilidad.
5. América/LATAM son catálogos vacíos y configurables por nombres de país; no se inventan
   países para Luis o Mayumi.

## Puerta de aprobación

La SPEC fue aprobada por el usuario antes de la implementación. Los catálogos América/LATAM
vacíos bloquean únicamente reglas que los requieran, pero no la ejecución diagnóstica del
piloto.
