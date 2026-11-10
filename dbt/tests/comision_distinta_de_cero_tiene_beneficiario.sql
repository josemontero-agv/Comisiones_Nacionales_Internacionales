-- Falla si una comisión distinta de cero no trae beneficiario.
-- No calcula el importe: solo revisa lo ya aterrizado.
select
    clave
from {{ ref('stg_linea_documento') }}
where coalesce(comision, 0) <> 0
  and nullif(btrim(beneficiario), '') is null
