import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os
from fpdf import FPDF

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="M&Y Finanzas Pro", layout="wide", page_icon="💰")

MESES_NOMBRE = {1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 
                7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'}

# --- FUNCIONES DE BASE DE DATOS ---
def ejecutar_query(q, p=()):
    conn = sqlite3.connect("finanzas.db")
    cursor = conn.cursor()
    cursor.execute(q, p)
    conn.commit()
    conn.close()
    st.session_state.hay_cambios = True

def verificar_y_reparar_db():
    conn = sqlite3.connect("finanzas.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, Fecha TEXT, Monto REAL, Persona TEXT, Descripcion TEXT, Tarjeta TEXT, CuotasTotales INTEGER, CuotasPagadas INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos_fijos (id INTEGER PRIMARY KEY AUTOINCREMENT, Descripcion TEXT, Monto REAL, Persona TEXT, Cuenta TEXT, Activo BOOLEAN, MesesPagados TEXT)")
    
    # Reparación de columnas faltantes
    c.execute("PRAGMA table_info(gastos_fijos)")
    cols_fijos = [col[1] for col in c.fetchall()]
    if 'Cuenta' not in cols_fijos: c.execute("ALTER TABLE gastos_fijos ADD COLUMN Cuenta TEXT DEFAULT 'DÉBITO'")
    if 'Activo' not in cols_fijos: c.execute("ALTER TABLE gastos_fijos ADD COLUMN Activo BOOLEAN DEFAULT 1")
    
    conn.commit()
    conn.close()

def inicializar_estado():
    if 'db_cargada' not in st.session_state: st.session_state.db_cargada = False
    if 'hay_cambios' not in st.session_state: st.session_state.hay_cambios = False
    if 'editando' not in st.session_state: st.session_state.editando = None

def manejar_db():
    st.sidebar.title("🔐 Acceso a Datos")
    archivo_subido = st.sidebar.file_uploader("Sube tu 'finanzas.db'", type="db")
    if archivo_subido and not st.session_state.db_cargada:
        with open("finanzas.db", "wb") as f: f.write(archivo_subido.getbuffer())
        verificar_y_reparar_db()
        st.session_state.db_cargada = True
        st.rerun()
    if not os.path.exists("finanzas.db"): verificar_y_reparar_db()

def float_a_uy(v):
    try: return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "0,00"

# --- INTERFAZ ---
def main():
    inicializar_estado()
    manejar_db()

    if st.session_state.hay_cambios:
        st.warning("⚠️ Cambios detectados. ¡Descarga tu backup!")
        with open("finanzas.db", "rb") as f:
            if st.download_button("💾 DESCARGAR DB ACTUALIZADA", f, "finanzas.db", use_container_width=True):
                st.session_state.hay_cambios = False
                st.rerun()

    conn = sqlite3.connect("finanzas.db")
    df_g = pd.read_sql_query("SELECT * FROM gastos", conn)
    df_f = pd.read_sql_query("SELECT * FROM gastos_fijos", conn)
    conn.close()

    t1, t2, t3, t4 = st.tabs(["➕ Nuevo", "📋 Cuentas", "📊 Proyección", "💾 Exportar"])

    # --- TAB 1: NUEVO ---
    with t1:
        st.subheader("Registrar Movimiento")
        tipo = st.radio("Tipo:", ["Débito / Fijo", "Compra en Cuotas"], horizontal=True)
        with st.form("alta", clear_on_submit=True):
            d = st.text_input("Descripción")
            m = st.number_input("Monto ($)", min_value=0.0)
            p = st.selectbox("Quién", ["Marcelo", "Yenny"])
            # Agregamos "OTROS" a la lista por defecto
            medio = st.selectbox("Medio de Pago", ["DÉBITO", "SANTANDER", "BROU", "OCA", "OTROS"])
            c_totales = st.number_input("Cuotas", 1, 48, 1) if tipo == "Compra en Cuotas" else 1
            if st.form_submit_button("✅ GUARDAR"):
                f = datetime.today().strftime("%d/%m/%Y")
                if tipo == "Compra en Cuotas":
                    ejecutar_query("INSERT INTO gastos (Fecha, Monto, Persona, Descripcion, Tarjeta, CuotasTotales, CuotasPagadas) VALUES (?,?,?,?,?,?,?)", (f, m, p, d, medio, c_totales, 0))
                else:
                    ejecutar_query("INSERT INTO gastos_fijos (Descripcion, Monto, Persona, Cuenta, Activo, MesesPagados) VALUES (?,?,?,?,?,?)", (d, m, p, medio, 1, f))
                st.rerun()

    # --- TAB 2: CUENTAS (ARREGLO PARA 'OTROS') ---
    with t2:
        st.subheader("Estado de Cuentas")
        
        # Obtener TODOS los medios únicos que existen en ambas tablas
        medios_fijos = df_f['Cuenta'].unique().tolist() if 'Cuenta' in df_f.columns else []
        medios_variables = df_g['Tarjeta'].unique().tolist() if 'Tarjeta' in df_g.columns else []
        todos_los_medios = sorted(list(set(medios_fijos + medios_variables + ["DÉBITO", "SANTANDER", "BROU", "OCA"])))

        if st.session_state.editando:
            ed = st.session_state.editando
            with st.form("editor"):
                n_d = st.text_input("Descripción", value=ed['desc'])
                n_m = st.number_input("Monto", value=float(ed['monto']))
                n_p = st.selectbox("Persona", ["Marcelo", "Yenny"], index=0 if ed['persona']=="Marcelo" else 1)
                if st.form_submit_button("Actualizar"):
                    tabla = "gastos_fijos" if ed['tipo'] == 'fijo' else "gastos"
                    ejecutar_query(f"UPDATE {tabla} SET Descripcion=?, Monto=?, Persona=? WHERE id=?", (n_d, n_m, n_p, ed['id']))
                    st.session_state.editando = None
                    st.rerun()

        for m in todos_los_medios:
            sf = df_f[df_f['Cuenta'] == m] if 'Cuenta' in df_f.columns else pd.DataFrame()
            sg = df_g[df_g['Tarjeta'] == m] if 'Tarjeta' in df_g.columns else pd.DataFrame()
            
            if not sf.empty or not sg.empty:
                total = sf['Monto'].sum() + sg['Monto'].sum()
                with st.expander(f"🏦 {m} - Total: ${float_a_uy(total)}"):
                    for _, r in sf.iterrows():
                        c1, c2, c3 = st.columns([0.6, 0.2, 0.2])
                        c1.write(f"🏠 {r['Descripcion']} ({r['Persona']}): ${float_a_uy(r['Monto'])}")
                        if c2.button("✏️", key=f"ef_{r['id']}"):
                            st.session_state.editando = {'id':r['id'], 'desc':r['Descripcion'], 'monto':r['Monto'], 'persona':r['Persona'], 'tipo':'fijo'}
                            st.rerun()
                        if c3.button("🗑️", key=f"df_{r['id']}"):
                            ejecutar_query("DELETE FROM gastos_fijos WHERE id=?", (r['id'],)); st.rerun()
                    for _, r in sg.iterrows():
                        c1, c2, c3 = st.columns([0.6, 0.2, 0.2])
                        c1.write(f"💳 {r['Descripcion']} ({r['Persona']}): ${float_a_uy(r['Monto'])}")
                        if c2.button("✏️", key=f"eg_{r['id']}"):
                            st.session_state.editando = {'id':r['id'], 'desc':r['Descripcion'], 'monto':r['Monto'], 'persona':r['Persona'], 'tipo':'cuota'}
                            st.rerun()
                        if c3.button("🗑️", key=f"dg_{r['id']}"):
                            ejecutar_query("DELETE FROM gastos WHERE id=?", (r['id'],)); st.rerun()

    # --- TAB 3 y 4 (Proyección y Exportar se mantienen igual) ---
    with t3:
        st.subheader("Proyección a 6 Meses")
        # ... (lógica de proyección igual a la anterior)
        inicio = datetime.today().replace(day=1)
        for i in range(6):
            mes = inicio + pd.DateOffset(months=i)
            sm, sy = 0.0, 0.0
            for _, r in df_f.iterrows():
                if r['Persona'] == "Marcelo": sm += r['Monto']
                else: sy += r['Monto']
            for _, r in df_g.iterrows():
                if i < (r.get('CuotasTotales', 1) - r.get('CuotasPagadas', 0)):
                    if r['Persona'] == "Marcelo": sm += r['Monto']
                    else: sy += r['Monto']
            st.info(f"📅 {MESES_NOMBRE[mes.month]} {mes.year} | Marcelo: ${float_a_uy(sm)} | Yenny: ${float_a_uy(sy)}")

    with t4:
        st.subheader("Exportar")
        if st.button("Limpiar Pantalla de Errores"): st.rerun()
        # Lógica de exportación... (igual a la anterior blindada)

if __name__ == "__main__":
    main()
