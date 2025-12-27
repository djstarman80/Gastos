import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os
from fpdf import FPDF

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="M&Y Finanzas Pro", layout="wide", page_icon="💰")

MESES_NOMBRE = {1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 
                7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'}

# --- FUNCIONES DB ---
def ejecutar_query(q, p=()):
    conn = sqlite3.connect("finanzas.db")
    cursor = conn.cursor()
    cursor.execute(q, p)
    conn.commit()
    conn.close()
    st.session_state.hay_cambios = True

def inicializar_db():
    if 'db_cargada' not in st.session_state: st.session_state.db_cargada = False
    if 'hay_cambios' not in st.session_state: st.session_state.hay_cambios = False
    if 'editando' not in st.session_state: st.session_state.editando = None

    archivo_subido = st.sidebar.file_uploader("📂 Carga tu 'finanzas.db'", type="db")
    if archivo_subido and not st.session_state.db_cargada:
        with open("finanzas.db", "wb") as f: f.write(archivo_subido.getbuffer())
        st.session_state.db_cargada = True
        st.rerun()

    if not os.path.exists("finanzas.db"):
        ejecutar_query("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, Fecha TEXT, Monto REAL, Persona TEXT, Descripcion TEXT, Tarjeta TEXT, CuotasTotales INTEGER, CuotasPagadas INTEGER)")
        ejecutar_query("CREATE TABLE IF NOT EXISTS gastos_fijos (id INTEGER PRIMARY KEY AUTOINCREMENT, Descripcion TEXT, Monto REAL, Persona TEXT, Cuenta TEXT, Activo BOOLEAN, MesesPagados TEXT)")

def float_a_uy(v):
    return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- INTERFAZ ---
def main():
    inicializar_db()

    # Alerta de guardado
    if st.session_state.hay_cambios:
        st.warning("⚠️ Cambios sin guardar en el archivo de tu celular.")
        with open("finanzas.db", "rb") as f:
            if st.download_button("💾 GUARDAR CAMBIOS EN CELULAR", f, "finanzas.db", use_container_width=True):
                st.session_state.hay_cambios = False
                st.rerun()

    conn = sqlite3.connect("finanzas.db")
    df_g = pd.read_sql_query("SELECT * FROM gastos", conn)
    df_f = pd.read_sql_query("SELECT * FROM gastos_fijos", conn)
    conn.close()

    t1, t2, t3, t4 = st.tabs(["➕ Nuevo", "📋 Cuentas", "📊 Proyección", "💾 Exportar"])

    # --- TAB 1: NUEVO (Igual al anterior) ---
    with t1:
        st.subheader("Registrar Movimiento")
        with st.form("alta"):
            d = st.text_input("Descripción")
            m = st.number_input("Monto", min_value=0.0)
            p = st.selectbox("Persona", ["Marcelo", "Yenny"])
            tipo = st.radio("Tipo", ["Fijo", "Cuotas"], horizontal=True)
            if st.form_submit_button("Guardar"):
                f = datetime.today().strftime("%d/%m/%Y")
                if tipo == "Cuotas":
                    ejecutar_query("INSERT INTO gastos (Fecha, Monto, Persona, Descripcion, Tarjeta, CuotasTotales, CuotasPagadas) VALUES (?,?,?,?,'SANTANDER',1,0)", (f,m,p,d))
                else:
                    ejecutar_query("INSERT INTO gastos_fijos (Descripcion, Monto, Persona, Cuenta, Activo, MesesPagados) VALUES (?,?,?,?,1,?)", (d,m,p,'DÉBITO',f))
                st.rerun()

    # --- TAB 2: CUENTAS (CON EDICIÓN) ---
    with t2:
        st.subheader("Gestión y Edición")
        
        # Lógica de Edición
        if st.session_state.editando:
            item = st.session_state.editando
            st.info(f"📝 Editando: {item['desc']}")
            with st.form("form_edit"):
                new_desc = st.text_input("Descripción", value=item['desc'])
                new_monto = st.number_input("Monto", value=float(item['monto']))
                c_edit1, c_edit2 = st.columns(2)
                if c_edit1.form_submit_button("✅ Actualizar"):
                    if item['tipo'] == 'fijo':
                        ejecutar_query("UPDATE gastos_fijos SET Descripcion=?, Monto=? WHERE id=?", (new_desc, new_monto, item['id']))
                    else:
                        ejecutar_query("UPDATE gastos SET Descripcion=?, Monto=? WHERE id=?", (new_desc, new_monto, item['id']))
                    st.session_state.editando = None
                    st.rerun()
                if c_edit2.form_submit_button("❌ Cancelar"):
                    st.session_state.editando = None
                    st.rerun()
            st.divider()

        # Listado por medios
        for m in ["DÉBITO", "SANTANDER", "BROU", "OCA"]:
            sf = df_f[(df_f['Cuenta']==m) & (df_f['Activo']==1)]
            sg = df_g[df_g['Tarjeta']==m]
            if not sf.empty or not sg.empty:
                with st.expander(f"🏦 {m}"):
                    for _, r in sf.iterrows():
                        col_a, col_b, col_c = st.columns([0.6, 0.2, 0.2])
                        col_a.write(f"{r['Descripcion']}: ${float_a_uy(r['Monto'])}")
                        if col_b.button("✏️", key=f"ef_{r['id']}"):
                            st.session_state.editando = {'id':r['id'], 'desc':r['Descripcion'], 'monto':r['Monto'], 'tipo':'fijo'}
                            st.rerun()
                        if col_c.button("🗑️", key=f"df_{r['id']}"):
                            ejecutar_query("DELETE FROM gastos_fijos WHERE id=?", (r['id'],))
                            st.rerun()
                    for _, r in sg.iterrows():
                        col_a, col_b, col_c = st.columns([0.6, 0.2, 0.2])
                        col_a.write(f"{r['Descripcion']}: ${float_a_uy(r['Monto'])}")
                        if col_b.button("✏️", key=f"eg_{r['id']}"):
                            st.session_state.editando = {'id':r['id'], 'desc':r['Descripcion'], 'monto':r['Monto'], 'tipo':'cuota'}
                            st.rerun()
                        if col_c.button("🗑️", key=f"dg_{r['id']}"):
                            ejecutar_query("DELETE FROM gastos WHERE id=?", (r['id'],))
                            st.rerun()

    # --- TAB 3 y 4 (Proyección y Exportar - Igual que antes) ---
    with t3: st.write("Proyección de gastos futuros...")
    with t4: st.write("Exportar a PDF o CSV...")

if __name__ == "__main__":
    main()
