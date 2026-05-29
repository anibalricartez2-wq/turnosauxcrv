import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta
from fpdf import FPDF
from io import BytesIO

st.set_page_config(page_title="Planificador Pro", layout="wide")

if "calculado" not in st.session_state:
    st.session_state.update({"calculado": False, "grilla": None, "resumen": None})

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

# --- PDF CORREGIDO (USANDO BYTESIO) ---
def generar_pdf(df, resumen, limite, mes, anio):
    pdf = FPDF()
    pdf.add_page()
    try: pdf.image('logo_smn.png', 10, 8, 20)
    except: pass
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"Cronograma {mes}/{anio}", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "B", 8)
    for col in ["Fecha", "Dia", "Manana", "Tarde"]: pdf.cell(45, 7, col, 1, 0, 'C')
    pdf.ln()
    pdf.set_font("Arial", "", 8)
    for i, row in df.iterrows():
        pdf.cell(45, 7, str(i), 1)
        pdf.cell(45, 7, str(row['Dia']), 1)
        pdf.cell(45, 7, str(row['M']), 1)
        pdf.cell(45, 7, str(row['T']), 1, ln=True)
    
    # FORZAR SALIDA A BYTES
    buffer = BytesIO()
    pdf.output(dest='F', name=buffer) # O usa la lógica de abajo si la versión es muy nueva
    # Si da error en la línea anterior, usa esto:
    buffer.write(pdf.output()) 
    buffer.seek(0)
    return buffer

# --- UI ---
st.title("🗓️ Planificador de Turnos SMN")
nombres = ["Sanchez", "Barros", "Garcia", "Ricartez"]
lista_dias = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"]
config = {}

st.sidebar.header("⚙️ Configuración")
anio = st.sidebar.number_input("Año", 2024, 2030, 2026)
mes = st.sidebar.slider("Mes", 1, 12, 6)
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
            for d in c['bloq'].split(','): agentes[n].bloqueos.add(date(anio, mes, int(d.strip())))
    
    _, dias_mes = calendar.monthrange(anio, mes)
    grilla = {}
    for d in range(1, dias_mes + 1):
        f = date(anio, mes, d)
        grilla[f] = {'Dia': lista_dias[f.weekday()], 'M': 'SIN CUBRIR', 'T': 'SIN CUBRIR'}
        
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
    
    st.session_state.update({
        "grilla": pd.DataFrame(grilla).T, 
        "resumen": pd.DataFrame({n: {'Horas': a.horas, 'Turnos M': a.conteo['M'], 'Turnos T': a.conteo['T']} for n, a in agentes.items()}).T,
        "calculado": True
    })
    st.rerun()

if st.session_state.get("calculado"):
    st.table(st.session_state["grilla"])
    st.table(st.session_state["resumen"])
    st.download_button("📥 Descargar PDF", data=generar_pdf(st.session_state["grilla"], st.session_state["resumen"], limite, mes, anio), file_name="cronograma.pdf", mime="application/pdf")
