-- Vista de staging. comision y beneficiario ya están en raw.
select
    snapshot_id || '|' || linea_id as clave,
    snapshot_id,
    linea_id,
    factura_id,
    canal,
    cuenta,
    producto,
    subtotal,
    comision,
    beneficiario
from {{ source('raw', 'linea_documento') }}
