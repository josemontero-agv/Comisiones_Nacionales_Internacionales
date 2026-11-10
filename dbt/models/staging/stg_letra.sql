-- Vista de staging. No decide si la letra comisiona.
select
    snapshot_id || '|' || letra_id as clave,
    snapshot_id,
    letra_id,
    factura_id,
    estado,
    monto,
    fecha_pago
from {{ source('raw', 'letra') }}
