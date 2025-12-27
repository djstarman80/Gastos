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

# --- FUNCIONES DE BASE DE DATOS Y PERSISTENCIA ---
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

    # Selector de archivo en la barra lateral
    st.sidebar.title("🔐 Acceso a Datos")
    archivo_subido = st.sidebar.file_uploader("Sube tu 'finanzas.db' para comenzar", type="db")
    
    if archivo_subido and not st.session_state.db_cargada:
        with open("finanzas.db", "wb") as f:
            f.write(archivo_subido.getbuffer())
        st.session_state.db_cargada = True
        st.sidebar.success("✅ Base de Datos cargada")
        st.rerun()

    # Estructura base si no existe
    if not os.path.exists("finanzas.db"):
        conn = sqlite3.connect("finanzas.db")
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, Fecha TEXT, Monto REAL, Persona TEXT, Descripcion TEXT, Tarjeta TEXT, CuotasTotales INTEGER, CuotasPagadas INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS gastos_fijos (id INTEGER PRIMARY KEY AUTOINCREMENT, Descripcion TEXT, Monto REAL, Persona TEXT, Cuenta TEXT, Activo BOOLEAN, MesesPagados TEXT)")
        conn.commit()
        conn.close()

def float_a_uy(v):
    return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- GENERADOR DE PDF ---
