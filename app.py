import streamlit as st
import pandas as pd
import calendar
from datetime import date
from fpdf import FPDF
from io import BytesIO

st.set_page_config(page_title="Planificador SMN", layout="wide")

class Agente:
    def __init__(self, nombre, lim):
        self.nombre = nombre
        self.lim = lim
        self.horas = 0
        self.conteo = {'M': 0, 'T': 0}
        self.pref_m, self.pref_t = set(), set()
        self.disp_m, self.disp_t = set(range(7)), set(range(7))

    def configurar(self, d_m, d_t, p_m, p_t):
        mapa = {"Lu":0, "Ma":1, "Mi":2, "Ju":3, "Vi":4, "Sá":5, "Do":6}
        self.disp_m = {mapa[d] for d in d_m}
        self.disp_t = {mapa[d] for d in d_t}
        self.pref_m = {int(d) for d in p_m}
        self.pref_t = {int(d) for d in p_t}

def generar_pdf(df, resumen, mes, anio):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"Cronograma {calendar.month_name[mes]} {anio}", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "", 8)
    for i, row in df.iterrows():
        pdf.cell(45, 7, f"{i.day}/{i.month}", 1)
        pdf.cell(45, 7, str(row['Dia']), 1)
        pdf.cell(45, 7, str(row['M']), 1)
        pdf.cell(45, 7, str(row['T']), 1, ln=True)
    
    # Agregar tabla de resumen al PDF
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Resumen de Turnos Asignados", ln=True, align="C")
    pdf.ln(5)
    pdf.set_font("Arial", "B", 10)
    for col in ["Agente", "Turnos M", "Turnos T"]: pdf.cell(45, 7, col, 1)
    pdf.ln()
    pdf.set_font("Arial", "", 10)
    for n, row in resumen.iterrows():
        pdf.cell(45, 7, str(n), 1)
        pdf.cell(45, 7, str(int(row['Turnos M'])), 1)
        pdf.cell(45, 7, str(int(row['Turnos T'])), 1, ln=True)
        
    buffer = BytesIO()
    buffer.write(pdf.output())
    buffer.seek(0)
    return buffer

st.title("🗓️ Planificador de Turnos SMN")
fecha_sel = st.date_input("Seleccionar mes", date(2026, 6, 1))
mes, anio = fecha_sel.month, fecha_sel.year

st.sidebar.header("⚙️ Configuración Agentes")
limite = st.sidebar.number_input("Límite Horas", value=130)
nombres = ["Sanchez", "Barros", "Garcia", "Ricartez"]
config = {}

for nom in nombres:
    with st.sidebar.expander(f"Agente: {nom}"):
        config[nom] = {
            'dm': st.multiselect("Mañana", ["Lu","Ma","Mi","Ju","Vi","Sá","Do"], default=["Lu","Ma","Mi","Ju","Vi"], key=f"m_{nom}"),
            'dt': st.multiselect("Tarde", ["Lu","Ma","Mi","Ju","Vi","Sá","Do"], default=["Lu","Ma","Mi","Ju","Vi"], key=f"t_{nom}"),
            'pm': st.multiselect("Pref. M", list(range(1, 32)), key=f"pm_{nom}"),
            'pt': st.multiselect("Pref. T", list(range(1, 32)), key=f"pt_{nom}")
        }

if st.sidebar.button("📊 Calcular"):
    agentes = {n: Agente(n, limite) for n in nombres}
    for n, c in config.items(): agentes[n].configurar(c['dm'], c['dt'], c['pm'], c['pt'])
    
    dias_tot = calendar.monthrange(anio, mes)[1]
    grilla = {date(anio, mes, d): {'Dia': ["Lu","Ma","Mi","Ju","Vi","Sá","Do"][date(anio, mes, d).weekday()], 'M': 'SIN CUBRIR', 'T': 'SIN CUBRIR'} for d in range(1, dias_tot + 1)}
    
    for d in range(1, dias_tot + 1):
        f = date(anio, mes, d)
        for t in ['M', 'T']:
            cands = [a for a in agentes.values() if a.horas + 9 <= a.lim]
            if cands:
                cands.sort(key=lambda x: (0 if (t=='M' and d in x.pref_m) or (t=='T' and d in x.pref_t) else 1, x.horas))
                el = cands[0]
                grilla[f][t] = el.nombre
                el.horas += 9
                el.conteo[t] += 1
    
    # Crear resumen para mostrar y exportar
    df_resumen = pd.DataFrame({n: {'Turnos M': a.conteo['M'], 'Turnos T': a.conteo['T']} for n, a in agentes.items()}).T
    st.session_state.update({"grilla": pd.DataFrame(grilla).T, "resumen": df_resumen, "calculado": True})
    st.rerun()

if st.session_state.get("calculado"):
    st.table(st.session_state.grilla)
    st.subheader("📊 Cantidad de Turnos por Agente")
    st.table(st.session_state.resumen)
    st.download_button("📥 Descargar PDF", data=generar_pdf(st.session_state.grilla, st.session_state.resumen, mes, anio), file_name="cronograma.pdf", mime="application/pdf")
