import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta
from fpdf import FPDF

# ==========================================
# 1. SISTEMA DE LOGIN CON SECRETS
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
# 2. LÓGICA DE NEGOCIO (AGENTES Y TURNOS)
# ==========================================
class Agente:
    def __init__(self, nombre, limite_horas_mes=130):
        self.nombre = nombre
        self.limite_horas_mes = limite_horas_mes
        self.horas_acumuladas = 0
        self.fechas_bloqueadas = set()
        
        # Guardar conteo de turnos para el reporte
        self.conteo_turnos = {'M': 0, 'T': 0}
        
        # Sets para guardar los días de la semana habilitados (0=Lunes, 6=Domingo)
        self.disp_manana = set()
        self.disp_tarde = set()

    def configurar_disponibilidad(self, dias_m, dias_t):
        mapa_dias = {"Lu": 0, "Ma": 1, "Mi": 2, "Ju": 3, "Vi": 4, "Sá": 5, "Do": 6}
        self.disp_manana = {mapa_dias[d] for d in dias_m}
        self.disp_tarde = {mapa_dias[d] for d in dias_t}

    def bloquear_fecha_especifica(self, fecha):
        if fecha:
            self.fechas_bloqueadas.add(fecha)

    def esta_disponible(self, fecha, turno, dia_del_mes, total_dias, grilla_actual):
        # 1. Filtro de fechas bloqueadas específicas
        if fecha in self.fechas_bloqueadas:
            return False
        
        # 2. Exclusión del mismo día (No duplica turnos en la misma fecha)
        if grilla_actual[fecha]['M'] == self.nombre or grilla_actual[fecha]['T'] == self.nombre:
            return False
        
        # 3. Filtro por día de la semana según el turno
        dia_semana = fecha.weekday()
        if turno == 'M' and dia_semana not in self.disp_manana:
            return False
        if turno == 'T' and dia_semana not in self.disp_tarde:
            return False
            
        # 4. Límite mensual de horas (Ambos turnos duran ahora 9 horas)
        duracion = 9
        if self.horas_acumuladas + duracion > self.limite_horas_mes:
            return False
            
        # 5. Regla de fatiga (Máximo 3 días seguidos)
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
        
        # 6. Control de ritmo proporcional para equilibrar huecos
        limite_proporcional = (self.limite_horas_mes * (dia_del_mes / total_dias)) + 18 
        if self.horas_acumuladas > limite_proporcional:
            return False
            
        return True

# ==========================================
# 3. GENERACIÓN DE PDF
# ==========================================
def generar_pdf_cronograma(grilla, resumen_horas, resumen_turnos, anio, mes, usuario_auditor):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    
    pdf.cell(0, 10, f"CRONOGRAMA DE TURNOS - {mes}/{anio}", ln=True, align="C")
    pdf.ln(5)
    
    # Encabezados de la Tabla
    pdf.set_font("Arial", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(35, 8, "Fecha", border=1, fill=True)
    pdf.cell(20, 8, "Dia", border=1, fill=True)
    pdf.cell(65, 8, "Manana (6 a 15 hs)", border=1, fill=True)
    pdf.cell(65, 8, "Tarde (15 a 24 hs)", border=1, fill=True, ln=True)
    
    pdf.set_font("Arial", "", 10)
    dias_es = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    
    for fecha, turnos in sorted(grilla.items()):
        dia_str = dias_es[fecha.weekday()]
        fecha_str = fecha.strftime("%Y-%m-%d")
        
        pdf.cell(35, 7, fecha_str, border=1)
        pdf.cell(20, 7, dia_str[:2], border=1)
        
        if turnos['M'] == 'SIN CUBRIR':
            pdf.set_text_color(200, 0, 0)
        pdf.cell(65, 7, turnos['M'], border=1)
        pdf.set_text_color(0, 0, 0)
        
        if turnos['T'] == 'SIN CUBRIR':
            pdf.set_text_color(200, 0, 0)
        pdf.cell(65, 7, turnos['T'], border=1, ln=True)
        pdf.set_text_color(0, 0, 0)
        
    pdf.ln(10)
    
    # Resumen de Rendimiento
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Resumen de Rendimiento por Agente", ln=True)
    pdf.set_font("Arial", "", 10)
    for nombre, horas in resumen_horas.items():
        t_m = resumen_turnos[nombre]['M']
        t_t = resumen_turnos[nombre]['T']
        pdf.cell(0, 6, f"Agente: {nombre:<12} | Horas: {horas} hs | Turnos M: {t_m} | Turnos T: {t_t}", ln=True)
        
    # Auditoría
    pdf.ln(15)
    pdf.set_font("Arial", "I", 8)
    pdf.set_text_color(100, 1
