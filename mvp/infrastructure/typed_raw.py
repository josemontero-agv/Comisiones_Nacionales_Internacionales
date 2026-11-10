"""Proyecta Bronze/Gold ya guardados a las tablas tipadas que lee dbt.

No calcula porcentajes ni elige roles. La comisión y el beneficiario se copian
del Gold ya persistido.
"""

from __future__ import annotations

from mvp.infrastructure.postgres.repository import PostgresMedallionRepository


def project_typed_raw(repository: PostgresMedallionRepository) -> dict[str, int]:
    with repository.connect() as connection:
        for table in ("factura", "linea_documento", "pago", "letra"):
            connection.execute(f"DELETE FROM raw.{table}")
        connection.execute(_SQL_FACTURA_SILVER)
        connection.execute(_SQL_LINEA_SILVER)
        connection.execute(_SQL_PAGO_SILVER)
        connection.execute(_SQL_FACTURA_GOLD)
        connection.execute(_SQL_LINEA_GOLD)
        connection.execute(_SQL_PAGO_GOLD)
        connection.execute(_SQL_LETRA_GOLD)
        counts = {}
        for table in ("factura", "linea_documento", "pago", "letra"):
            row = connection.execute(f"SELECT COUNT(*) AS n FROM raw.{table}").fetchone()
            counts[table] = int(row["n"] if row else 0)
    return counts


_SQL_FACTURA_SILVER = """
INSERT INTO raw.factura (
    snapshot_id, factura_id, canal, documento, fecha, moneda,
    partner_id, pais_iso, move_type, payload_json
)
SELECT
    snapshot_id,
    payload_json::jsonb->>'doc_key',
    NULLIF(payload_json::jsonb->>'channel', ''),
    payload_json::jsonb->>'doc_key',
    NULLIF(payload_json::jsonb->>'invoice_date', '')::date,
    NULLIF(payload_json::jsonb->>'currency', ''),
    NULLIF(payload_json::jsonb->>'partner_ref', ''),
    NULLIF(payload_json::jsonb->>'country_code', ''),
    NULLIF(payload_json::jsonb->>'move_type', ''),
    payload_json
FROM raw.silver_record
WHERE entity_type = 'document'
  AND COALESCE(payload_json::jsonb->>'doc_key', '') <> ''
ON CONFLICT (snapshot_id, factura_id) DO NOTHING
"""

_SQL_LINEA_SILVER = """
INSERT INTO raw.linea_documento (
    snapshot_id, linea_id, factura_id, canal, cuenta, producto,
    subtotal, comision, beneficiario, payload_json
)
SELECT
    silver.snapshot_id,
    silver.payload_json::jsonb->>'line_key',
    silver.payload_json::jsonb->>'doc_key',
    factura.canal,
    NULLIF(silver.payload_json::jsonb->>'account_code', ''),
    NULLIF(silver.payload_json::jsonb->>'product_code', ''),
    NULLIF(silver.payload_json::jsonb->>'price_subtotal', '')::numeric,
    NULL,
    NULL,
    silver.payload_json
FROM raw.silver_record AS silver
LEFT JOIN raw.factura AS factura
  ON factura.snapshot_id = silver.snapshot_id
 AND factura.factura_id = silver.payload_json::jsonb->>'doc_key'
WHERE silver.entity_type = 'document_line'
  AND COALESCE(silver.payload_json::jsonb->>'line_key', '') <> ''
ON CONFLICT (snapshot_id, linea_id) DO NOTHING
"""

_SQL_PAGO_SILVER = """
INSERT INTO raw.pago (
    snapshot_id, pago_id, factura_id, fecha_conciliacion, monto, moneda, payload_json
)
SELECT
    snapshot_id,
    payload_json::jsonb->>'allocation_key',
    NULLIF(payload_json::jsonb->>'doc_key', ''),
    NULLIF(payload_json::jsonb->>'payment_date', '')::date,
    NULLIF(payload_json::jsonb->>'amount', '')::numeric,
    NULL,
    payload_json
FROM raw.silver_record
WHERE entity_type = 'payment_allocation'
  AND COALESCE(payload_json::jsonb->>'allocation_key', '') <> ''
ON CONFLICT (snapshot_id, pago_id) DO NOTHING
"""

