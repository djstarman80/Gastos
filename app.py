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

# --- FUNCIONES DE BASE DE DATOS (REPARACIÓN, RENOMBRE Y CONSULTA) ---
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
    
    # 1. Asegurar existencia de tablas
    c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, Fecha TEXT, Monto REAL, Persona TEXT, Descripcion TEXT, Tarjeta TEXT, CuotasTotales INTEGER, CuotasPagadas INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos_fijos (id INTEGER PRIMARY KEY AUTOINCREMENT, Descripcion TEXT, Monto REAL, Persona TEXT, Cuenta TEXT, Activo BOOLEAN, MesesPagados TEXT)")
    
    # 2. Reparar columnas faltantes
    c.execute("PRAGMA table_info(gastos_fijos)")
    cols_fijos = [col[1] for col in c.fetchall()]
    if 'Cuenta' not in cols_fijos: c.execute("ALTER TABLE gastos_fijos ADD COLUMN Cuenta TEXT DEFAULT 'DÉBITO'")
    
    # 3. RENOMBRAR "otra" o "Otros" a "DÉBITO" (REGLA SOLICITADA)
    # Lo hacemos en ambas tablas para que todo quede unificado
    c.execute("UPDATE gastos_fijos SET Cuenta = 'DÉBITO' WHERE LOWER(Cuenta) IN ('otra', 'otros', 'otra ', 'otros ')")
    c.execute("UPDATE gastos SET Tarjeta = 'DÉBITO' WHERE LOWER(Tarjeta) IN ('otra', 'otros', 'otra ', 'otros ')")
    
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
        # Si se renombraron cosas al subir, marcamos que hay cambios para descargar
        st.session_state.hay_cambios = True 
        st.rerun()
    if not os.path.exists("finanzas.db"): verificar_y_reparar_db()

def float_a_uy(v):
    try: return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "0,00"

