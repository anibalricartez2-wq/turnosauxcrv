import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta
from fpdf import FPDF
import io

# ==========================================
# 1. SISTEMA DE LOGIN CON SECRETS
# ==========================================
def check_password():
    """Devuelve True si el usuario ingresó la contraseña correcta."""
    def password_entered():
        usuario = st.session_state["username"]
        password = st.session_state["password"]
        
        # Validar credenciales contra los secrets de Streamlit
        if "credenciales" in st.secrets and usuario in st.secrets["credenciales"] and st.secrets["credenciales"][usuario] == password:
            st.session_state["password_correct"] = True
            st.session_state["usuario_actual"] = usuario
            del st.session_state["password"]  # Borrar clave por seguridad
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    # Interfaz de Login
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
        self.disponibilidad = {i: ['M', 'T'] for i in range(7)}
        self.fechas_bloqueadas = set()

    def configurar_disponibilidad(self, dias_bool, turnos):
        for i, puede in enumerate(dias_bool):
            if puede:
                self.disponibilidad[i] = turnos
            else:
                self.disponibilidad[i] = []

    def bloquear_rango_fechas(self, inicio, fin):
        actual = inicio
        while actual <= fin:
            self.fechas_bloqueadas.add(actual)
            actual += timedelta(days=1)

    def esta_disponible(self, fecha, turno, dia_del_mes, total_dias):
        # Filtro de bloqueos (vacaciones/cursos)
        if fecha in self.fechas_bloqueadas:
            return False
        
        # Filtro de días de la semana y turno permitido
        dia_semana = fecha.weekday()
        if turno not in self.disponibilidad[dia_semana]:
            return False
            
        # Límite estricto mensual
        duracion = 9 if turno == 'M' else 8
        if self.horas_acumuladas + duracion > self.limite_horas_mes:
            return False
        
        # Control de ritmo: evita quemar todas las horas en las primeras semanas
        # Forzando a que los huecos ("SIN CUBRIR") se distribuyan y no queden a fin de mes
        limite_proporcional = (self.limite_horas_mes * (dia_del_mes / total_dias)) + 18 
        if self.horas_acumuladas > limite_proporcional:
            return False
            
        return True

