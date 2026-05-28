import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta
from fpdf import FPDF

# ==========================================
# 1. INITIALIZE SESSION STATE (MEMORIA)
# ==========================================
if "calculado" not in st.session_state:
    st.session_state["calculado"] = False
    st.session_state["grilla_resultados"] = {}
    st.session_state["resumen_horas"] = {}
    st.session_state["resumen_turnos"] = {}

# ==========================================
# 2. SISTEMA DE LOGIN CON SECRETS
# ==========================================
def check_password():
    def password_entered():
        usuario = st.session_state["username"]
        password = st.session_state["password"]
        
        if "credenciales" in st.secrets:
            if usuario in st.secrets["credenciales"]:
                if st.secrets["credenciales"][usuario] == password:
                    st.session_state["password_correct"] = True
                    st.session_state["usuario_actual"] = usuario
                    del st.session_state["password"]
                    return
        st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.title("🔒 Acceso Restringido")
    st.text_input("Usuario", key="username")
    st.text_input("Contraseña", type="password", key="password")
    st.button("Ingresar", on_click=password_entered)

    if st.session_state.get("password_correct") == False:
        st.error("😕 Usuario o contraseña incorrectos.")
    return False

# ==========================================
# 3. LÓGICA DE NEGOCIO (MOTOR DE ASIGNACIÓN)
# ==========================================
class Agente:
    def __init__(self, nombre, limite_horas_mes=130):
        self.nombre = nombre
        self.limite_horas_mes = limite_horas_mes
        self.horas_acumuladas = 0
        self.fechas_bloqueadas = set()
        self.conteo_turnos = {'M': 0, 'T': 0}
        self.disp_manana = set()
        self.disp_tarde = set()

    def configurar_disponibilidad(self, dias_m, dias_t):
        mapa = {"Lu":0, "Ma":1, "Mi":2, "Ju":3, "Vi":4, "Sá":5, "Do":6}
        self.disp_manana = {mapa[d] for d in dias_m}
        self.disp_tarde = {mapa[d] for d in dias_t}

    def bloquear_fecha(self, fecha):
        if fecha:
            self.fechas_bloqueadas.add(fecha)

    def esta_disponible(self, fecha, turno, grilla):
        if fecha in self.fechas_bloqueadas:
            return False
        if grilla[fecha]['M'] == self.nombre or grilla[fecha]['T'] == self.nombre:
            return False
        
        dia_semana = fecha.weekday()
        if turno == 'M' and dia_semana not in self.disp_manana:
            return False
        if turno == 'T' and dia_semana not in self.disp_tarde:
            return False
            
        if self.horas_acumuladas + 9 > self.limite_horas_mes:
            return False
            
        consecutivos = 0
        for i in range(1, 4):
            previo = fecha - timedelta(days=i)
            if previo in grilla:
                if grilla[previo]['M'] == self.nombre or grilla[previo]['T'] == self.nombre:
                    consecutivos += 1
                else:
                    break
            else:
                break
        if consecutivos >= 3:
            return False
            
        return True

# ==========================================
# 4. GENERACIÓN DE PDF
# ==========================================
def generar_pdf_cronograma(grilla, res_h, res_t, anio, mes, auditor):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"CRONOGRAMA DE TURNOS - {mes}/{anio}", ln=True, align="C")
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(35, 8, "Fecha", border=1, fill=True)
    pdf.cell(20, 8, "Dia", border=1, fill=True)
    pdf.cell(65, 8, "Manana (6 a 15 hs)", border=1, fill=True)
    pdf.cell(65, 8, "Tarde (15 a 24 hs)", border=1, fill=True, ln=True)
    
    pdf.set_font("Arial", "", 10)
    dias_es = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    
    for f, t in sorted(grilla.items()):
        dia_str = dias_es[f.weekday()]
        f_str = f.strftime("%Y-%m-%d")
        
        pdf.cell(35, 7, f_str, border=1)
        pdf.cell(20, 7, dia_str[:2], border=1)
        
        if t['M'] == 'SIN CUBRIR':
            pdf.set_text_color(200, 0, 0)
        pdf.cell(65, 7, t['M'], border=1)
        pdf.set_text_color(0, 0, 0)
        
        if t['T'] == 'SIN CUBRIR':
            pdf.set_text_color(200, 0, 0)
        pdf.cell(65, 7, t['T'], border=1, ln=True)
        pdf.set_text_color(0, 0, 0)
        
    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Resumen de Rendimiento por Agente", ln=True)
    
    pdf.set_font("Arial", "", 10)
    for nom, h in res_h.items():
        tm = res_t[nom]['M']
        tt = res_t[nom]['T']
        info = f"Agente: {nom:<12} | Horas: {h} hs | M: {tm} | T: {tt}"
        pdf.cell(0, 6, info, ln=True)
        
    pdf.ln(15)
    pdf.set_font("Arial", "I", 8)
    pdf.set_text_color(100, 100, 100)
    f_imp = date.today().strftime("%Y-%m-%d")
    
    linea_auditor = f"Documento generado electronicamente. Auditor: {auditor.capitalize()}"
    linea_fecha = f"Fecha de exportacion: {f_imp}"
    
    pdf.cell(0, 5, linea_auditor, ln=True)
    pdf.cell(0, 5, linea_fecha, ln=True)
    return bytes(pdf.output())

# ==========================================
# 5. INTERFAZ DE USUARIO (STREAMLIT)
# ==========================================
st.set_page_config(page_title="Planificador de Turnos", layout="wide")

if not check_password():
    st.stop()

st.title("🗓️ Planificador y Rotación de Turnos")
st.sidebar.markdown(f"**👤 Operador:** `{st.session_state['usuario_actual'].capitalize()}`")
st.sidebar.markdown("---")

st.sidebar.header("1. Período a Planificar")
anio = st.sidebar.number_input("Año", min_value=
