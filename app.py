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
        self.disp_m = set(range(7))
        self.disp_t = set(range(7))

    def configurar(self, d_m, d_t):
        mapa = {"Lu":0, "Ma":1, "Mi":2, "Ju":3, "Vi":4, "Sá":5, "Do":6}
        self.disp_m = {mapa[d] for d in d_m}
        self.disp_t = {mapa[d] for d in d_t}

    def esta_disponible(self, f, t, grilla):
        if f in self.bloqueos: return False
        if grilla.get(f, {}).get(t) == self.nombre: return False
        ds = f.weekday()
        if t == 'M' and ds not in self.disp_m: return False
        if t == 'T' and ds not in self.disp_t: return False
        return self.horas + 9 <= 130

# --- PDF ---
def generar_pdf(grilla):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Cronograma Mensual", ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    for f, t in sorted(grilla.items()):
        pdf.cell(0, 7, f"{f}: M: {t['M']} | T: {t['T']}", ln=True)
    return bytes(pdf.output())

# --- UI ---
st.title("🗓️ Planificador de Turnos")
nombres = ["Sanchez", "Barros", "Garcia", "Ricartez"]
lista_dias = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"]
config = {}

st.sidebar.header("⚙️ Configuración Agentes")
anio = st.sidebar.number_input("Año", 2024, 2030, 2026)
mes = st.sidebar.slider("Mes", 1, 12, 6)

for nom in nombres:
    with st.sidebar.expander(f"Agente: {nom}"):
        d_m = st.multiselect(f"Mañana", lista_dias, default=lista_dias, key=f"m_{nom}")
        d_t = st.multiselect(f"Tarde", lista_dias, default=lista_dias, key=f"t_{nom}")
        bloq = st.text_input(f"Días a bloquear (ej: 1, 15)", key=f"b_{nom}")
        config[nom] = {'dm': d_m, 'dt': d_t, 'bloq': bloq}

if st.sidebar.button("📊 Calcular Turnos"):
    agentes = {n: Agente(n) for n in nombres}
    for nom, cfg in config.items():
        agentes[nom].configurar(cfg['dm'], cfg['dt'])
        if cfg['bloq']:
            for d in cfg['bloq'].split(','):
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
    
    st.session_state.update({"grilla": grilla, "calculado": True})

if st.session_state["calculado"]:
    st.table(pd.DataFrame(st.session_state["grilla"]).T)
    st.download_button("📥 Descargar PDF", data=generar_pdf(st.session_state["grilla"]), file_name="cronograma.pdf", mime="application/pdf")
