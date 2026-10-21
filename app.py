"""Panel local JobHunter CL. Ejecutar con: streamlit run app.py"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
import json
import streamlit as st
from jobhunter.config import load_profile, save_profile
from jobhunter.collect import fetch_all
from jobhunter.matching import evaluate
from jobhunter.storage import (connection, list_jobs, upsert_jobs, set_status,
                               set_notes, STATUSES, get_setting, set_setting,
                               export_backup, import_backup, get_backup_profile)

st.set_page_config(page_title="JobHunter CL", page_icon="🔎", layout="wide")
st.title("JobHunter CL")
st.caption("Buscador y organizador personal de postulaciones. Las postulaciones no se envían automáticamente en esta versión.")

db = connection()
try:
    profile = load_profile()
except (OSError, ValueError, json.JSONDecodeError) as exc:
    st.error(f"No se pudo cargar el perfil: {exc}")
    st.stop()

with st.sidebar:
    st.header("Búsqueda")
    st.write("Fuentes: " + ", ".join([x for x, on in [("Get on Board", profile["sources"].get("getonbrd")),
                                                   ("Remotive", profile["sources"].get("remotive"))] if on] +
                     [f"Greenhouse/{s}" for s in profile["sources"].get("greenhouse_boards", [])] +
                     [f"Lever/{s}" for s in profile["sources"].get("lever_sites", [])]))
    last_scan = get_setting(db, "last_scan")
    if last_scan:
        st.caption("Última consulta: " + last_scan[:19].replace("T", " ") + " UTC")
    if st.button("Buscar nuevas ofertas", type="primary", use_container_width=True):
        cooldown = timedelta(hours=6 if profile["sources"].get("remotive") else 0, minutes=30)
        if last_scan and datetime.now(timezone.utc) - datetime.fromisoformat(last_scan) < cooldown:
            st.info("Ya se consultaron las fuentes recientemente. Espera antes de volver a consultar.")
        else:
            with st.spinner("Consultando fuentes públicas..."):
                jobs, errors = fetch_all(profile["sources"])
                if jobs:
                    n = upsert_jobs(db, jobs)
                    st.success(f"{len(jobs)} ofertas leídas, {n} nuevas.")
                    set_setting(db, "last_scan", datetime.now(timezone.utc).isoformat())
                if not jobs and not errors:
                    st.warning("No hay fuentes habilitadas o no se encontraron ofertas.")
                for err in errors:
                    st.warning(err)
    st.divider()
    st.caption("No introduzcas contraseñas laborales ni datos sensibles en este equipo si no está autorizado.")

tab_jobs, tab_tracking, tab_profile = st.tabs(["Ofertas", "Seguimiento", "Perfil y fuentes"])
rows = list_jobs(db)
with tab_jobs:
    if not rows:
        st.info("Todavía no hay ofertas. Usa «Buscar nuevas ofertas». Necesitas conexión a internet.")
    status_filter = st.multiselect("Estado", STATUSES, default=["Nueva", "Revisar"])
    min_score = st.slider("Puntuación mínima", 0, 100, int(profile.get("min_score", 30)))
    keyword = st.text_input("Filtrar por cargo o empresa", "")
    filtered = []
    for job in rows:
        score, matches, warnings = evaluate(job, profile)
        if job["status"] not in status_filter or score < min_score:
            continue
        if keyword.casefold() not in (job["title"] + " " + job["company"]).casefold():
            continue
        filtered.append((score, job, matches, warnings))
    filtered.sort(key=lambda x: (-x[0], x[1]["title"]))
    st.caption(f"{len(filtered)} ofertas visibles de {len(rows)} guardadas. La puntuación es orientativa.")
    for score, job, matches, warnings in filtered[:150]:
        with st.expander(f"{score}/100 · {job['title']} — {job['company']} ({job['status']})"):
            st.write(f"**Fuente:** {job['source']}  |  **Ubicación:** {job['location'] or 'No indicada'}")
            if matches:
                st.success(" · ".join(matches))
            if warnings:
                st.warning(" · ".join(warnings))
            st.write(job["description"][:3500] or "Sin descripción en la fuente; revisar oferta original.")
            st.link_button("Abrir oferta y postular en el portal", job["url"])
            new_status = st.selectbox("Estado", STATUSES, index=STATUSES.index(job["status"]), key="status_"+job["id"])
            if new_status != job["status"]:
                set_status(db, job["id"], new_status)
                st.rerun()
            note = st.text_area("Notas (opcional)", value=job["notes"], key="notes_"+job["id"], height=90)
            if st.button("Guardar nota", key="save_"+job["id"]):
                set_notes(db, job["id"], note)
                st.success("Nota guardada")
with tab_tracking:
    st.subheader("Control de postulaciones")
    cols = st.columns(len(STATUSES))
    for i, status in enumerate(STATUSES):
        cols[i].metric(status, sum(1 for j in rows if j["status"] == status))
    st.dataframe([{"Cargo": j["title"], "Empresa": j["company"], "Fuente": j["source"],
                   "Estado": j["status"], "URL": j["url"]} for j in rows],
                 use_container_width=True, hide_index=True)
    st.subheader("Mover el seguimiento a otro equipo")
    st.caption("GitHub sincroniza el código; el JSON transfiere también el perfil, las ofertas, estados y notas. Contiene datos privados.")
    st.download_button("Descargar respaldo del seguimiento (.json)", export_backup(db, profile),
                       file_name="jobhunter_respaldo.json", mime="application/json")
    uploaded = st.file_uploader("Importar respaldo anterior", type="json", key="backup")
    if uploaded is not None and st.button("Importar respaldo"):
        try:
            backup_data = uploaded.getvalue()
            backup_profile = get_backup_profile(backup_data)
            n = import_backup(db, backup_data)
            if backup_profile is not None:
                save_profile(backup_profile)
            st.success(f"{n} registros importados. El perfil también se restauró si estaba incluido; actualiza la página.")
        except (ValueError, json.JSONDecodeError, TypeError, KeyError) as exc:
            st.error(f"Respaldo inválido: {exc}")
with tab_profile:
    st.subheader("Qué trabajos buscar")
    st.caption("Edita estas listas de forma fiel a tu experiencia real. Un concepto por línea.")
    titles = st.text_area("Cargos objetivo", "\n".join(profile.get("titles", [])), height=170)
    skills = st.text_area("Habilidades reales", "\n".join(profile.get("skills", [])), height=170)
    locations = st.text_area("Ubicaciones y modalidades", "\n".join(profile.get("locations", [])), height=110)
    st.subheader("Fuentes públicas")
    getonbrd_enabled = st.checkbox("Get on Board (Chile/LatAm)", value=profile["sources"].get("getonbrd", True))
    remotive_enabled = st.checkbox("Remotive (remotas, verificar país elegible)", value=profile["sources"].get("remotive", False))
    gh = st.text_input("Greenhouse: identificadores separados por coma", ", ".join(profile["sources"].get("greenhouse_boards", [])))
    lv = st.text_input("Lever: identificadores separados por coma", ", ".join(profile["sources"].get("lever_sites", [])))
    if st.button("Guardar perfil y fuentes", type="primary"):
        profile.update({"titles": [s.strip() for s in titles.splitlines() if s.strip()],
                        "skills": [s.strip() for s in skills.splitlines() if s.strip()],
                        "locations": [s.strip() for s in locations.splitlines() if s.strip()],
                        "sources": {"getonbrd": getonbrd_enabled, "remotive": remotive_enabled,
                                    "greenhouse_boards": [s.strip() for s in gh.split(",") if s.strip()],
                                    "lever_sites": [s.strip() for s in lv.split(",") if s.strip()]}})
        save_profile(profile)
        st.success("Perfil local guardado.")
        st.rerun()
    st.caption("No se almacena un CV ni se ejecutan envíos automáticos. La información permanece en la carpeta data/ local.")