def generar_pdf_pro(df, titulo):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16); pdf.cell(0, 10, titulo, ln=True, align="C")
    pdf.ln(5)
    cols = ["Fecha", "Descripcion", "Monto", "Persona", "Medio"]
    anchos = [25, 65, 30, 30, 40]
    pdf.set_font("Arial", "B", 10); pdf.set_fill_color(230, 230, 230)
    for i, c in enumerate(cols): pdf.cell(anchos[i], 10, c, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font("Arial", "", 9)
    for _, r in df.iterrows():
        for i, c in enumerate(cols):
            val = str(r.get(c, ""))
            pdf.cell(anchos[i], 8, val[:30], border=1)
        pdf.ln()
    return pdf.output(dest="S").encode("latin-1", "replace")

# --- CUERPO DE LA APP ---
def main():
    inicializar_estado()
    manejar_db()

    # Botón de guardado para persistencia en celular
    if st.session_state.hay_cambios:
        st.info("💡 Se han actualizado datos (como el renombre de 'Otros' a 'DÉBITO').")
        with open("finanzas.db", "rb") as f:
            if st.download_button("💾 DESCARGAR Y ACTUALIZAR DB", f, "finanzas.db", use_container_width=True):
                st.session_state.hay_cambios = False
                st.rerun()

    conn = sqlite3.connect("finanzas.db")
    df_g = pd.read_sql_query("SELECT * FROM gastos", conn)
    df_f = pd.read_sql_query("SELECT * FROM gastos_fijos", conn)
    conn.close()

    t1, t2, t3, t4 = st.tabs(["➕ NUEVO", "📋 CUENTAS", "📊 PROYECCIÓN", "💾 EXPORTAR"])

    # 1. REGISTRO
    with t1:
        st.subheader("Registrar Movimiento")
        tipo = st.radio("Clase:", ["Débito / Fijo", "Compra en Cuotas"], horizontal=True)
        with st.form("alta", clear_on_submit=True):
            d = st.text_input("Descripción")
            m = st.number_input("Monto ($)", min_value=0.0)
            p = st.selectbox("Responsable", ["Marcelo", "Yenny"])
            medio = st.selectbox("Medio de Pago", ["DÉBITO", "SANTANDER", "BROU", "OCA"])
            c_totales = st.number_input("Cuotas totales", 1, 48, 1) if tipo == "Compra en Cuotas" else 1
            if st.form_submit_button("✅ GUARDAR"):
                f = datetime.today().strftime("%d/%m/%Y")
                if tipo == "Compra en Cuotas":
                    ejecutar_query("INSERT INTO gastos (Fecha, Monto, Persona, Descripcion, Tarjeta, CuotasTotales, CuotasPagadas) VALUES (?,?,?,?,?,?,?)", (f, m, p, d, medio, c_totales, 0))
                else:
                    ejecutar_query("INSERT INTO gastos_fijos (Descripcion, Monto, Persona, Cuenta, Activo, MesesPagados) VALUES (?,?,?,?,?,?)", (d, m, p, medio, 1, f))
                st.rerun()

    # 2. CUENTAS (EDITAR / ELIMINAR)
    with t2:
        if st.session_state.editando:
            ed = st.session_state.editando
            with st.form("editor"):
                n_d = st.text_input("Descripción", value=ed['desc'])
                n_m = st.number_input("Monto", value=float(ed['monto']))
                n_p = st.selectbox("Persona", ["Marcelo", "Yenny"], index=0 if ed['persona']=="Marcelo" else 1)
                n_medio = st.selectbox("Medio", ["DÉBITO", "SANTANDER", "BROU", "OCA"], index=0)
                if st.form_submit_button("✅ ACTUALIZAR"):
                    tabla = "gastos_fijos" if ed['tipo'] == 'fijo' else "gastos"
                    col_medio = "Cuenta" if ed['tipo'] == 'fijo' else "Tarjeta"
                    ejecutar_query(f"UPDATE {tabla} SET Descripcion=?, Monto=?, Persona=?, {col_medio}=? WHERE id=?", (n_d, n_m, n_p, n_medio, ed['id']))
                    st.session_state.editando = None
                    st.rerun()

        # Medios dinámicos (esto mostrará DÉBITO, SANTANDER, etc.)
        medios_f = df_f['Cuenta'].unique().tolist() if 'Cuenta' in df_f.columns else []
        medios_v = df_g['Tarjeta'].unique().tolist() if 'Tarjeta' in df_g.columns else []
        todos_medios = sorted(list(set(medios_f + medios_v + ["DÉBITO", "SANTANDER", "BROU", "OCA"])))

        for m in todos_medios:
            sf = df_f[df_f['Cuenta'] == m] if 'Cuenta' in df_f.columns else pd.DataFrame()
            sg = df_g[df_g['Tarjeta'] == m] if 'Tarjeta' in df_g.columns else pd.DataFrame()
            if not sf.empty or not sg.empty:
                total_m = sf['Monto'].sum() + sg['Monto'].sum()
                with st.expander(f"🏦 {m} - Total: ${float_a_uy(total_m)}"):
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

    # 3. PROYECCIÓN
    with t3:
        st.subheader("Proyección Mensual")
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

    # 4. EXPORTAR
    with t4:
        st.subheader("Exportar")
        df_f_exp = df_f.copy().rename(columns={'Cuenta':'Medio', 'MesesPagados':'Fecha'})
        df_g_exp = df_g.copy().rename(columns={'Tarjeta':'Medio'})
        master = pd.concat([df_f_exp, df_g_exp], ignore_index=True).reindex(columns=['Fecha', 'Descripcion', 'Monto', 'Persona', 'Medio']).fillna("S/D")
        if not master.empty:
            st.download_button("📥 PDF PROFESIONAL", generar_pdf_pro(master, "Resumen Finanzas M&Y"), "reporte_my.pdf", use_container_width=True)

if __name__ == "__main__":
    main()