_SQL_FACTURA_GOLD = """
INSERT INTO raw.factura (
    snapshot_id, factura_id, canal, documento, moneda, payload_json
)
SELECT DISTINCT ON (run.snapshot_id, line.payload_json::jsonb->>'document')
    run.snapshot_id,
    line.payload_json::jsonb->>'document',
    NULLIF(line.payload_json::jsonb->>'channel', ''),
    line.payload_json::jsonb->>'document',
    NULLIF(line.payload_json::jsonb->>'currency', ''),
    line.payload_json
FROM gold.gold_commission_line AS line
JOIN gold.gold_run AS run ON run.run_id = line.run_id
WHERE COALESCE(line.payload_json::jsonb->>'document', '') <> ''
ORDER BY
    run.snapshot_id,
    line.payload_json::jsonb->>'document',
    run.completed_at DESC
ON CONFLICT (snapshot_id, factura_id) DO NOTHING
"""

_SQL_LINEA_GOLD = """
INSERT INTO raw.linea_documento (
    snapshot_id, linea_id, factura_id, canal, subtotal, comision, beneficiario, payload_json
)
SELECT DISTINCT ON (run.snapshot_id, line.row_key)
    run.snapshot_id,
    line.row_key,
    NULLIF(line.payload_json::jsonb->>'document', ''),
    NULLIF(line.payload_json::jsonb->>'channel', ''),
    NULLIF(line.payload_json::jsonb->>'base_raw', '')::numeric,
    NULLIF(line.payload_json::jsonb->>'commission_presented', '')::numeric,
    NULLIF(line.payload_json::jsonb->>'person', ''),
    line.payload_json
FROM gold.gold_commission_line AS line
JOIN gold.gold_run AS run ON run.run_id = line.run_id
ORDER BY run.snapshot_id, line.row_key, run.completed_at DESC
ON CONFLICT (snapshot_id, linea_id) DO UPDATE
SET comision = EXCLUDED.comision,
    beneficiario = EXCLUDED.beneficiario
"""

_SQL_PAGO_GOLD = """
INSERT INTO raw.pago (
    snapshot_id, pago_id, factura_id, monto, moneda, payload_json
)
SELECT DISTINCT ON (run.snapshot_id, line.row_key)
    run.snapshot_id,
    line.row_key,
    NULLIF(line.payload_json::jsonb->>'document', ''),
    NULLIF(line.payload_json::jsonb->>'collected_presented', '')::numeric,
    NULLIF(line.payload_json::jsonb->>'currency', ''),
    line.payload_json
FROM gold.gold_collected_line AS line
JOIN gold.gold_run AS run ON run.run_id = line.run_id
WHERE COALESCE(line.payload_json::jsonb->>'category', '') <> 'LETRAS'
ORDER BY run.snapshot_id, line.row_key, run.completed_at DESC
ON CONFLICT (snapshot_id, pago_id) DO NOTHING
"""

_SQL_LETRA_GOLD = """
INSERT INTO raw.letra (
    snapshot_id, letra_id, factura_id, estado, monto, payload_json
)
SELECT DISTINCT ON (run.snapshot_id, line.row_key)
    run.snapshot_id,
    line.row_key,
    NULLIF(line.payload_json::jsonb->>'document', ''),
    'gold',
    NULLIF(line.payload_json::jsonb->>'commission_presented', '')::numeric,
    line.payload_json
FROM gold.gold_commission_line AS line
JOIN gold.gold_run AS run ON run.run_id = line.run_id
WHERE line.payload_json::jsonb->>'category' = 'LETRAS'
ORDER BY run.snapshot_id, line.row_key, run.completed_at DESC
ON CONFLICT (snapshot_id, letra_id) DO NOTHING
"""
