-- Vista de staging. No calcula porcentajes ni roles.
select
    snapshot_id || '|' || factura_id as clave,
    snapshot_id,
    factura_id,
    canal,
    documento,
    fecha,
    moneda,
    partner_id,
    pais_iso,
    move_type
from {{ source('raw', 'factura') }}