# ==========================================
# 3. GENERACIÓN DE PDF
# ==========================================
def generar_pdf_cronograma(grilla, resumen_horas, anio, mes, usuario_auditor):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    
    pdf.cell(0, 10, f"CRONOGRAMA DE TURNOS - {mes}/{anio}", ln=True, align="C")
    pdf.ln(5)
    
    # Encabezados de Tabla
    pdf.set_font("Arial", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(35, 8, "Fecha", border=1, fill=True)
    pdf.cell(20, 8, "Dia", border=1, fill=True)
    pdf.cell(65, 8, "Manana (6 a 15 hs)", border=1, fill=True)
    pdf.cell(65, 8, "Tarde (15 a 23 hs)", border=1, fill=True, ln=True)
    
    # Filas de la Tabla
    pdf.set_font("Arial", "", 10)
    dias_es = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    
    for fecha, turnos in sorted(grilla.items()):
        dia_str = dias_es[fecha.weekday()]
        fecha_str = fecha.strftime("%Y-%m-%d")
        
        pdf.cell(35, 7, fecha_str, border=1)
        pdf.cell(20, 7, dia_str[:2], border=1)
        
        # Color rojo para casilleros sin cubrir
        if turnos['M'] == 'SIN CUBRIR':
            pdf.set_text_color(200, 0, 0)
        pdf.cell(65, 7, turnos['M'], border=1)
        pdf.set_text_color(0, 0, 0)
        
        if turnos['T'] == 'SIN CUBRIR':
            pdf.set_text_color(200, 0, 0)
        pdf.cell(65, 7, turnos['T'], border=1, ln=True)
        pdf.set_text_color(0, 0, 0)
        
    pdf.ln(10)
    
    # Resumen de Horas
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Resumen de Horas Trabajadas", ln=True)
    pdf.set_font("Arial", "", 10)
    for nombre, horas in resumen_horas.items():
        pdf.cell(0, 6, f"Agente: {nombre:<12} | Horas Asignadas: {horas} hs", ln=True)
        
    # Pie de página / Auditoría
    pdf.ln(15)
    pdf.set_font("Arial", "I", 8)
    pdf.set_text_color(100, 100, 100)
    fecha_impresion = date.today().strftime("%Y-%m-%d")
    pdf.cell(0, 5, f"Documento generado electronicamente. Auditor: {usuario_auditor.capitalize()}", ln=True)
    pdf.cell(0, 5, f"Fecha de exportacion: {fecha_impresion}", ln=True)
    
    return pdf.output(dest='S').encode('latin1') # Asegura compatibilidad de caracteres

# ==========================================
# 4. INTERFAZ PRINCIPAL STREAMLIT
# ==========================================
st.set_page_config(page_title="Planificador de Turnos", layout="wide")

# Barrera de Seguridad
if not check_password():
    st.stop()

st.title("🗓️ Sistema de Planificación y Rotación de Turnos")
st.sidebar.markdown(f"**👤 Operador actual:** `{st.session_state['usuario_actual'].capitalize()}`")
st.sidebar.markdown("---")

# Panel lateral: Período
st.sidebar.header("1. Período a Planificar")
anio = st.sidebar.number_input("Año", min_value=2024, max_value=2030, value=2026)
mes = st.sidebar.slider("Mes", min_value=1, max_value=12, value=6)
horas_max = st.sidebar.number_input("Límite Horas Mensuales", value=130)

# Panel lateral: Agentes
nombres_agentes = ["Sanchez", "Barros", "Garcia", "Ricartez"]
agentes_dict = {nom: Agente(nom, horas_max) for nom in nombres_agentes}

st.sidebar.header("2. Restricciones por Agente")
for nom in nombres_agentes:
    with st.sidebar.expander(f"⚙️ Configurar {nom}"):
        st.write("**Días de la semana permitidos:**")
        cols = st.columns(4)
        lu = cols[0].checkbox("Lu", value=True, key=f"lu_{nom}")
        ma = cols[1].checkbox("Ma", value=True, key=f"ma_{nom}")
        mi = cols[2].checkbox("Mi", value=True, key=f"mi_{nom}")
        ju = cols[3].checkbox("Ju", value=True, key=f"ju_{nom}")
        
        cols2 = st.columns(4)
        vi = cols2[0].checkbox("Vi", value=True, key=f"vi_{nom}")
        sa = cols2[1].checkbox("Sá", value=True, key=f"sa_{nom}")
        do = cols2[2].checkbox("Do", value=True, key=f"do_{nom}")
        
        turnos_pref = st.multiselect("Turnos permitidos", ["M", "T"], default=["M", "T"], key=f"tur_{nom}")
        agentes_dict[nom].configurar_disponibilidad([lu, ma, mi, ju, vi, sa, do], turnos_pref)
        
        st.write("**Fechas Bloqueadas (Licencias/Cursos):**")
        rango = st.date_input("Seleccionar rango", value=[], key=f"bloq_{nom}")
        if len(rango) == 2:
            agentes_dict[nom].bloquear_rango_fechas(rango[0], rango[1])

# Acción principal
if st.button("📊 Calcular y Distribuir Turnos", type="primary"):
    _, total_dias = calendar.monthrange(anio, mes)
    grilla_resultados = {}
    
    # Limpiar grilla
    for d in range(1, total_dias + 1):
        fecha_act = date(anio, mes, d)
        grilla_resultados[fecha_act] = {'M': 'SIN CUBRIR', 'T': 'SIN CUBRIR'}
        
    # Asignación de turnos (Prioridad Mañana)
    duracion_turnos = {'M': 9, 'T': 8}
    for turno in ['M', 'T']:
        for d in range(1, total_dias + 1):
            fecha_act = date(anio, mes, d)
            candidatos = [ag for ag in agentes_dict.values() if ag.esta_disponible(fecha_act, turno, d, total_dias)]
            
            if candidatos:
                candidatos.sort(key=lambda x: x.horas_acumuladas)
                elegido = candidatos[0]
                grilla_resultados[fecha_act][turno] = elegido.nombre
                elegido.horas_acumuladas += duracion_turnos[turno]

    # Mostrar Resultados en dos columnas
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("📋 Grilla de Turnos")
        data_tabla = []
        dias_es = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"]
        for f, t in sorted(grilla_resultados.items()):
            data_tabla.append({
                "Fecha": f.strftime("%Y-%m-%d"),
                "Día": dias_es[f.weekday()],
                "Mañana (6-15 hs)": t['M'],
                "Tarde (15-23 hs)": t['T']
            })
        df_mostrar = pd.DataFrame(data_tabla)
        
        # Resaltar en rojo si falta cubrir
        def color_rojo(val):
            color = '#ffcccc' if val == 'SIN CUBRIR' else ''
            return f'background-color: {color}'
            
        st.dataframe(df_mostrar.style.map(color_rojo, subset=["Mañana (6-15 hs)", "Tarde (15-23 hs)"]), use_container_width=True, height=600)

    with col2:
        st.subheader("📊 Resumen Horas")
        resumen_horas = {}
        for nom, ag in agentes_dict.items():
            resumen_horas[nom] = ag.horas_acumuladas
            st.metric(label=f"{nom}", value=f"{ag.horas_acumuladas} hs", delta=f"{horas_max - ag.horas_acumuladas} disp", delta_color="normal")
            
        st.markdown("---")
        st.subheader("🖨️ Exportar")
        
        # Generar PDF pasando el usuario logueado
        pdf_bytes = generar_pdf_cronograma(grilla_resultados, resumen_horas, anio, mes, st.session_state['usuario_actual'])
        
        st.download_button(
            label="📥 Descargar PDF Oficial",
            data=pdf_bytes,
            file_name=f"cronograma_{mes}_{anio}.pdf",
            mime="application/pdf",
            type="primary"
        )
