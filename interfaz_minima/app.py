"""Interfaz local del piloto; consume exclusivamente contratos Gold."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from mvp.application.odoo_load import load_september
from mvp.application.reporting import build_collected_by_line, build_commission_pivot
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
period = st.selectbox("Periodo", ("Septiembre 2026",))
if st.button("Ejecutar LOAD Odoo de septiembre", type="primary"):
    with st.spinner("Extrayendo Odoo en solo lectura y calculando Gold..."):
        result = load_september(channel, DATABASE)
    st.session_state["run_id"] = result.run_id
    st.success("LOAD Odoo completado. El periodo continúa marcado como no pagable.")

with st.expander("Validar contra Excel (opcional)"):
    st.caption(
        "Esta comparación crea una corrida separada y no sustituye ni alimenta el cálculo Odoo."
    )
    if st.button("Validar septiembre contra Excel"):
        with st.spinner("Calculando comparación histórica..."):
            validation = run_historical_parity(channel, DATABASE)
        st.session_state["validation_run_id"] = validation.run_id
        st.json(validation.manifest())

repository = MedallionRepository(DATABASE)
manifests = repository.latest_manifests(bronze_origin="odoo")
selected = next((item for item in manifests if item["channel"] == channel), None)

if selected is None:
    st.info("Ejecute el LOAD Odoo del canal para generar Gold.")
else:
    payload = repository.load_result_payload(str(selected["run_id"]))
    columns = st.columns(4)
    columns[0].metric("Estado", str(selected["status"]))
    columns[1].metric("Periodo", period)
    columns[2].metric("Total comisión", f"{selected['currency']} {selected['actual_total']}")
    columns[3].metric("Filas Bronze", int(selected.get("bronze_row_count", 0)))

    pivot_tab, collected_tab, detail_tab, exceptions_tab, manifest_tab = st.tabs(
        (
            "Pivote de comisiones",
            "Cobrado por línea",
            "Detalle Gold",
            "Excepciones",
            "Manifest",
        )
    )
    with pivot_tab:
        st.dataframe(build_commission_pivot([payload]), width="stretch")
    with collected_tab:
        st.dataframe(build_collected_by_line([payload]), width="stretch")
    with detail_tab:
        st.dataframe(payload["rows"], width="stretch")
    with exceptions_tab:
        st.dataframe(payload["exceptions"], width="stretch")
    with manifest_tab:
        st.code(json.dumps(selected, ensure_ascii=False, indent=2), language="json")

if selected is not None:
    requested_path = EXPORTS[channel]
    export_path = export_rrhh_workbook(
        DATABASE, requested_path, channel, bronze_origin="odoo"
    )
    if export_path.resolve() != requested_path.resolve():
        st.warning(
            f"El Excel de entrega está abierto o bloqueado. Se escribió una copia en {export_path}."
        )
    st.download_button(
        f"Descargar Excel {channel.title()}",
        data=export_path.read_bytes(),
        file_name=requested_path.name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
