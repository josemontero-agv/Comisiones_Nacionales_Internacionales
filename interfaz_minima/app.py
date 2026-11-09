"""Interfaz local del piloto; consume exclusivamente contratos Gold."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from mvp.export import export_rrhh_workbook
from mvp.historical import run_historical_parity
from mvp.infrastructure.sqlite import MedallionRepository

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "var/commission-pilot.sqlite3"
EXPORTS = {
    "nacional": ROOT / "entrega_rrhh/comisiones_nacional_septiembre_2026.xlsx",
    "internacional": (
        ROOT / "entrega_rrhh/comisiones_internacional_septiembre_2026.xlsx"
    ),
}

st.set_page_config(page_title="Comisiones AGV — Piloto", layout="wide")
st.title("Comisiones Nacional e Internacional")
st.warning(
    "Piloto no pagable: faltan 1–2 cierres adicionales por canal y existen reglas/catálogos "
    "que requieren aprobación."
)

channel = st.selectbox("Canal", ("nacional", "internacional"))
if st.button("Ejecutar paridad de septiembre", type="primary"):
    with st.spinner("Calculando y comparando..."):
        result = run_historical_parity(channel, DATABASE)
    st.session_state["run_id"] = result.run_id

repository = MedallionRepository(DATABASE)
manifests = repository.latest_manifests()
selected = next((item for item in manifests if item["channel"] == channel), None)

if selected is None:
    st.info("Ejecute la paridad del canal para generar Gold.")
else:
    payload = repository.load_result_payload(str(selected["run_id"]))
    columns = st.columns(4)
    columns[0].metric("Estado", str(selected["status"]))
    columns[1].metric(
        "Esperado", f"{selected['currency']} {selected['expected_total']}"
    )
    columns[2].metric("Calculado", f"{selected['currency']} {selected['actual_total']}")
    columns[3].metric("Diferencias", int(selected["difference_count"]))

    detail_tab, differences_tab, exceptions_tab, manifest_tab = st.tabs(
        ("Detalle Gold", "Diferencias", "Excepciones", "Manifest")
    )
    with detail_tab:
        st.dataframe(payload["rows"], width="stretch")
    with differences_tab:
        st.dataframe(payload["differences"], width="stretch")
    with exceptions_tab:
        st.dataframe(payload["exceptions"], width="stretch")
    with manifest_tab:
        st.code(json.dumps(selected, ensure_ascii=False, indent=2), language="json")

if selected is not None:
    export_path = EXPORTS[channel]
    export_rrhh_workbook(DATABASE, export_path, channel)
    st.download_button(
        f"Descargar Excel {channel.title()}",
        data=export_path.read_bytes(),
        file_name=export_path.name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