def generar_pdf_pro(df, titulo):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, titulo, ln=True, align="C")
    pdf.ln(5)
    pdf.set_font("Arial", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    anchos = [25, 65, 30, 30, 40]
    cols = ["Fecha", "Descripcion", "Monto", "Persona", "Medio"]
    for i, c in enumerate(cols): pdf.cell(anchos[i], 10, c, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font("Arial", "", 9)
    for _, r in df.iterrows():
        pdf.cell(anchos[0], 8, str(r["Fecha"]), border=1)
        pdf.cell(anchos[1], 8, str(r["Descripcion"])[:35], border=1)
        pdf.cell(anchos[2], 8, f"$ {float_a_uy(r['Monto'])}", border=1, align="R")
        pdf.cell(anchos[3], 8, str(r["Persona"]), border=1, align="C")
        pdf.cell(anchos[4], 8, str(r["Medio"]), border=1, align="C")
        pdf.ln()
    return pdf.output(dest="S").encode("latin-1", "replace")

# --- INTERFAZ PRINCIPAL ---
def main():
    inicializar_db()

    # Botón de Guardado Persistente para Celular
    if st.session_state.hay_cambios:
        st.warning("⚠️ Tienes cambios nuevos sin guardar en tu archivo.")
        with open("finanzas.db", "rb") as f:
            if st.download_button("💾 DESCARGAR Y ACTUALIZAR ARCHIVO EN CELULAR", f, "finanzas.db", use_container_width=True):
                st.session_state.hay_cambios = False
                st.rerun()

    conn = sqlite3.connect("finanzas.db")
    df_g = pd.read_sql_query("SELECT * FROM gastos", conn)
    df_f = pd.read_sql_query("SELECT * FROM gastos_fijos", conn)
    conn.close()

    t1, t2, t3, t4 = st.tabs(["➕ Nuevo", "📋 Cuentas", "📊 Proyección", "💾 Exportar"])

    # --- TAB 1: REGISTRO ---
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
            if st.form_submit_button("✅ GUARDAR GASTO"):
                f_hoy = datetime.today().strftime("%d/%m/%Y")
                if tipo == "Compra en Cuotas":
                    ejecutar_query("INSERT INTO gastos (Fecha, Monto, Persona, Descripcion, Tarjeta, CuotasTotales, CuotasPagadas) VALUES (?,?,?,?,?,?,?)", (f_hoy, monto, pers, desc, medio, cuotas, 0))
                else:
                    ejecutar_query("INSERT INTO gastos_fijos (Descripcion, Monto, Persona, Cuenta, Activo, MesesPagados) VALUES (?,?,?,?,?,?)", (desc, monto, pers, medio, 1, f_hoy))
                st.rerun()

    # --- TAB 2: CUENTAS (EDICIÓN Y ELIMINACIÓN) ---
    with t2:
        if st.session_state.editando:
            ed = st.session_state.editando
            st.info(f"📝 Editando: {ed['desc']}")
            with st.form("editor"):
                n_desc = st.text_input("Nueva Descripción", value=ed['desc'])
                n_monto = st.number_input("Nuevo Monto", value=float(ed['monto']))
                c_ed1, c_ed2 = st.columns(2)
                if c_ed1.form_submit_button("✅ Actualizar"):
                    tabla = "gastos_fijos" if ed['tipo'] == 'fijo' else "gastos"
                    ejecutar_query(f"UPDATE {tabla} SET Descripcion=?, Monto=? WHERE id=?", (n_desc, n_monto, ed['id']))
                    st.session_state.editando = None
                    st.rerun()
                if c_ed2.form_submit_button("❌ Cancelar"):
                    st.session_state.editando = None
                    st.rerun()

        for m in ["DÉBITO", "SANTANDER", "BROU", "OCA"]:
            sf = df_f[(df_f['Cuenta']==m) & (df_f['Activo']==1)]
            sg = df_g[df_g['Tarjeta']==m]
            total_medio = sf['Monto'].sum() + sg['Monto'].sum()
            with st.expander(f"🏦 {m} - Total: ${float_a_uy(total_medio)}"):
                for _, r in sf.iterrows():
                    ca, cb, cc = st.columns([0.6, 0.2, 0.2])
                    ca.write(f"🏠 {r['Descripcion']}: ${float_a_uy(r['Monto'])} ({r['Persona']})")
                    if cb.button("✏️", key=f"ef_{r['id']}"):
                        st.session_state.editando = {'id':r['id'], 'desc':r['Descripcion'], 'monto':r['Monto'], 'tipo':'fijo'}
                        st.rerun()
                    if cc.button("🗑️", key=f"df_{r['id']}"):
                        ejecutar_query("DELETE FROM gastos_fijos WHERE id=?", (r['id'],)); st.rerun()
                for _, r in sg.iterrows():
                    ca, cb, cc = st.columns([0.6, 0.2, 0.2])
                    ca.write(f"💳 {r['Descripcion']}: ${float_a_uy(r['Monto'])} ({r['Persona']})")
                    if cb.button("✏️", key=f"eg_{r['id']}"):
                        st.session_state.editando = {'id':r['id'], 'desc':r['Descripcion'], 'monto':r['Monto'], 'tipo':'cuota'}
                        st.rerun()
                    if cc.button("🗑️", key=f"dg_{r['id']}"):
                        ejecutar_query("DELETE FROM gastos WHERE id=?", (r['id'],)); st.rerun()

    # --- TAB 3: PROYECCIÓN ---
    with t3:
        st.subheader("Proyección a 6 Meses")
        inicio = datetime.today().replace(day=1)
        for i in range(6):
            mes = inicio + pd.DateOffset(months=i)
            sm, sy = 0.0, 0.0
            for _, r in df_f[df_f['Activo']==1].iterrows():
                if r['Persona'] == "Marcelo": sm += r['Monto']
                else: sy += r['Monto']
            for _, r in df_g.iterrows():
                if i < (r['CuotasTotales'] - r['CuotasPagadas']):
                    if r['Persona'] == "Marcelo": sm += r['Monto']
                    else: sy += r['Monto']
            st.info(f"📅 {MESES_NOMBRE[mes.month]} {mes.year} | Marcelo: ${float_a_uy(sm)} | Yenny: ${float_a_uy(sy)} | Total: ${float_a_uy(sm+sy)}")

    # --- TAB 4: EXPORTAR ---
    with t4:
        st.subheader("Reportes y Descargas")
        # Unificación para reporte
        df_f_m = df_f[df_f['Activo']==1][['MesesPagados', 'Descripcion', 'Monto', 'Persona', 'Cuenta']].rename(columns={'MesesPagados':'Fecha', 'Cuenta':'Medio'})
        df_g_m = df_g[['Fecha', 'Descripcion', 'Monto', 'Persona', 'Tarjeta']].rename(columns={'Tarjeta':'Medio'})
        df_master = pd.concat([df_f_m, df_g_m])
        
        if not df_master.empty:
            c_pdf, c_csv = st.columns(2)
            pdf_bytes = generar_pdf_pro(df_master, "Reporte Mensual M&Y")
            c_pdf.download_button("📥 DESCARGAR PDF", pdf_bytes, "reporte.pdf", "application/pdf", use_container_width=True)
            csv_data = df_master.to_csv(index=False).encode('utf-8')
            c_csv.download_button("📥 DESCARGAR EXCEL (CSV)", csv_data, "datos.csv", "text/csv", use_container_width=True)

if __name__ == "__main__":
    main()
