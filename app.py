import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta
from fpdf import FPDF

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Planificador de Turnos", layout="wide")

if "calculado" not in st.session_state:
    st.session_state["calculado"] = False
    st.session_state["grilla"] = {}
    st.session_state["resumen_h"] = {}

# --- MOTOR ---
class Agente:
    def __init__(self, nombre):
        self.nombre = nombre
        self.horas = 0
        self.conteo = {'M': 0, 'T': 0}
        self.bloqueos = set()

    def esta_disponible(self, f, t, grilla):
        if f in self.bloqueos: return False
        if grilla[f].get(t) == self.nombre: return False
        return self.horas + 9 <= 130

# --- PDF ---
def generar_pdf(grilla, resumen_h):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Cronograma Mensual", ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    for f, t in sorted(grilla.items()):
        pdf.cell(0, 7, f"{f}: Manana: {t['M']} | Tarde: {t['T']}", ln=True)
    return bytes(pdf.output())

# --- UI ---
st.title("🗓️ Planificador de Turnos")
nombres = ["Sanchez", "Barros", "Garcia", "Ricartez"]
config = {}

st.sidebar.header("⚙️ Configuración")
anio = st.sidebar.number_input("Año", 2024, 2030, 2026)
mes = st.sidebar.slider("Mes", 1, 12, 6)

for nom in nombres:
    with st.sidebar.expander(f"Agente: {nom}"):
        b_sueltos = st.text_input(f"Bloqueos (ej: 1, 15)", key=f"b_{nom}")
        config[nom] = b_sueltos

if st.sidebar.button("📊 Calcular Turnos"):
    agentes = {n: Agente(n) for n in nombres}
    for nom, val in config.items():
        if val:
            for d in val.split(','):
                agentes[nom].bloqueos.add(date(anio, mes, int(d.strip())))
    
    _, dias_mes = calendar.monthrange(anio, mes)
    grilla = {date(anio, mes, d): {'M': '---', 'T': '---'} for d in range(1, dias_mes + 1)}
    
    for d in range(1, dias_mes + 1):
        f = date(anio, mes, d)
        for t in ['M', 'T']:
            cands = [a for a in agentes.values() if a.esta_disponible(f, t, grilla)]
            if cands:
                cands.sort(key=lambda x: (x.horas, x.conteo[t]))
                el = cands[0]
                grilla[f][t] = el.nombre
                el.horas += 9
                el.conteo[t] += 1
    
    st.session_state.update({"grilla": grilla, "resumen_h": {n: a.horas for n, a in agentes.items()}, "calculado": True})

if st.session_state["calculado"]:
    st.table(pd.DataFrame(st.session_state["grilla"]).T)
    st.download_button("📥 Descargar PDF", data=generar_pdf(st.session_state["grilla"], st.session_state["resumen_h"]), file_name="cronograma.pdf", mime="application/pdf")
