import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta
from fpdf import FPDF

# Inicializar los estados de memoria para que no se borren los resultados al interactuar
if "calculado" not in st.session_state:
    st.session_state["calculado"] = False
    st.session_state["grilla_resultados"] = {}
    st.session_state["resumen_horas"] = {}
    st.session_state["resumen_turnos"] = {}

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
        
        # Registro exacto de asignaciones
        self.conteo_turnos = {'M': 0, 'T': 0}
        
        # Disponibilidad semanal (0=Lunes, 6=Domingo)
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
        if fecha in self.fechas_bloqueadas:
            return False
        
        if grilla_actual[fecha]['M'] == self.nombre or grilla_actual[fecha]['T'] == self.nombre:
            return False
        
        dia_semana = fecha.weekday()
        if turno == 'M' and dia_semana not in self.disp_manana:
            return False
        if turno == 'T' and dia_semana not in self.disp_tarde:
            return False
            
        duracion = 9
        if self.horas_acumuladas + duracion > self.limite_horas_mes:
            return False
            
        # Regla de fatiga: máximo 3 días de servicio consecutivos
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
    
    # Encabezados de tabla
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
    
    # Reporte de balances
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Resumen de Rendimiento por Agente", ln=True)
    pdf.set_font("Arial", "", 10)
    for nombre, horas in resumen_horas.items():
        t_m = resumen_turnos[nombre]['M']
        t_t = resumen_turnos[nombre]['T']
        pdf.cell(0, 6, f"Agente: {nombre:<12} | Horas: {horas} hs | Turnos M: {t_m} | Turnos T: {t_t}", ln=True)
        
    # Bloque de auditoría
    pdf.ln(15)
    pdf.set_font("Arial", "I", 8)
    pdf.set_text_color(100, 100, 100)
    fecha_impresion = date.today().strftime("%Y-%m-%d")
    pdf.cell(0, 5, f"Documento generado electronicamente. Auditor: {usuario_auditor.capitalize()}", ln=True)
    pdf.cell(0, 5, f"Fecha de exportacion: {fecha_impresion}", ln=True)
    
    return bytes(pdf.output())

# ==========================================
# 4. INTERFAZ PRINCIPAL STREAMLIT
# ==========================================
st.set_page_config(page_title="Planificador de Turnos", layout="wide")

if not check_password():
    st.stop()

st.title("🗓️ Sistema de Planificación y Rotación de Turnos")
st.sidebar.markdown(f"**👤 Operador actual:** `{st.session_state['usuario_actual'].capitalize()}`")
st.sidebar.markdown("---")

# Parámetros del período
st.sidebar.header("1. Período a Planificar")
anio = st.sidebar.number_input("Año", min_value=2024, max_value=2030, value=2026)
mes = st.sidebar.slider("Mes", min_value=1, max_value=12, value=6)
horas_max = st.sidebar.number_input("Límite Horas Mensuales", value=130)

# Inicialización limpia de agentes
nombres_agentes = ["Sanchez", "Barros", "Garcia", "Ricartez"]
agentes_dict = {nom: Agente(nom, horas_max) for nom in nombres_agentes}
lista_dias = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"]

st.sidebar.header("2. Restricciones por Agente")
for nom in nombres_agentes:
    with st.sidebar.expander(f"⚙️ Configurar {nom}"):
        st.write("**Disponibilidad semanal por Turno:**")
        dias_m = st.multiselect("Días para Mañana (6-15 hs)", lista_dias, default=lista_dias, key=f"m_{nom}")
        dias_t = st.multiselect("Días para Tarde (15-24 hs)", lista_dias, default=lista_dias, key=f"t_{nom}")
        agentes_dict[nom].configurar_disponibilidad(dias_m, dias_t)
        
        st.write("**Bloquear fechas específicas en el calendario:**")
        fechas_bloq = st.date_input("Seleccionar rango o día individual", value=[], key=f"fechas_especificas_{nom}")
        
        if isinstance(fechas_bloq, (list, tuple)):
            if len(fechas_bloq) == 2:
                inicio, fin = fechas_bloq[0], fechas_bloq[1]
                cursor = inicio
                while cursor <= fin:
                    agentes_dict[nom].block_fecha = agentes_dict[nom].bloquear_fecha(cursor)
                    cursor += timedelta(days=1)
            elif len(fechas_bloq) == 1:
                agentes_dict[nom].bloquear_fecha(fechas_bloq[0])
        elif fechas_bloq:
            agentes_dict[nom].bloquear_fecha(fechas_bloq)

