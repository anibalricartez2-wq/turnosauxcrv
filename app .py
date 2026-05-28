import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta
from fpdf import FPDF

# ==========================================
# 1. INITIALIZE SESSION STATE (MEMORIA DE LA APP)
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
    """Devuelve True si el usuario ingresó la contraseña correcta."""
    def password_entered():
        usuario = st.session_state["username"]
        password = st.session_state["password"]
        
        if "credenciales" in st.secrets and usuario in st.secrets["credenciales"] and st.secrets["credenciales"][usuario] == password:
            st.session_state["password_correct"] = True
            st.session_state["usuario_actual"] = usuario
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.title("🔒 Acceso Restringido")
    st.markdown("Por favor, ingresá tus credenciales para acceder al planificador.")
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
        mapa_dias = {"Lu": 0, "Ma": 1, "Mi": 2, "Ju": 3, "Vi": 4, "Sá": 5, "Do": 6}
        self.disp_manana = {mapa_dias[d] for d in dias_m}
        self.disp_tarde = {mapa_dias[d] for d in dias_t}

    def bloquear_fecha(self, fecha):
        if fecha:
            self.fechas_bloqueadas.add(fecha)

    def esta_disponible(self, fecha, turno, dia_del_mes, total_dias, grilla_actual):
        # 1. Filtro de fechas bloqueadas individuales o licencias
        if fecha in self.fechas_bloqueadas:
            return False
        
        # 2. Control de doble turno el mismo día
        if grilla_actual[fecha]['M'] == self.nombre or grilla_actual[fecha]['T'] == self.nombre:
            return False
        
        # 3. Filtro de disponibilidad semanal por turno
        dia_semana = fecha.weekday()
        if turno == 'M' and dia_semana not in self.disp_manana:
            return False
        if turno == 'T' and dia_semana not in self.disp_tarde:
            return False
            
        # 4. Límite de carga horaria (Ambos turnos de 9hs)
        if self.horas_acumuladas + 9 > self.limite_horas_mes:
            return False
            
        # 5. Regla de fatiga: Máximo 3 días seguidos de servicio
        consecutivos = 0
        for i in range(1, 4):
            dia_previo = fecha - timedelta(days=i)
            if dia_previo in grilla_actual:
                if grilla_actual[dia_previo]['M'] == self.nombre or grilla_actual[dia_previo]['T'] == self.nombre:
                    consecutivos += 1
                else:
                    break
            else:
                break
                
        if consecutivos >= 3:
            return False
        
        # 6. Distribución armónica (Pacing)
        limite_proporcional = (self.limite_horas_mes * (dia_del_mes / total_dias)) + 18 
        if self.horas_acumuladas > limite_proporcional:
            return False
            
        return True

# ==========================================
# 4. GENERACIÓN DE PDF COMPATIBLE CON FPDF2
# ==========================================
def generar_pdf_cronograma(grilla, resumen_horas, resumen_turnos, anio, mes, usuario_auditor):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    
    pdf.cell(0, 10, f"CRONOGRAMA DE TURNOS - {mes}/{anio}", ln=True, align="C")
    pdf.ln(5)
    
    # Encabezados
    pdf.set_font("Arial", "B",
