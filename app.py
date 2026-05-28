import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta
from fpdf import FPDF

# --- SESIÓN ---
if "calculado" not in st.session_state:
    st.session_state["calculado"] = False
    st.session_state["grilla_resultados"] = {}
    st.session_state["resumen_horas"] = {}
    st.session_state["resumen_turnos"] = {}

# --- LOGIN ---
def check_password():
    def password_entered():
        u = st.session_state["username"]
        p = st.session_state["password"]
        if "credenciales" in st.secrets:
            if u in st.secrets["credenciales"]:
                if st.secrets["credenciales"][u] == p:
                    st.session_state["password_correct"] = True
                    st.session_state["usuario_actual"] = u
                    del st.session_state["password"]
                    return
        st.session_state["password_correct"] = False
    if st.session_state.get("password_correct", False): return True
    st.title("🔒 Acceso Restringido")
    st.text_input("Usuario", key="username")
    st.text_input("Contraseña", type="password", key="password")
    st.button("Ingresar", on_click=password_entered)
    return False

# --- MOTOR ---
class Agente:
    def __init__(self, nombre, lim=130):
        self.nombre = nombre
        self.lim = lim
        self.horas = 0
        self.bloq = set()
        self.conteo = {'M': 0, 'T': 0}
        self.disp_m = set()
        self.disp_t = set()

    def configurar(self, d_m, d_t):
        mapa = {"Lu":0, "Ma":1, "Mi":2, "Ju":3, "Vi":4, "Sá":5, "Do":6}
        self.disp_m = {mapa[d] for d in d_m}
        self.disp_t = {mapa[d] for d in d_t}

    def esta_disponible(self, f, t, grilla):
        if f in self.bloq or grilla[f]['M'] == self.nombre or grilla[f]['T'] == self.nombre: return False
        ds = f.weekday()
        if t == 'M' and ds not in self.disp_m: return False
        if t == 'T' and ds not in self.disp_t: return False
        if self.horas + 9 > self.lim: return False
        cons = 0
        for i in range(1, 4):
            prev = f - timedelta(days=i)
            if prev in grilla and (grilla[prev]['M'] == self.nombre or grilla[previo]['T'] == self.nombre): cons += 1
            else: break
        return cons < 3

# --- PDF ---
def generar_pdf(grilla, res_h, res_t, anio, mes, auditor):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"CRONOGRAMA {mes}/{anio}", ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    for f, t in sorted(grilla.items()):
        linea = f"{f.strftime('%Y-%m-%d')} | M: {t['M']} | T: {t['T']}"
        pdf.cell(0, 7, linea, ln=True)
    pdf.cell(0, 10, f"Auditor: {auditor}", ln=True)
    return bytes(pdf.output())

# --- UI ---
st.set_page_config(layout="wide")
if not check_password(): st.stop()
st.title("🗓️ Planificador")
anio = st.sidebar.number_input("Año", 2024, 2030, 2026)
mes = st.sidebar.slider("Mes", 1, 12, 6)
limite = st.sidebar.number_input("Límite Horas", 130)

if st.button("📊 Calcular"):
    _, total_d = calendar.monthrange(anio, mes)
    agentes = {n: Agente(n, limite) for n in ["Sanchez", "Barros", "Garcia", "Ricartez"]}
    grilla = {date(anio, mes, d): {'M': 'SIN CUBRIR', 'T': 'SIN CUBRIR'} for d in range(1, total_d + 1)}
    for d in range(1, total_d + 1):
        f = date(anio, mes, d)
        for t in ['M', 'T']:
            cand = [a for a in agentes.values() if a.esta_disponible(f, t, grilla)]
            if cand:
                cand.sort(key=lambda x: (x.horas, x.conteo[t]))
                el = cand[0]
                grilla[f][t] = el.nombre
                el.horas += 9
                el.conteo[t] += 1
    st.session_state.update({"grilla": grilla, "calculado": True})

if st.session_state["calculado"]:
    st.dataframe(pd.DataFrame(st.session_state["grilla"]).T)