# Clic en procesar cálculo
if st.button("📊 Calcular y Distribuir Turnos", type="primary"):
    _, total_dias = calendar.monthrange(anio, mes)
    grilla_resultados = {}
    
    for d in range(1, total_dias + 1):
        fecha_act = date(anio, mes, d)
        grilla_resultados[fecha_act] = {'M': 'SIN CUBRIR', 'T': 'SIN CUBRIR'}
        
    duracion_turnos = {'M': 9, 'T': 9}
    
    for d in range(1, total_dias + 1):
        fecha_act = date(anio, mes, d)
        for turno in ['M', 'T']:
            candidatos = [ag for ag in agentes_dict.values() if ag.esta_disponible(fecha_act, turno, d, total_dias, grilla_resultados)]
            
            if candidatos:
                candidatos.sort(key=lambda x: x.horas_acumuladas)
                elegido = candidatos[0]
                
                grilla_resultados[fecha_act][turno] = elegido.nombre
                elegido.horas_acumuladas += duracion_turnos[turno]
                elegido.conteo_turnos[turno] += 1

    # PERSISTENCIA: Guardamos todo en la memoria de la sesión
    st.session_state["grilla_resultados"] = grilla_resultados
    st.session_state["resumen_horas"] = {nom: ag.horas_acumuladas for nom, ag in agentes_dict.items()}
    st.session_state["resumen_turnos"] = {nom: ag.conteo_turnos for nom, ag in agentes_dict.items()}
    st.session_state["calculado"] = True

# RENDERING INDEPENDIENTE: Si ya está calculado, se dibuja siempre (no desaparece)
if st.session_state["calculado"]:
    grilla_resultados = st.session_state["grilla_resultados"]
    resumen_horas = st.session_state["resumen_horas"]
    resumen_turnos = st.session_state["resumen_turnos"]
    
    col1, col2 = st.columns([2.7, 1.2])
    
    with col1:
        st.subheader("📋 Grilla de Turnos")
        data_tabla = []
        for f, t in sorted(grilla_resultados.items()):
            data_tabla.append({
                "Fecha": f.strftime("%Y-%m-%d"),
                "Día": lista_dias[f.weekday()],
                "Mañana (6-15 hs)": t['M'],
                "Tarde (15-24 hs)": t['T']
            })
        df_mostrar = pd.DataFrame(data_tabla)
        
        def color_rojo(val):
            return 'background-color: #ffcccc' if val == 'SIN CUBRIR' else ''
            
        st.dataframe(df_mostrar.style.map(color_rojo, subset=["Mañana (6-15 hs)", "Tarde (15-24 hs)"]), use_container_width=True, height=600)

    with col2:
        st.subheader("📊 Métricas de Carga")
        
        data_tabla_turnos = []
        for nom in nombres_agentes:
            horas = resumen_horas[nom]
            t_m = resumen_turnos[nom]['M']
            t_t = resumen_turnos[nom]['T']
            
            data_tabla_turnos.append({
                "Agente": nom,
                "Turnos M": t_m,
                "Turnos T": t_t,
                "Total Horas": f"{horas} hs"
            })
            
            st.metric(label=f"Horas {nom}", value=f"{horas} hs", delta=f"{horas_max - horas} disp")
            
        st.markdown
