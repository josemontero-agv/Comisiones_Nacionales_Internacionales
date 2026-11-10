-- Contrato medallón alineado a mvp/infrastructure/sqlite/schema.sql.
-- No calcula comisiones, porcentajes ni roles. Esas decisiones siguen en el motor Python.
-- dbt solo hace staging sobre raw.factura, raw.linea_documento, raw.pago y raw.letra.
--
-- Las claves de snapshot y de corrida son las que ya asigna el motor (texto). No se
-- reemplazan por identity: cambiarlas partiría el contrato SQLite que este corte lee.
--
-- raw, gold y staging no deben agregarse a Exposed schemas. Flask usa DATABASE_URL
-- (rol postgres del pooler de sesión) solo en el servidor. Next.js no recibe esa cadena
-- ni la service role key.
--
-- RLS queda activo y forzado, sin políticas: anon, authenticated y service_role no
-- tienen GRANT. El rol postgres de Supabase es superusuario y sigue pudiendo operar
-- desde el servidor. El CLI de Supabase no estaba instalado en esta máquina; el nombre
-- del archivo sigue el formato <timestamp>_nombre.sql.

create schema if not exists raw;
create schema if not exists gold;
create schema if not exists staging;

comment on schema raw is
    'Aterrizaje Bronze/Silver y tablas tipadas. dbt no calcula comisiones aqui.';
comment on schema gold is
    'Resultado ya calculado por el motor Python: manifiesto, lineas, diferencias y excepciones.';
comment on schema staging is
    'Vistas de dbt-core. No elige roles ni porcentajes.';

revoke all on schema raw from public, anon, authenticated, service_role;
revoke all on schema gold from public, anon, authenticated, service_role;
revoke all on schema staging from public, anon, authenticated, service_role;

alter default privileges for role postgres in schema raw
    revoke all on tables from public, anon, authenticated, service_role;
alter default privileges for role postgres in schema gold
    revoke all on tables from public, anon, authenticated, service_role;
alter default privileges for role postgres in schema staging
    revoke all on tables from public, anon, authenticated, service_role;

create table if not exists raw.bronze_snapshot (
    snapshot_id text primary key,
    channel text not null,
    period_start text not null,
    period_end text not null,
    source_path text not null,
    source_sha256 text not null,
    loaded_at text not null,
    status text not null,
    constraint bronze_snapshot_channel_check
        check (channel in ('nacional', 'internacional')),
    constraint bronze_snapshot_status_check
        check (status in ('open', 'closed'))
);

create index if not exists bronze_snapshot_closed_lookup_idx
    on raw.bronze_snapshot (channel, period_start, period_end, source_path, loaded_at desc)
    where status = 'closed';

create table if not exists raw.bronze_record (
    snapshot_id text not null references raw.bronze_snapshot (snapshot_id),
    source_model text not null,
    source_key text not null,
    payload_json text not null,
    payload_sha256 text not null,
    primary key (snapshot_id, source_model, source_key)
);

create table if not exists raw.silver_record (
    snapshot_id text not null references raw.bronze_snapshot (snapshot_id),
    entity_type text not null,
    entity_key text not null,
    payload_json text not null,
    primary key (snapshot_id, entity_type, entity_key)
);

create table if not exists gold.gold_run (
    run_id text primary key,
    snapshot_id text not null references raw.bronze_snapshot (snapshot_id),
    channel text not null,
    status text not null,
    manifest_json text not null,
    completed_at text not null,
    constraint gold_run_channel_check
        check (channel in ('nacional', 'internacional'))
);

create index if not exists gold_run_snapshot_id_idx
    on gold.gold_run (snapshot_id);

create index if not exists gold_run_channel_completed_at_idx
    on gold.gold_run (channel, completed_at desc);

create table if not exists gold.gold_commission_line (
    run_id text not null references gold.gold_run (run_id),
    row_key text not null,
    payload_json text not null,
    primary key (run_id, row_key)
);

create table if not exists gold.gold_collected_line (
    run_id text not null references gold.gold_run (run_id),
    row_key text not null,
    payload_json text not null,
    primary key (run_id, row_key)
);

create table if not exists gold.gold_difference (
    run_id text not null references gold.gold_run (run_id),
    difference_key text not null,
    classification text not null,
    payload_json text not null,
    primary key (run_id, difference_key, classification)
);

create table if not exists gold.gold_exception (
    run_id text not null references gold.gold_run (run_id),
    exception_key text not null,
    payload_json text not null,
    primary key (run_id, exception_key)
);

-- Tablas tipadas para staging. Vacias hasta que se carguen. La comision y el
-- beneficiario, si vienen, ya estan aterrizados: dbt no los deriva.
create table if not exists raw.factura (
    snapshot_id text not null,
    factura_id text not null,
    canal text,
    documento text,
    fecha date,
    moneda text,
    partner_id text,
    pais_iso text,
    move_type text,
    payload_json text,
    primary key (snapshot_id, factura_id),
    constraint factura_canal_check
        check (canal is null or canal in ('nacional', 'internacional'))
);

create table if not exists raw.linea_documento (
    snapshot_id text not null,
    linea_id text not null,
    factura_id text,
    canal text,
    cuenta text,
    producto text,
    subtotal numeric,
    comision numeric,
    beneficiario text,
    payload_json text,
    primary key (snapshot_id, linea_id),
    constraint linea_documento_canal_check
        check (canal is null or canal in ('nacional', 'internacional'))
);

comment on column raw.linea_documento.comision is
    'Importe ya aterrizado. dbt no calcula el porcentaje.';
comment on column raw.linea_documento.beneficiario is
    'Beneficiario ya aterrizado. dbt no elige el rol.';

create index if not exists linea_documento_factura_idx
    on raw.linea_documento (snapshot_id, factura_id);

create table if not exists raw.pago (
    snapshot_id text not null,
    pago_id text not null,
    factura_id text,
    fecha_conciliacion date,
    monto numeric,
    moneda text,
    payload_json text,
    primary key (snapshot_id, pago_id)
);

create index if not exists pago_factura_idx
    on raw.pago (snapshot_id, factura_id);

create table if not exists raw.letra (
    snapshot_id text not null,
    letra_id text not null,
    factura_id text,
    estado text,
    monto numeric,
    fecha_pago date,
    payload_json text,
    primary key (snapshot_id, letra_id)
);

create index if not exists letra_factura_idx
    on raw.letra (snapshot_id, factura_id);

-- Deny-by-default. Sin politicas, ningun rol sujeto a RLS ve filas.
do $$
declare
    rel text;
begin
    foreach rel in array array[
        'raw.bronze_snapshot',
        'raw.bronze_record',
        'raw.silver_record',
        'raw.factura',
        'raw.linea_documento',
        'raw.pago',
        'raw.letra',
        'gold.gold_run',
        'gold.gold_commission_line',
        'gold.gold_collected_line',
        'gold.gold_difference',
        'gold.gold_exception'
    ]
    loop
        execute format('alter table %s enable row level security', rel);
        execute format('alter table %s force row level security', rel);
        execute format(
            'revoke all on table %s from public, anon, authenticated, service_role',
            rel
        );
    end loop;
end $$;
