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
    s = str(t).strip().replace("$", "").replace(" ", "")
    if not s: return 0.0
    try:
        if "," in s and "." in s: s = s.replace(".", "").replace(",", ".")
        elif "," in s: s = s.replace(",", ".")
        return float(s)
    except: return 0.0

def float_a_monto_uy(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return "0,00"
    try:
        v = float(v)
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return str(v)

def limpiar_texto_pdf(texto):
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

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
            CuentaDebito TEXT, FechaInicio TEXT, FechaFin TEXT,
            Activo BOOLEAN, Variaciones TEXT, Distribucion TEXT, MesesPagados TEXT
        )
    """)
    conn.commit()
    conn.close()

def cargar_datos():
    conn = sqlite3.connect("finanzas.db")
    df = pd.read_sql_query("SELECT * FROM gastos", conn)
    conn.close()
    if not df.empty:
        df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
    return df

def cargar_gastos_fijos():
    conn = sqlite3.connect("finanzas.db")
    df = pd.read_sql_query("SELECT * FROM gastos_fijos", conn)
    conn.close()
    if not df.empty:
        df['Variaciones'] = df['Variaciones'].apply(lambda x: json.loads(x) if x else {})
        df['Distribucion'] = df['Distribucion'].apply(lambda x: json.loads(x) if x else {"Marcelo": 50, "Yenny": 50})
        df['Activo'] = df['Activo'].astype(bool)
    return df

# --- CLASE PDF ---
class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Reporte Financiero - Marcelo & Yenny', 0, 1, 'C')
        self.ln(5)

    def generar_tabla(self, titulo, headers, datos, col_widths):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, limpiar_texto_pdf(titulo), 0, 1, 'L')
        self.set_font('Arial', 'B', 10)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 10, h, 1, 0, 'C')
        self.ln()
        self.set_font('Arial', '', 9)
        for fila in datos:
            for i, dato in enumerate(fila):
                self.cell(col_widths[i], 8, limpiar_texto_pdf(dato), 1, 0, 'L')
            self.ln()
        self.ln(5)

# --- INTERFAZ PRINCIPAL ---
def main():
    init_db()
    
    if 'df_gastos' not in st.session_state: st.session_state.df_gastos = cargar_datos()
    if 'df_fijos' not in st.session_state: st.session_state.df_fijos = cargar_gastos_fijos()

    st.sidebar.title("⚙️ Sistema M&Y")
    if st.sidebar.button("🔄 Refrescar Datos"):
        st.session_state.df_gastos = cargar_datos()
        st.session_state.df_fijos = cargar_gastos_fijos()
        st.rerun()

    tab_ingreso, tab_gastos, tab_fijos, tab_pagos = st.tabs(["➕ Ingreso", "📋 Gastos", "💳 Fijos", "⏰ Pagos Futuros"])

    # --- TAB INGRESO ---
    with tab_ingreso:
        tipo = st.radio("Tipo de gasto:", ["Normal (Tarjeta/Efectivo)", "Fijo (Mensual)"], horizontal=True)
        with st.form("form_nuevo"):
            col1, col2 = st.columns(2)
            desc = col1.text_input("Descripción")
            monto = col2.text_input("Monto", "0,00")
            cat = col1.selectbox("Categoría", ["Supermercado", "Servicios", "Salidas", "Educación", "Salud", "Hogar", "Otros"])
            pers = col2.selectbox("Persona", ["Marcelo", "Yenny", "Ambos"])
            
            if "Normal" in tipo:
                fecha = st.date_input("Fecha", datetime.today())
                tarjeta = st.selectbox("Medio de Pago", ["BROU", "Santander", "OCA", "Efectivo", "Transferencia"])
                cuotas = st.number_input("Cuotas Totales", 1, 36, 1)
                if st.form_submit_button("💾 Guardar Gasto"):
                    conn = sqlite3.connect("finanzas.db")
                    conn.execute("INSERT INTO gastos (Fecha, Monto, Categoria, Persona, Descripcion, Tarjeta, CuotasTotales, CuotasPagadas, MesesPagados) VALUES (?,?,?,?,?,?,?,?,?)",
                                 (fecha.strftime("%d/%m/%Y"), monto_uy_a_float(monto), cat, pers, desc, tarjeta, cuotas, 0, ""))
                    conn.commit()
                    conn.close()
                    st.success("Gasto guardado")
                    st.rerun()
            else:
                cuenta = st.selectbox("Cuenta Débito", ["BROU", "Santander", "OCA", "Otra"])
                if st.form_submit_button("💾 Guardar Gasto Fijo"):
                    conn = sqlite3.connect("finanzas.db")
                    conn.execute("INSERT INTO gastos_fijos (Descripcion, Monto, Categoria, Persona, CuentaDebito, FechaInicio, Activo, Variaciones, Distribucion, MesesPagados) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                 (desc, monto_uy_a_float(monto), cat, pers, cuenta, datetime.today().strftime("%d/%m/%Y"), 1, "{}", json.dumps({"Marcelo":50, "Yenny":50}), ""))
                    conn.commit()
                    conn.close()
                    st.success("Gasto fijo guardado")
                    st.rerun()

    # --- TAB GASTOS ---
    with tab_gastos:
        df = cargar_datos()
        if not df.empty:
            st.dataframe(df.sort_values("id", ascending=False), use_container_width=True)
            col_e, col_b = st.columns(2)
            with col_b:
                id_del = st.number_input("ID a eliminar", min_value=0, step=1, key="del_n")
                if st.button("🗑️ Eliminar Gasto"):
                    conn = sqlite3.connect("finanzas.db")
                    conn.execute("DELETE FROM gastos WHERE id=?", (id_del,))
                    conn.commit()
                    conn.close()
                    st.rerun()

    # --- TAB FIJOS ---
    with tab_fijos:
        df_f = cargar_gastos_fijos()
        if not df_f.empty:
            st.dataframe(df_f[["id", "Descripcion", "Monto", "Persona", "Activo"]], use_container_width=True)
            id_f_edit = st.number_input("ID Fijo para Editar/Activar", min_value=0, step=1)
            if id_f_edit in df_f['id'].values:
                f_curr = df_f[df_f['id'] == id_f_edit].iloc[0]
                with st.form("edit_fijo"):
                    nf_act = st.checkbox("Activo", value=f_curr['Activo'])
                    nf_monto = st.text_input("Monto mensual", float_a_monto_uy(f_curr['Monto']))
                    if st.form_submit_button("Actualizar Gasto Fijo"):
                        conn = sqlite3.connect("finanzas.db")
                        conn.execute("UPDATE gastos_fijos SET Activo=?, Monto=? WHERE id=?", (nf_act, monto_uy_a_float(nf_monto), id_f_edit))
                        conn.commit()
                        conn.close()
                        st.rerun()

    # --- TAB PAGOS FUTUROS (MEJORADA) ---
    with tab_pagos:
        hoy = datetime.today()
        mes_actual_id = hoy.strftime("%Y-%m")
        st.header(f"📅 Gestión de Pagos: {MESES_NUMERO[hoy.month]}")

        # 1. Pendientes del Mes
        pend_norm = st.session_state.df_gastos[(st.session_state.df_gastos['CuotasPagadas'] < st.session_state.df_gastos['CuotasTotales']) & (~st.session_state.df_gastos['MesesPagados'].str.contains(mes_actual_id, na=False))].copy()
        pend_fij = st.session_state.df_fijos[(st.session_state.df_fijos['Activo'] == True) & (~st.session_state.df_fijos['MesesPagados'].str.contains(mes_actual_id, na=False))].copy()

        if not pend_norm.empty or not pend_fij.empty:
            st.subheader("⚠️ Pendientes de liquidar este mes")
            c1, c2 = st.columns(2)
            with c1: st.write("Cuotas:"); st.dataframe(pend_norm[["Descripcion", "Monto", "Persona"]], hide_index=True)
            with c2: st.write("Fijos:"); st.dataframe(pend_fij[["Descripcion", "Monto", "Persona"]], hide_index=True)
            
            if st.button("✅ Marcar todo el mes como pagado", type="primary", use_container_width=True):
                conn = sqlite3.connect("finanzas.db")
                cursor = conn.cursor()
                for _, r in pend_norm.iterrows():
                    m_pagados = (str(r['MesesPagados']) + f",{mes_actual_id}").strip(',')
                    cursor.execute("UPDATE gastos SET CuotasPagadas=CuotasPagadas+1, MesesPagados=? WHERE id=?", (m_pagados, r['id']))
                for _, r in pend_fij.iterrows():
                    m_pagados = (str(r['MesesPagados']) + f",{mes_actual_id}").strip(',')
                    cursor.execute("UPDATE gastos_fijos SET MesesPagados=? WHERE id=?", (m_pagados, r['id']))
                conn.commit()
                conn.close()
                st.rerun()
        else:
            st.success("🎉 ¡Todo al día! No hay pagos pendientes para este mes.")

        st.divider()

        # 2. Proyección 12 Meses por Persona
        st.subheader("📊 Proyección de Aportes Marcelo vs Yenny")
        inicio_p = hoy.replace(day=1) if (not pend_norm.empty or not pend_fij.empty) else (hoy.replace(day=1) + pd.DateOffset(months=1))
        
        proyeccion_list = []
        for i in range(12):
            mes_f = inicio_p + pd.DateOffset(months=i)
            m_marcelo, m_yenny = 0.0, 0.0
            
            # Sumar Fijos
            for _, f in st.session_state.df_fijos[st.session_state.df_fijos['Activo'] == True].iterrows():
                m = float(f['Monto'])
                if f['Persona'] == "Marcelo": m_marcelo += m
                elif f['Persona'] == "Yenny": m_yenny += m
                else: 
                    m_marcelo += m * (f['Distribucion'].get('Marcelo', 50)/100)
                    m_yenny += m * (f['Distribucion'].get('Yenny', 50)/100)
            
            # Sumar Cuotas
            for _, g in st.session_state.df_gastos.iterrows():
                if i < (g['CuotasTotales'] - g['CuotasPagadas']):
                    cuota = float(g['Monto']) / g['CuotasTotales']
                    if g['Persona'] == "Marcelo": m_marcelo += cuota
                    elif g['Persona'] == "Yenny": m_yenny += cuota
                    else: m_marcelo += cuota*0.5; m_yenny += cuota*0.5

            proyeccion_list.append({"Mes": f"{MESES_NUMERO[mes_f.month]} '{str(mes_f.year)[2:]}", "Marcelo": f"${float_a_monto_uy(m_marcelo)}", "Yenny": f"${float_a_monto_uy(m_yenny)}", "Total": f"${float_a_monto_uy(m_marcelo+m_yenny)}"})
        
        df_proy = pd.DataFrame(proyeccion_list)
        st.table(df_proy)

        # 3. Exportar PDF
        if st.button("📄 Descargar Proyección en PDF", use_container_width=True):
            pdf = PDFReport()
            pdf.add_page()
            pdf.generar_tabla("Proyeccion de Aportes", ["Mes", "Marcelo", "Yenny", "Total"], [list(d.values()) for d in proyeccion_list], [40, 50, 50, 50])
            st.download_button("⬇️ Click para Descargar", pdf.output(dest='S').encode('latin-1', 'replace'), "proyeccion.pdf", "application/pdf")

if __name__ == "__main__":
    main()
