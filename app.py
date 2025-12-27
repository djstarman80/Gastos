import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import json
import os
from fpdf import FPDF
import warnings

warnings.simplefilter(action="ignore", category=FutureWarning)

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Finanzas M&Y", layout="wide", page_icon="💰")

# --- CONSTANTES ---
MESES_NUMERO = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}

# --- UTILIDADES DE FORMATEO ---
def monto_uy_a_float(t):
    if t is None or (isinstance(t, float) and pd.isna(t)): return 0.0
    if isinstance(t, (int, float)): return float(t)
    s = str(t).strip().replace("$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try: return float(s)
    except: return 0.0

def float_a_monto_uy(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return "0,00"
    try:
        v = float(v)
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "0,00"

# --- BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect("finanzas.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Fecha TEXT, Monto REAL, Categoria TEXT, Persona TEXT,
            Descripcion TEXT, Tarjeta TEXT, CuotasTotales INTEGER,
            CuotasPagadas INTEGER, MesesPagados TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos_fijos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Descripcion TEXT, Monto REAL, Categoria TEXT, Persona TEXT,
            CuentaDebito TEXT, Activo BOOLEAN, Distribucion TEXT, MesesPagados TEXT
        )
    """)
    conn.commit()
    conn.close()

def cargar_datos():
    conn = sqlite3.connect("finanzas.db")
    df = pd.read_sql_query("SELECT * FROM gastos", conn)
    conn.close()
    return df

def cargar_gastos_fijos():
    conn = sqlite3.connect("finanzas.db")
    df = pd.read_sql_query("SELECT * FROM gastos_fijos", conn)
    conn.close()
    if not df.empty:
        df['Distribucion'] = df['Distribucion'].apply(lambda x: json.loads(x) if x else {"Marcelo": 50, "Yenny": 50})
    return df

# --- LÓGICA DE AUTOCIERRE ---
def aplicar_autocierre(dia_limite):
    hoy = datetime.today()
    if hoy.day >= dia_limite:
        mes_id = hoy.strftime("%Y-%m")
        conn = sqlite3.connect("finanzas.db")
        cursor = conn.cursor()
        # Cerrar Gastos Normales
        cursor.execute("""
            UPDATE gastos SET CuotasPagadas = CuotasPagadas + 1,
            MesesPagados = CASE WHEN MesesPagados='' OR MesesPagados IS NULL THEN ? ELSE MesesPagados||','||? END
            WHERE CuotasPagadas < CuotasTotales AND (MesesPagados NOT LIKE ? OR MesesPagados IS NULL)
        """, (mes_id, mes_id, f"%{mes_id}%"))
        # Cerrar Gastos Fijos
        cursor.execute("""
            UPDATE gastos_fijos SET 
            MesesPagados = CASE WHEN MesesPagados='' OR MesesPagados IS NULL THEN ? ELSE MesesPagados||','||? END
            WHERE Activo = 1 AND (MesesPagados NOT LIKE ? OR MesesPagados IS NULL)
        """, (mes_id, mes_id, f"%{mes_id}%"))
        conn.commit()
        conn.close()

# --- INTERFAZ ---
def main():
    init_db()
    
    # Sidebar Config
    st.sidebar.title("⚙️ Configuración")
    dia_cierre = st.sidebar.slider("Día de Autocierre", 1, 28, 10)
    if st.sidebar.button("💾 Backup Base de Datos"):
        with open("finanzas.db", "rb") as f:
            st.sidebar.download_button("Descargar .db", f, "finanzas.db")
    
    aplicar_autocierre(dia_cierre)
    
    st.session_state.df_gastos = cargar_datos()
    st.session_state.df_fijos = cargar_gastos_fijos()

    tab1, tab2, tab3, tab4 = st.tabs(["➕ Ingreso", "📋 Historial", "💳 Gastos Fijos", "⏰ Pagos Futuros"])

    # --- TAB 1: INGRESO ---
    with tab1:
        tipo = st.radio("Tipo:", ["Normal/Cuotas", "Fijo Mensual"], horizontal=True)
        with st.form("nuevo_gasto"):
            c1, c2 = st.columns(2)
            desc = c1.text_input("Descripción")
            monto = c2.text_input("Monto (UYU)", "0,00")
            pers = c1.selectbox("Persona", ["Marcelo", "Yenny", "Ambos"])
            cat = c2.selectbox("Categoría", ["Super", "Servicios", "Hogar", "Salud", "Salidas", "Otros"])
            
            if tipo == "Normal/Cuotas":
                cuotas = st.number_input("Cuotas Totales", 1, 36, 1)
                tarj = st.selectbox("Medio", ["BROU", "Santander", "OCA", "Efectivo"])
                if st.form_submit_button("Guardar"):
                    conn = sqlite3.connect("finanzas.db")
                    conn.execute("INSERT INTO gastos (Fecha, Monto, Categoria, Persona, Descripcion, Tarjeta, CuotasTotales, CuotasPagadas, MesesPagados) VALUES (?,?,?,?,?,?,?,?,?)",
                                 (datetime.today().strftime("%d/%m/%Y"), monto_uy_a_float(monto), cat, pers, desc, tarj, cuotas, 0, ""))
                    conn.commit()
                    conn.close()
                    st.rerun()
            else:
                if st.form_submit_button("Guardar Fijo"):
                    conn = sqlite3.connect("finanzas.db")
                    conn.execute("INSERT INTO gastos_fijos (Descripcion, Monto, Categoria, Persona, Activo, Distribucion, MesesPagados) VALUES (?,?,?,?,?,?,?)",
                                 (desc, monto_uy_a_float(monto), cat, pers, 1, json.dumps({"Marcelo":50, "Yenny":50}), ""))
                    conn.commit()
                    conn.close()
                    st.rerun()

    # --- TAB 4: PAGOS FUTUROS (LÓGICA MEJORADA) ---
    with tab4:
        hoy = datetime.today()
        st.header(f"Gestión de Pagos - {MESES_NUMERO[hoy.month]}")
        
        # Inicio de proyección dinámico
        inicio_p = hoy.replace(day=1) + pd.DateOffset(months=1) if hoy.day >= dia_cierre else hoy.replace(day=1)
        
        if hoy.day < dia_cierre:
            st.warning(f"Faltan {dia_cierre - hoy.day} días para el autocierre.")
        else:
            st.success(f"Día {hoy.day}: Mes actual cerrado automáticamente.")

        # Generar Proyección
        proyeccion = []
        for i in range(12):
            mes_f = inicio_p + pd.DateOffset(months=i)
            m_marce, m_yenny = 0.0, 0.0
            
            # Fijos
            for _, f in st.session_state.df_fijos[st.session_state.df_fijos['Activo']==1].iterrows():
                m = f['Monto']
                if f['Persona'] == "Marcelo": m_marce += m
                elif f['Persona'] == "Yenny": m_yenny += m
                else: 
                    m_marce += m * (f['Distribucion'].get('Marcelo', 50)/100)
                    m_yenny += m * (f['Distribucion'].get('Yenny', 50)/100)
            
            # Cuotas
            for _, g in st.session_state.df_gastos.iterrows():
                if i < (g['CuotasTotales'] - g['CuotasPagadas']):
                    cuota = g['Monto'] / g['CuotasTotales']
                    if g['Persona'] == "Marcelo": m_marce += cuota
                    elif g['Persona'] == "Yenny": m_yenny += cuota
                    else: m_marce += cuota*0.5; m_yenny += cuota*0.5
            
            proyeccion.append({
                "Mes": f"{MESES_NUMERO[mes_f.month]} '{str(mes_f.year)[2:]}",
                "Marcelo": f"${float_a_monto_uy(m_marce)}",
                "Yenny": f"${float_a_monto_uy(m_yenny)}",
                "Total": f"${float_a_monto_uy(m_marce + m_yenny)}"
            })
        
        st.table(pd.DataFrame(proyeccion))

        # --- MÉTRICAS FINALES ---
        st.divider()
        t_m = sum([monto_uy_a_float(x['Marcelo']) for x in proyeccion])
        t_y = sum([monto_uy_a_float(x['Yenny']) for x in proyeccion])
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Promedio Marcelo", f"${float_a_monto_uy(t_m/12)}")
        c2.metric("Promedio Yenny", f"${float_a_monto_uy(t_y/12)}")
        c3.metric("Gasto Promedio Mensual", f"${float_a_monto_uy((t_m+t_y)/12)}")

if __name__ == "__main__":
    main()
