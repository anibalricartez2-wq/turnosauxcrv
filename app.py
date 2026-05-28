import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta
from fpdf import FPDF
from io import BytesIO

st.set_page_config(page_title="Planificador Pro", layout="wide")

# --- MOTOR ---
class Agente:
    def __init__(self, nombre, lim):
        self.nombre = nombre
        self.lim = lim
        self.horas = 0
        self.conteo = {'M': 0, 'T': 0}
        self.bloqueos = set()
        self.disp_m, self.disp_t = set(range(7)), set(range(7))

    def esta_disponible(self, f, t, grilla):
        if f in self.bloqueos or grilla.get(f, {}).get(t) != 'SIN CUBRIR': return False
        if grilla.get(f, {}).get('M' if t == 'T' else 'T') == self.nombre: return False # Anti-doble turno
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

def exportar_pdf(df):
    pdf = FPDF(orientation='L')
    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    for i, row in df.iterrows():
        pdf.cell(0, 10, f"{i} | M: {row['M']} | T: {row['T']}", ln=True)
    return pdf.output(dest='S').encode('latin1')

# --- UI ---
st.title("🗓️ Planificador Pro")
nombres = ["Sanchez", "Barros", "Garcia", "Ricartez"]
config = {n: {'bloq': st.sidebar.text_input(f"Bloqueos {n}", key=f"b_{n}")} for n in nombres}
limite = st.sidebar.number_input("Límite Horas", 130)

if st.sidebar.button("📊 Calcular"):
    _, dias_mes = calendar.monthrange(2026, 6)
    agentes = {n: Agente(n, limite) for n in nombres}
    grilla = {date(2026, 6, d): {'M': 'SIN CUBRIR', 'T': 'SIN CUBRIR'} for d in range(1, dias_mes + 1)}
    
    for d in range(1, dias_mes + 1):
        f = date(2026, 6, d)
        for t in ['M', 'T']:
            # Pacing: si ya cubrimos mucho, dejar SIN CUBRIR
            cands = [a for a in agentes.values() if a.esta_disponible(f, t, grilla)]
            if cands:
                cands.sort(key=lambda x: (x.horas, x.conteo[t]))
                if cands[0].horas < limite * 0.9: # Estrategia de distribución
                    el = cands[0]
                    grilla[f][t] = el.nombre
                    el.horas += 9
                    el.conteo[t] += 1
    
    st.session_state.update({"grilla": pd.DataFrame(grilla).T, "calculado": True})

if st.session_state["calculado"]:
    df = st.session_state["grilla"]
    st.table(df)
    tipo = st.radio("Formato", ["Excel", "PDF"])
    if tipo == "Excel":
        st.download_button("📥 Descargar", exportar_excel(df), "turnos.xlsx", "application/vnd.ms-excel")
    else:
        st.download_button("📥 Descargar", exportar_pdf(df), "turnos.pdf", "application/pdf")
