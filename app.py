import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta
from fpdf import FPDF

# Configuración inicial
st.set_page_config(page_title="Planificador de Turnos", layout="wide")

# Lógica del motor
class Agente:
    def __init__(self, nombre):
        self.nombre = nombre
        self.horas = 0
        self.conteo = {'M': 0, 'T': 0}
        self.bloqueos = set()
        self.disp_m = set(range(7))
        self.disp_t = set(range(7))

    def esta_disponible(self, f, t, grilla):
        if f in self.bloqueos: return False
        if grilla.get(f, {}).get('M') == self.nombre or grilla.get(f, {}).get('T') == self.nombre: return False
        return True

# Interfaz
st.title("🗓️ Planificador de Turnos")

nombres = ["Sanchez", "Barros", "Garcia", "Ricartez"]
config = {}

# Recreación de los menús desaparecidos
st.sidebar.header("⚙️ Configuración")
for nom in nombres:
    with st.sidebar.expander(f"Agente: {nom}"):
        dias_bloq = st.text_input(f"Días a bloquear (ej: 1, 15)", key=f"bloq_{nom}")
        config[nom] = dias_bloq

if st.sidebar.button("Calcular Planificación"):
    mes, anio = 6, 2026
    _, total_dias = calendar.monthrange(anio, mes)
    
    agentes = {n: Agente(n) for n in nombres}
    # Aplicar bloqueos
    for nom, val in config.items():
        if val:
            for d in val.split(','):
                agentes[nom].bloqueos.add(date(anio, mes, int(d.strip())))

    grilla = {date(anio, mes, d): {'M': '---', 'T': '---'} for d in range(1, total_dias + 1)}

    # Motor simple de asignación
    for d in range(1, total_dias + 1):
        f = date(anio, mes, d)
        for t in ['M', 'T']:
            candidatos = [a for a in agentes.values() if a.esta_disponible(f, t, grilla)]
            if candidatos:
                candidatos.sort(key=lambda x: (x.horas, x.conteo[t]))
                elegido = candidatos[0]
                grilla[f][t] = elegido.nombre
                elegido.horas += 9
                elegido.conteo[t] += 1

    st.session_state['data'] = grilla
    st.rerun()

# Visualización
if 'data' in st.session_state:
    df = pd.DataFrame(st.session_state['data']).T
    st.table(df)
else:
    st.info("Configurá los bloqueos en el menú lateral y presioná 'Calcular'.")
