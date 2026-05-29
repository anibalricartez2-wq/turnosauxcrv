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
        # Regla 3 días seguidos
        cons = 0
        for i in range(1, 4):
            prev = f - timedelta(days=i)
            if grilla.get(prev, {}).get('M') == self.nombre or grilla.get(prev, {}).get('T') == self.nombre: cons += 1
        return cons < 3

# --- EXPORTADORES ---
def exportar_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=True)
    return output.getvalue()

def exportar_pdf(df, resumen):
    pdf = FPDF(orientation='L')
    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Cronograma Mensual", ln=True)
    pdf.set_font("Arial", "", 8)
    for i, row in df.iterrows():
        pdf.cell(0, 7, f"{i} | M: {row['M']} | T: {row['T']}", ln=True)
    pdf.add_page()
    pdf.cell(0, 10, "Resumen de Turnos", ln=True)
    pdf.cell(0, 7, resumen.to_string(), ln=True)
    return pdf.output(dest='S').encode('latin1')

# --- UI ---
st.title("🗓️ Planificador Pro")
nombres = ["Sanchez", "Barros", "Garcia", "Ricartez"]
lista_dias = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"]
config = {}

st.sidebar.header("⚙️ Configuración Agentes")
anio = st.sidebar.number_input("Año", 2024, 2030, 2026)
mes = st.sidebar.slider("Mes", 1, 12, 6)
limite = st.sidebar.number_input("Límite Horas", 130)

for nom in nombres:
    with st.sidebar.expander(f"Agente: {nom}"):
        d_m = st.multiselect("Días Mañana", lista_dias, default=lista_dias, key=f"m_{nom}")
        d_t = st.multiselect("Días Tarde", lista_dias, default=lista_dias, key=f"t_{nom}")
        bloq = st.text_input("Días bloqueo (ej: 1, 15)", key=f"b_{nom}")
        config[nom] = {'dm': d_m, 'dt': d_t, 'bloq': bloq}

if st.sidebar.button("📊 Calcular Turnos"):
    agentes = {n: Agente(n, limite) for n in nombres}
    for n, c in config.items():
        agentes[n].configurar(c['dm'], c['dt'])
        if c['bloq']:
            for d in c['bloq'].split(','):
                agentes[n].bloqueos.add(date(anio, mes, int(d.strip())))
    
    _, dias_mes = calendar.monthrange(anio, mes)
    grilla = {date(anio, mes, d): {'M': 'SIN CUBRIR', 'T': 'SIN CUBRIR'} for d in range(1, dias_mes + 1)}
    
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

if st.session_state.get("calculado", False):
    st.subheader("📋 Grilla")
    st.table(st.session_state["grilla"])
    st.subheader("📊 Resumen")
    st.table(st.session_state["resumen"])
    
    tipo = st.radio("Formato Exportación", ["Excel", "PDF"])
    if tipo == "Excel":
        st.download_button("📥 Descargar", exportar_excel(st.session_state["grilla"]), "turnos.xlsx", "application/vnd.ms-excel")
    else:
        st.download_button("📥 Descargar", exportar_pdf(st.session_state["grilla"], st.session_state["resumen"]), "turnos.pdf", "application/pdf")
