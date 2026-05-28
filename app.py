import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta
from fpdf import FPDF

# --- CONFIGURACIÓN Y ESTADO ---
st.set_page_config(page_title="Planificador Profesional", layout="wide")

if "calculado" not in st.session_state:
    st.session_state.update({"calculado": False, "grilla": {}, "resumen": {}})

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
        if f in self.bloqueos or grilla.get(f, {}).get(t) != '---': return False
        ds = f.weekday()
        if t == 'M' and ds not in self.disp_m: return False
        if t == 'T' and ds not in self.disp_t: return False
        return self.horas + 9 <= 130

# --- PDF PROFESIONAL ---
def generar_pdf(grilla, resumen):
    pdf = FPDF()
    pdf.add_page()
    # Título
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Cronograma Mensual de Servicios", ln=True, align="C")
    pdf.ln(5)
    # Tabla
    pdf.set_font("Arial", "B", 10)
    pdf.set_fill_color(200, 200, 200)
    pdf.cell(40, 8, "Fecha", 1, 0, 'C', 1)
    pdf.cell(50, 8, "Manana (06-15)", 1, 0, 'C', 1)
    pdf.cell(50, 8, "Tarde (15-24)", 1, 1, 'C', 1)
    pdf.set_font("Arial", "", 10)
    for f, t in sorted(grilla.items()):
        pdf.cell(40, 7, str(f), 1)
        pdf.cell(50, 7, t['M'], 1)
        pdf.cell(50, 7, t['T'], 1, 1)
    # Resumen
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Resumen de Carga por Agente", ln=True)
    pdf.set_font("Arial", "", 12)
    for n, d in resumen.items():
        pdf.cell(0, 8, f"Agente: {n} | Horas: {d['H']} | Turnos M: {d['M']} | Turnos T: {d['T']}", ln=True)
    return bytes(pdf.output())

# --- UI ---
st.title("🗓️ Planificador de Turnos")
nombres = ["Sanchez", "Barros", "Garcia", "Ricartez"]
lista_dias = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"]
config = {}

st.sidebar.header("⚙️ Configuración")
anio = st.sidebar.number_input("Año", 2024, 2030, 2026)
mes = st.sidebar.slider("Mes", 1, 12, 6)

for nom in nombres:
    with st.sidebar.expander(f"Agente: {nom}"):
        config[nom] = {'dm': st.multiselect("Mañana", lista_dias, default=lista_dias, key=f"m_{nom}"),
                       'dt': st.multiselect("Tarde", lista_dias, default=lista_dias, key=f"t_{nom}"),
                       'bloq': st.text_input("Días bloqueo (ej: 1, 15)", key=f"b_{nom}")}

if st.sidebar.button("📊 Generar"):
    agentes = {n: Agente(n) for n in nombres}
    for n, c in config.items():
        agentes[n].configurar(c['dm'], c['dt'])
        if c['bloq']:
            for d in c['bloq'].split(','):
                agentes[n].bloqueos.add(date(anio, mes, int(d.strip())))
    
    _, dias_mes = calendar.monthrange(anio, mes)
    grilla = {date(anio, mes, d): {'M': '---', 'T': '---'} for d in range(1, dias_mes + 1)}
    
    for d in range(1, dias_mes + 1):
        f = date(anio, mes, d)
        for t in ['M', 'T']:
            cand = [a for a in agentes.values() if a.esta_disponible(f, t, grilla)]
            if cand:
                cand.sort(key=lambda x: (x.horas, x.conteo[t]))
                el = cand[0]
                grilla[f][t] = el.nombre
                el.horas += 9
                el.conteo[t] += 1
    
    resumen = {n: {'H': a.horas, 'M': a.conteo['M'], 'T': a.conteo['T']} for n, a in agentes.items()}
    st.session_state.update({"grilla": grilla, "resumen": resumen, "calculado": True})

if st.session_state["calculado"]:
    col1, col2 = st.columns([2, 1])
    col1.subheader("📋 Grilla")
    col1.table(pd.DataFrame(st.session_state["grilla"]).T)
    col2.subheader("📊 Métricas")
    col2.table(pd.DataFrame(st.session_state["resumen"]).T)
    st.download_button("📥 Descargar PDF Profesional", data=generar_pdf(st.session_state["grilla"], st.session_state["resumen"]), file_name="cronograma.pdf", mime="application/pdf")
