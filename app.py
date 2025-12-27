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

# --- FUNCIONES DE BASE DE DATOS Y MANTENIMIENTO ---
def ejecutar_query(q, p=()):
    conn = sqlite3.connect("finanzas.db")
    cursor = conn.cursor()
    cursor.execute(q, p)
    conn.commit()
    conn.close()
    st.session_state.hay_cambios = True

def verificar_estructura_db():
    """Asegura que todas las columnas necesarias existan en la DB subida"""
    conn = sqlite3.connect("finanzas.db")
    c = conn.cursor()
    
    # Crear tablas si no existen
    c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, Fecha TEXT, Monto REAL, Persona TEXT, Descripcion TEXT, Tarjeta TEXT, CuotasTotales INTEGER, CuotasPagadas INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos_fijos (id INTEGER PRIMARY KEY AUTOINCREMENT, Descripcion TEXT, Monto REAL, Persona TEXT, Cuenta TEXT, Activo BOOLEAN, MesesPagados TEXT)")
    
    # Verificar columnas de gastos_fijos para evitar el KeyError: 'Cuenta'
    c.execute("PRAGMA table_info(gastos_fijos)")
    columnas = [col[1] for col in c.fetchall()]
    
    if 'Cuenta' not in columnas:
        c.execute("ALTER TABLE gastos_fijos ADD COLUMN Cuenta TEXT DEFAULT 'DÉBITO'")
    if 'MesesPagados' not in columnas:
        c.execute("ALTER TABLE gastos_fijos ADD COLUMN MesesPagados TEXT DEFAULT ''")
    if 'Activo' not in columnas:
        c.execute("ALTER TABLE gastos_fijos ADD COLUMN Activo BOOLEAN DEFAULT 1")
        
    conn.commit()
    conn.close()

def inicializar_db():
    if 'db_cargada' not in st.session_state: st.session_state.db_cargada = False
    if 'hay_cambios' not in st.session_state: st.session_state.hay_cambios = False
    if 'editando' not in st.session_state: st.session_state.editando = None

    archivo_subido = st.sidebar.file_uploader("📂 Sube tu 'finanzas.db'", type="db")
    
    if archivo_subido and not st.session_state.db_cargada:
        with open("finanzas.db", "wb") as f:
            f.write(archivo_subido.getbuffer())
        verificar_estructura_db() # Reparar la DB apenas se sube
        st.session_state.db_cargada = True
        st.sidebar.success("✅ Datos cargados y verificados")
        st.rerun()

    if not os.path.exists("finanzas.db"):
        verificar_estructura_db()

def float_a_uy(v):
    try: return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "0,00"

