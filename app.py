import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os
from fpdf import FPDF

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="M&Y Finanzas", layout="wide", page_icon="💰")

# Estado de la sesión para seguridad
if 'ultimo_borrado' not in st.session_state: st.session_state.ultimo_borrado = None

MESES_NOMBRE = {1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 
                7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'}

# --- FUNCIONES DE APOYO ---
def monto_uy_a_float(t):
    if not t: return 0.0
    try:
        s = str(t).replace("$", "").replace(".", "").replace(",", ".").strip()
        return float(s)
    except: return 0.0

def float_a_monto_uy(v):
    return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def init_db():
    conn = sqlite3.connect("finanzas.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, Fecha TEXT, Monto REAL, Persona TEXT, Descripcion TEXT, Tarjeta TEXT, CuotasTotales INTEGER, CuotasPagadas INTEGER, MesesPagados TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos_fijos (id INTEGER PRIMARY KEY AUTOINCREMENT, Descripcion TEXT, Monto REAL, Persona TEXT, Cuenta TEXT, Activo BOOLEAN, MesesPagados TEXT)")
    conn.commit()
    conn.close()

def ejecutar_query(q, p=()):
    conn = sqlite3.connect("finanzas.db")
    conn.execute(q, p); conn.commit(); conn.close()

# --- INTERFAZ ---
def main():
    init_db()
    st.sidebar.title("⚙️ Ajustes")
    dia_cierre = st.sidebar.slider("Día de Cierre", 1, 28, 10)

    # BANNER DESHACER (Visible en todas las pestañas si hay un borrado reciente)
    if st.session_state.ultimo_borrado:
        with st.container():
            col_inf, col_undo = st.columns([3, 1])
            col_inf.warning(f"⚠️ Eliminado: {st.session_state.ultimo_borrado['nombre']}")
            if col_undo.button("↩️ DESHACER"):
                b = st.session_state.ultimo_borrado
                if b['tabla'] == 'gastos':
                    ejecutar_query("INSERT INTO gastos (Fecha, Monto, Persona, Descripcion, Tarjeta, CuotasTotales, CuotasPagadas, MesesPagados) VALUES (?,?,?,?,?,?,?,?)", b['datos'][1:])
                else:
                    ejecutar_query("INSERT INTO gastos_fijos (Descripcion, Monto, Persona, Cuenta, Activo, MesesPagados) VALUES (?,?,?,?,?,?)", b['datos'][1:])
                st.session_state.ultimo_borrado = None
                st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["➕ Ingreso", "📋 Por Tarjeta", "📊 Proyección", "💾 Backup"])

    # --- TAB 1: INGRESO UNIFICADO ---
    with tab1:
        with st.form("f_uni", clear_on_submit=True):
            tipo = st.radio("Tipo de Gasto", ["Gasto en Cuotas", "Gasto Fijo"], horizontal=True)
            desc = st.text_input("Descripción")
            monto = st.text_input("Monto ($)")
            c1, c2 = st.columns(2)
            pers = c1.selectbox("Responsable", ["Marcelo", "Yenny"])
            if tipo == "Gasto en Cuotas":
                medio = c2.selectbox("Tarjeta", ["BROU", "OCA", "SANTANDER"])
                cuotas = st.number_input("Cuotas Totales", 1, 36, 1)
            else:
                medio = c2.selectbox("Medio", ["DÉBITO", "BROU", "OCA", "SANTANDER"])
                cuotas = 1
            if st.form_submit_button("✅ GUARDAR", use_container_width=True):
                m_f = monto_uy_a_float(monto)
                if tipo == "Gasto en Cuotas":
                    ejecutar_query("INSERT INTO gastos (Fecha, Monto, Persona, Descripcion, Tarjeta, CuotasTotales, CuotasPagadas, MesesPagados) VALUES (?,?,?,?,?,?,?,?)", (datetime.today().strftime("%d/%m/%Y"), m_f, pers, desc, medio, cuotas, 0, ""))
                else:
                    ejecutar_query("INSERT INTO gastos_fijos (Descripcion, Monto, Persona, Cuenta, Activo, MesesPagados) VALUES (?,?,?,?,?,?)", (desc, m_f, pers, medio, 1, ""))
                st.rerun()

    # --- TAB 2: GESTIÓN POR TARJETA ---
    with tab2:
        conn = sqlite3.connect("finanzas.db")
        df_g = pd.read_sql_query("SELECT * FROM gastos", conn)
        df_f = pd.read_sql_query("SELECT * FROM gastos_fijos", conn)
        conn.close()
        for m in ["DÉBITO", "BROU", "OCA", "SANTANDER"]:
            with st.expander(f"🏦 {m}"):
                for _, r in df_g[df_g['Tarjeta']==m].iterrows():
                    c_t, c_b = st.columns([4, 1])
                    c_t.write(f"💳 {r['Descripcion']} ({r['Persona']}): ${float_a_monto_uy(r['Monto'])} [{r['CuotasPagadas']}/{r['CuotasTotales']}]")
                    if c_b.button("🗑️", key=f"dg{r['id']}"):
                        st.session_state.ultimo_borrado = {'tabla':'gastos', 'datos':r.values, 'nombre':r['Descripcion']}
                        ejecutar_query("DELETE FROM gastos WHERE id=?", (r['id'],)); st.rerun()
                for _, r in df_f[df_f['Cuenta']==m].iterrows():
                    c_t, c_b = st.columns([4, 1])
                    c_t.write(f"🏠 {r['Descripcion']} ({r['Persona']}): ${float_a_monto_uy(r['Monto'])} {'✅' if r['Activo'] else '❌'}")
                    if c_b.button("🗑️", key=f"df{r['id']}"):
                        st.session_state.ultimo_borrado = {'tabla':'gastos_fijos', 'datos':r.values, 'nombre':r['Descripcion']}
                        ejecutar_query("DELETE FROM gastos_fijos WHERE id=?", (r['id'],)); st.rerun()

    # --- TAB 3: PROYECCIÓN (DISEÑO MÓVIL) ---
    with tab3:
        hoy = datetime.today()
        inicio_p = hoy.replace(day=1) + pd.DateOffset(months=1) if hoy.day >= dia_cierre else hoy.replace(day=1)
        for i in range(6): # Mostramos los próximos 6 meses como tarjetas
            mes_f = inicio_p + pd.DateOffset(months=i)
            sm, sy = 0.0, 0.0
            for _, f in df_f[df_f['Activo']==1].iterrows():
                if f['Persona'] == "Marcelo": sm += f['Monto']
                else: sy += f['Monto']
            for _, g in df_g.iterrows():
                if i < (g['CuotasTotales'] - g['CuotasPagadas']):
                    if g['Persona'] == "Marcelo": sm += g['Monto']
                    else: sy += g['Monto']
            
            # Diseño de Tarjeta
            with st.container(border=True):
                st.markdown(f"### 📅 {MESES_NOMBRE[mes_f.month]} {mes_f.year}")
                c_m, c_y = st.columns(2)
                c_m.metric("Marcelo", f"${float_a_monto_uy(sm)}")
                c_y.metric("Yenny", f"${float_a_monto_uy(sy)}")
                st.markdown(f"**Total Mes: ${float_a_monto_uy(sm+sy)}**")

    # --- TAB 4: BACKUP ---
    with tab4:
        if os.path.exists("finanzas.db"):
            with open("finanzas.db", "rb") as f:
                st.download_button("📥 Descargar Base de Datos", f, "finanzas.db")

if __name__ == "__main__":
    main()
