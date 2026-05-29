import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta
from fpdf import FPDF
from io import BytesIO

st.set_page_config(page_title="Planificador Pro", layout="wide")

# --- INICIALIZACIÓN ---
if "calculado" not in st.session_state:
    st.session_state.update({"calculado": False, "grilla": None, "resumen": None})

# --- MOTOR ---
class Agente:
    def __init__(self, nombre, lim):
        self.nombre = nombre
        self.lim = lim
        self.horas = 0
        self.conteo = {'M': 0, 'T': 0}
        self.bloqueos = set()
        self.disp_m, self.disp_t = set(range(7)), set(range(7))

    def configurar(self, d_m, d_t):
        mapa = {"Lu":0, "Ma":1, "Mi":2, "Ju":3, "Vi":4, "Sá":5, "Do":6}
        self.disp_m = {mapa[d] for d in d_m}
        self.disp_t = {mapa[d] for d in d_t}

    def esta_disponible(self, f, t, grilla):
        if f in self.bloqueos or grilla.get(f, {}).get(t) != 'SIN CUBRIR': return False
        if grilla.get(f, {}).get('M' if t == 'T' else 'T') == self.nombre: return False
        if self.horas + 9 > self.lim: return False
        cons = 0
        for i in range(1, 4):
            prev = f - timedelta(days=i)
            if grilla.get(prev, {}).get('M') == self.nombre or grilla.get(prev, {}).get('T') == self.nombre: cons += 1
        return cons < 3

# --- PDF AVANZADO ---
def generar_pdf(df, resumen, limite):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Cronograma Mensual (Limite: " + str(limite) + " hs)", ln=True, align="C")
    pdf.ln(5)
    # Tabla Grilla
    pdf.set_font("Arial", "B", 8)
    for col in ["Fecha", "Manana", "Tarde"]: pdf.cell(60, 7, col, 1, 0, 'C')
    pdf.ln()
    pdf.set_font("Arial", "", 8)
    for i, row in df.iterrows():
        pdf.cell(60, 7, str(i), 1)
        pdf.cell(60, 7, row['M'], 1)
        pdf.cell(60, 7, row['T'], 1, ln=True)
    # Tabla Resumen
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Detalle de Turnos por Agente", ln=True)
    pdf.set_font("Arial", "B", 10)
    for col in ["Agente", "Horas", "Turnos M", "Turnos T"]: pdf.cell(45, 7, col, 1)
    pdf.ln()
    pdf.set_font("Arial", "", 10)
    for n, row in resumen.iterrows():
        pdf.cell(45, 7, n, 1)
        pdf.cell(45, 7, str(row['Horas']), 1)
        pdf.cell(45, 7, str(row['Turnos M']), 1)
        pdf.cell(45, 7, str(row['Turnos T']), 1, ln=True)
        
    buffer = BytesIO()
    buffer.write(pdf.output(dest='S').encode('latin1') if isinstance(pdf.output(dest='S'), str) else pdf.output(dest='S'))
    buffer.seek(0)
    return buffer

# --- UI ---
st.title("🗓️ Planificador de Turnos Pro")
nombres = ["Sanchez", "Barros", "Garcia", "Ricartez"]
lista_dias = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"]
config = {}

st.sidebar.header("⚙️ Configuración")
limite = st.sidebar.number_input("Límite Horas Mensuales", min_value=80, max_value=200, value=130)

for nom in nombres:
    with st.sidebar.expander(f"Agente: {nom}"):
        config[nom] = {
            'dm': st.multiselect("Mañana", lista_dias, default=lista_dias, key=f"m_{nom}"),
            'dt': st.multiselect("Tarde", lista_dias, default=lista_dias, key=f"t_{nom}"),
            'bloq': st.text_input("Bloqueos (ej: 1, 15)", key=f"b_{nom}")
        }

if st.sidebar.button("📊 Calcular Turnos"):
    agentes = {n: Agente(n, limite) for n in nombres}
    for n, c in config.items():
        agentes[n].configurar(c['dm'], c['dt'])
        if c['bloq']:
            for d in c['bloq'].split(','): agentes[n].bloqueos.add(date(2026, 6, int(d.strip())))
    
    grilla = {date(2026, 6, d): {'M': 'SIN CUBRIR', 'T': 'SIN CUBRIR'} for d in range(1, 31)}
    for d in range(1, 31):
        f = date(2026, 6, d)
        for t in ['M', 'T']:
            cand = [a for a in agentes.values() if a.esta_disponible(f, t, grilla)]
            if cand:
                cand.sort(key=lambda x: (x.horas, x.conteo[t]))
                el = cand[0]
                grilla[f][t] = el.nombre
                el.horas += 9
                el.conteo[t] += 1
    
    st.session_state.update({
        "grilla": pd.DataFrame(grilla).T, 
        "resumen": pd.DataFrame({n: {'Horas': a.horas, 'Turnos M': a.conteo['M'], 'Turnos T': a.conteo['T']} for n, a in agentes.items()}).T,
        "calculado": True
    })
    st.rerun()

if st.session_state.get("calculado"):
    st.subheader("📋 Grilla de Turnos")
    st.table(st.session_state["grilla"])
    st.subheader("📊 Resumen por Agente")
    st.table(st.session_state["resumen"])
    st.download_button("📥 Descargar PDF", data=generar_pdf(st.session_state["grilla"], st.session_state["resumen"], limite), file_name="cronograma.pdf", mime="application/pdf")
