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

def ejecutar_query(q, p=()):
    conn = sqlite3.connect("finanzas.db")
    cursor = conn.cursor()
    cursor.execute(q, p)
    conn.commit()
    conn.close()
    st.session_state.hay_cambios = True

def verificar_estructura_db():
    conn = sqlite3.connect("finanzas.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, Fecha TEXT, Monto REAL, Persona TEXT, Descripcion TEXT, Tarjeta TEXT, CuotasTotales INTEGER, CuotasPagadas INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos_fijos (id INTEGER PRIMARY KEY AUTOINCREMENT, Descripcion TEXT, Monto REAL, Persona TEXT, Cuenta TEXT, Activo BOOLEAN, MesesPagados TEXT)")
    c.execute("PRAGMA table_info(gastos_fijos)")
    cols = [col[1] for col in c.fetchall()]
    if 'Cuenta' not in cols: c.execute("ALTER TABLE gastos_fijos ADD COLUMN Cuenta TEXT DEFAULT 'DÉBITO'")
    if 'MesesPagados' not in cols: c.execute("ALTER TABLE gastos_fijos ADD COLUMN MesesPagados TEXT DEFAULT ''")
    if 'Activo' not in cols: c.execute("ALTER TABLE gastos_fijos ADD COLUMN Activo BOOLEAN DEFAULT 1")
    conn.commit()
    conn.close()

def inicializar_db():
    if 'db_cargada' not in st.session_state: st.session_state.db_cargada = False
    if 'hay_cambios' not in st.session_state: st.session_state.hay_cambios = False
    if 'editando' not in st.session_state: st.session_state.editando = None

    archivo_subido = st.sidebar.file_uploader("📂 Sube tu 'finanzas.db'", type="db")
    if archivo_subido and not st.session_state.db_cargada:
        with open("finanzas.db", "wb") as f: f.write(archivo_subido.getbuffer())
        verificar_estructura_db()
        st.session_state.db_cargada = True
        st.rerun()
    if not os.path.exists("finanzas.db"): verificar_estructura_db()

def float_a_uy(v):
    try: return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "0,00"

def generar_pdf_pro(df, titulo):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16); pdf.cell(0, 10, titulo, ln=True, align="C")
    pdf.ln(5)
    pdf.set_font("Arial", "B", 10); pdf.set_fill_color(230, 230, 230)
    cols = ["Fecha", "Descripcion", "Monto", "Persona", "Medio"]
    anchos = [25, 65, 30, 30, 40]
    for i, c in enumerate(cols): pdf.cell(anchos[i], 10, c, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font("Arial", "", 9)
    for _, r in df.iterrows():
        for i, c in enumerate(cols):
            val = str(r[c]) if c in r else ""
            pdf.cell(anchos[i], 8, val[:35], border=1)
        pdf.ln()
    return pdf.output(dest="S").encode("latin-1", "replace")

# --- APP PRINCIPAL ---
def main():
    inicializar_db()

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

    with t1:
        st.subheader("Registrar Movimiento")
        tipo = st.radio("Tipo:", ["Gasto Fijo / Débito", "Compra en Cuotas"], horizontal=True)
        with st.form("alta", clear_on_submit=True):
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
            with st.form("edit"):
                n_d = st.text_input("Desc", value=ed['desc'])
                n_m = st.number_input("Monto", value=float(ed['monto']))
                if st.form_submit_button("Actualizar"):
                    tabla = "gastos_fijos" if ed['tipo'] == 'fijo' else "gastos"
                    ejecutar_query(f"UPDATE {tabla} SET Descripcion=?, Monto=? WHERE id=?", (n_d, n_m, ed['id']))
                    st.session_state.editando = None
                    st.rerun()

        for m in ["DÉBITO", "SANTANDER", "BROU", "OCA"]:
            sf = df_f[df_f['Cuenta'] == m] if 'Cuenta' in df_f.columns else pd.DataFrame()
            sg = df_g[df_g['Tarjeta'] == m] if 'Tarjeta' in df_g.columns else pd.DataFrame()
            with st.expander(f"🏦 {m}"):
                for _, r in sf.iterrows():
                    c1, c2, c3 = st.columns([0.6, 0.2, 0.2])
                    c1.write(f"🏠 {r['Descripcion']}: ${float_a_uy(r['Monto'])}")
                    if c2.button("✏️", key=f"ef_{r['id']}"):
                        st.session_state.editando = {'id':r['id'], 'desc':r['Descripcion'], 'monto':r['Monto'], 'tipo':'fijo'}
                        st.rerun()
                    if c3.button("🗑️", key=f"df_{r['id']}"):
                        ejecutar_query("DELETE FROM gastos_fijos WHERE id=?", (r['id'],)); st.rerun()
                for _, r in sg.iterrows():
                    c1, c2, c3 = st.columns([0.6, 0.2, 0.2])
                    c1.write(f"💳 {r['Descripcion']}: ${float_a_uy(r['Monto'])}")
                    if c2.button("✏️", key=f"eg_{r['id']}"):
                        st.session_state.editando = {'id':r['id'], 'desc':r['Descripcion'], 'monto':r['Monto'], 'tipo':'cuota'}
                        st.rerun()
                    if c3.button("🗑️", key=f"dg_{r['id']}"):
                        ejecutar_query("DELETE FROM gastos WHERE id=?", (r['id'],)); st.rerun()

    with t3:
        st.subheader("Proyección a 6 Meses")
        inicio = datetime.today().replace(day=1)
        for i in range(6):
            mes = inicio + pd.DateOffset(months=i)
            sm, sy = 0.0, 0.0
            for _, r in df_f[df_f.get('Activo', 1) == 1].iterrows():
                if r['Persona'] == "Marcelo": sm += r['Monto']
                else: sy += r['Monto']
            for _, r in df_g.iterrows():
                if i < (r.get('CuotasTotales', 1) - r.get('CuotasPagadas', 0)):
                    if r['Persona'] == "Marcelo": sm += r['Monto']
                    else: sy += r['Monto']
            st.info(f"📅 {MESES_NOMBRE[mes.month]} {mes.year} | Marcelo: ${float_a_uy(sm)} | Yenny: ${float_a_uy(sy)} | Total: ${float_a_uy(sm+sy)}")

    with t4:
        st.subheader("Reportes")
        # --- Lógica Blindada para unificar tablas ---
        df_f_tmp = df_f.copy()
        df_f_tmp['Medio'] = df_f_tmp['Cuenta'] if 'Cuenta' in df_f_tmp.columns else "DÉBITO"
        df_f_tmp['Fecha'] = df_f_tmp['MesesPagados'] if 'MesesPagados' in df_f_tmp.columns else ""
        
        df_g_tmp = df_g.copy()
        df_g_tmp['Medio'] = df_g_tmp['Tarjeta'] if 'Tarjeta' in df_g_tmp.columns else "S/D"

        cols_final = ['Fecha', 'Descripcion', 'Monto', 'Persona', 'Medio']
        # Nos aseguramos que solo usamos columnas que existen
        master = pd.concat([df_f_tmp.reindex(columns=cols_final), df_g_tmp.reindex(columns=cols_final)])
        master = master.fillna("")

        if not master.empty:
            st.download_button("📥 Descargar PDF", generar_pdf_pro(master, "Reporte M&Y"), "reporte.pdf", use_container_width=True)
            st.download_button("📥 Descargar CSV", master.to_csv(index=False).encode('utf-8'), "datos.csv", "text/csv", use_container_width=True)

if __name__ == "__main__":
    main()