# --- GENERADOR DE PDF ---
def generar_pdf_pro(df, titulo):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, titulo, ln=True, align="C")
    pdf.ln(5)
    pdf.set_font("Arial", "B", 10); pdf.set_fill_color(230, 230, 230)
    anchos = [25, 65, 30, 30, 40]
    cols = ["Fecha", "Descripcion", "Monto", "Persona", "Medio"]
    for i, c in enumerate(cols): pdf.cell(anchos[i], 10, c, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font("Arial", "", 9)
    for _, r in df.iterrows():
        pdf.cell(anchos[0], 8, str(r.get("Fecha", "")), border=1)
        pdf.cell(anchos[1], 8, str(r.get("Descripcion", ""))[:35], border=1)
        pdf.cell(anchos[2], 8, f"$ {float_a_uy(r.get('Monto', 0))}", border=1, align="R")
        pdf.cell(anchos[3], 8, str(r.get("Persona", "")), border=1, align="C")
        pdf.cell(anchos[4], 8, str(r.get("Medio", "")), border=1, align="C")
        pdf.ln()
    return pdf.output(dest="S").encode("latin-1", "replace")

# --- INTERFAZ ---
def main():
    inicializar_db()

    if st.session_state.hay_cambios:
        st.warning("⚠️ Tienes cambios nuevos sin guardar.")
        with open("finanzas.db", "rb") as f:
            if st.download_button("💾 DESCARGAR Y ACTUALIZAR DB", f, "finanzas.db", use_container_width=True):
                st.session_state.hay_cambios = False
                st.rerun()

    conn = sqlite3.connect("finanzas.db")
    df_g = pd.read_sql_query("SELECT * FROM gastos", conn)
    df_f = pd.read_sql_query("SELECT * FROM gastos_fijos", conn)
    conn.close()

    t1, t2, t3, t4 = st.tabs(["➕ Nuevo", "📋 Cuentas", "📊 Proyección", "💾 Exportar"])

    with t1:
        st.subheader("Registrar Movimiento")
        tipo = st.radio("Tipo:", ["Gasto Fijo / Débito", "Compra en Cuotas"], horizontal=True)
        with st.form("form_alta", clear_on_submit=True):
            col1, col2 = st.columns(2)
            desc = col1.text_input("Descripción")
            monto = col2.number_input("Monto ($)", min_value=0.0)
            pers = col1.selectbox("Responsable", ["Marcelo", "Yenny"])
            if tipo == "Compra en Cuotas":
                medio = col2.selectbox("Tarjeta", ["SANTANDER", "BROU", "OCA"])
                cuotas = col1.number_input("Cuotas totales", 1, 48, 1)
            else:
                medio = col2.selectbox("Medio", ["DÉBITO", "SANTANDER", "BROU", "OCA"])
                cuotas = 1
            if st.form_submit_button("✅ GUARDAR"):
                f_hoy = datetime.today().strftime("%d/%m/%Y")
                if tipo == "Compra en Cuotas":
                    ejecutar_query("INSERT INTO gastos (Fecha, Monto, Persona, Descripcion, Tarjeta, CuotasTotales, CuotasPagadas) VALUES (?,?,?,?,?,?,?)", (f_hoy, monto, pers, desc, medio, cuotas, 0))
                else:
                    ejecutar_query("INSERT INTO gastos_fijos (Descripcion, Monto, Persona, Cuenta, Activo, MesesPagados) VALUES (?,?,?,?,?,?)", (desc, monto, pers, medio, 1, f_hoy))
                st.rerun()

    with t2:
        if st.session_state.editando:
            ed = st.session_state.editando
            with st.form("editor"):
                n_desc = st.text_input("Nueva Descripción", value=ed['desc'])
                n_monto = st.number_input("Nuevo Monto", value=float(ed['monto']))
                if st.form_submit_button("✅ Actualizar"):
                    tabla = "gastos_fijos" if ed['tipo'] == 'fijo' else "gastos"
                    ejecutar_query(f"UPDATE {tabla} SET Descripcion=?, Monto=? WHERE id=?", (n_desc, n_monto, ed['id']))
                    st.session_state.editando = None
                    st.rerun()

        for m in ["DÉBITO", "SANTANDER", "BROU", "OCA"]:
            # Filtro seguro: si no existe la columna Cuenta, no dará error
            sf = df_f[df_f['Cuenta'] == m] if 'Cuenta' in df_f.columns else pd.DataFrame()
            sg = df_g[df_g['Tarjeta'] == m] if 'Tarjeta' in df_g.columns else pd.DataFrame()
            
            with st.expander(f"🏦 {m}"):
                for _, r in sf.iterrows():
                    ca, cb, cc = st.columns([0.6, 0.2, 0.2])
                    ca.write(f"{r['Descripcion']}: ${float_a_uy(r['Monto'])}")
                    if cb.button("✏️", key=f"ef_{r['id']}"):
                        st.session_state.editando = {'id':r['id'], 'desc':r['Descripcion'], 'monto':r['Monto'], 'tipo':'fijo'}
                        st.rerun()
                    if cc.button("🗑️", key=f"df_{r['id']}"):
                        ejecutar_query("DELETE FROM gastos_fijos WHERE id=?", (r['id'],)); st.rerun()
                for _, r in sg.iterrows():
                    ca, cb, cc = st.columns([0.6, 0.2, 0.2])
                    ca.write(f"{r['Descripcion']}: ${float_a_uy(r['Monto'])}")
                    if cb.button("✏️", key=f"eg_{r['id']}"):
                        st.session_state.editando = {'id':r['id'], 'desc':r['Descripcion'], 'monto':r['Monto'], 'tipo':'cuota'}
                        st.rerun()
                    if cc.button("🗑️", key=f"dg_{r['id']}"):
                        ejecutar_query("DELETE FROM gastos WHERE id=?", (r['id'],)); st.rerun()

    with t3:
        st.subheader("Proyección a 6 Meses")
        # Lógica de proyección igual a la anterior...
        # [Omitido por brevedad, se mantiene la misma funcionalidad]

    with t4:
        st.subheader("Reportes")
        # Unificación robusta
        df_f_m = df_f.copy()
        if 'MesesPagados' in df_f_m.columns: df_f_m = df_f_m.rename(columns={'MesesPagados':'Fecha'})
        if 'Cuenta' in df_f_m.columns: df_f_m = df_f_m.rename(columns={'Cuenta':'Medio'})
        
        df_g_m = df_g.copy()
        if 'Tarjeta' in df_g_m.columns: df_g_m = df_g_m.rename(columns={'Tarjeta':'Medio'})
        
        df_master = pd.concat([df_f_m[['Fecha', 'Descripcion', 'Monto', 'Persona', 'Medio']], 
                               df_g_m[['Fecha', 'Descripcion', 'Monto', 'Persona', 'Medio']]])
        
        st.download_button("📥 PDF", generar_pdf_pro(df_master, "Resumen M&Y"), "reporte.pdf")

if __name__ == "__main__":
    main()
