-- Vista de staging. No prorratea el pago ni calcula comisión.
select
    snapshot_id || '|' || pago_id as clave,
    snapshot_id,
    pago_id,
    factura_id,
    fecha_conciliacion,
    monto,
    moneda
from {{ source('raw', 'pago') }}
