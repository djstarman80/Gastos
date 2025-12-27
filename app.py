import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import json
import os
from fpdf import FPDF

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Finanzas M&Y", layout="wide", page_icon="💰")

MESES_NOMBRE = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}

# --- FUNCIONES DE FORMATEO ---
def monto_uy_a_float(t):
    if not t: return 0.0
    try:
        if isinstance(t, str):
            s = t.replace("$", "").replace(".", "").replace(",", ".").strip()
            return float(s)
        return float(t)
    except: return 0.0

def float_a_monto_uy(v):
    try:
        return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "0,00"

# --- BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect("finanzas.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Fecha TEXT, Monto REAL, Persona TEXT, Descripcion TEXT, 
            CuotasTotales INTEGER, CuotasPagadas INTEGER, MesesPagados TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos_fijos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Descripcion TEXT, Monto REAL, Persona TEXT, Activo BOOLEAN, MesesPagados TEXT
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
    return df

# --- LÓGICA DE AUTOCIERRE ---
def aplicar_autocierre(dia_limite):
    hoy = datetime.today()
    if hoy.day >= dia_limite:
        mes_id = hoy.strftime("%Y-%m")
        conn = sqlite3.connect("finanzas.db")
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE gastos SET CuotasPagadas = CuotasPagadas + 1,
            MesesPagados = CASE WHEN MesesPagados='' OR MesesPagados IS NULL THEN ? ELSE MesesPagados||','||? END
            WHERE CuotasPagadas < CuotasTotales AND (MesesPagados NOT LIKE ? OR MesesPagados IS NULL)
        """, (mes_id, mes_id, f"%{mes_id}%"))
        cursor.execute("""
            UPDATE gastos_fijos SET 
            MesesPagados = CASE WHEN MesesPagados='' OR MesesPagados IS NULL THEN ? ELSE MesesPagados||','||? END
            WHERE Activo=1 AND (MesesPagados NOT LIKE ? OR MesesPagados IS NULL)
        """, (mes_id, mes_id, f"%{mes_id}%"))
        conn.commit()
        conn.close()

# --- INTERFAZ PRINCIPAL ---
def main():
    init_db()
    
    st.sidebar.title("⚙️ Ajustes")
    dia_cierre = st.sidebar.slider("Día de Autocierre", 1, 28, 10)
    aplicar_autocierre(dia_cierre)

    tab1, tab2, tab3, tab4 = st.tabs(["➕ Ingreso", "📋 Gestión", "📊 Pagos Futuros", "💾 Respaldo y Reportes"])

    # --- TAB 1: INGRESO ---
    with tab1:
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Gasto por Cuotas")
            with st.form("f_cuotas"):
                desc = st.text_input("Descripción")
                monto_cuota = st.text_input("Valor de CADA CUOTA ($)")
                cuotas_t = st.number_input("Cantidad de cuotas", 1, 36, 1)
                pers = st.selectbox("A nombre de:", ["Marcelo", "Yenny"], key="p1")
                if st.form_submit_button("Guardar Gasto"):
                    conn = sqlite3.connect("finanzas.db")
                    conn.execute("INSERT INTO gastos (Fecha, Monto, Persona, Descripcion, CuotasTotales, CuotasPagadas, MesesPagados) VALUES (?,?,?,?,?,?,?)",
                                 (datetime.today().strftime("%d/%m/%Y"), monto_uy_a_float(monto_cuota), pers, desc, cuotas_t, 0, ""))
                    conn.commit()
                    st.success("Gasto guardado")
                    st.rerun()
        with col_b:
            st.subheader("Gasto Fijo (Mensual)")
            with st.form("f_fijo"):
                desc_f = st.text_input("Descripción")
                monto_f = st.text_input("Monto Mensual ($)")
                pers_f = st.selectbox("A nombre de:", ["Marcelo", "Yenny"], key="p2")
                if st.form_submit_button("Guardar Fijo"):
                    conn = sqlite3.connect("finanzas.db")
                    conn.execute("INSERT INTO gastos_fijos (Descripcion, Monto, Persona, Activo, MesesPagados) VALUES (?,?,?,?,?)",
                                 (desc_f, monto_uy_a_float(monto_f), pers_f, 1, ""))
                    conn.commit()
                    st.success("Fijo guardado")
                    st.rerun()

    # --- TAB 2: GESTIÓN ---
    with tab2:
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.write("### Cuotas Activas")
            df_g = cargar_datos()
            for _, r in df_g.iterrows():
                with st.expander(f"{r['Descripcion']} - {r['Persona']} (${float_a_monto_uy(r['Monto'])})"):
                    st.write(f"Pago: {r['CuotasPagadas']}/{r['CuotasTotales']}")
                    if st.button(f"Borrar ID {r['id']}", key=f"dg{r['id']}"):
                        conn = sqlite3.connect("finanzas.db"); conn.execute("DELETE FROM gastos WHERE id=?", (r['id'],)); conn.commit(); st.rerun()
        with col_g2:
            st.write("### Gastos Fijos")
            df_f = cargar_gastos_fijos()
            for _, r in df_f.iterrows():
                with st.expander(f"{r['Descripcion']} - {r['Persona']} ({'✅' if r['Activo'] else '❌'})"):
                    if st.button("Alternar Activo", key=f"tf{r['id']}"):
                        nuevo = 0 if r['Activo'] else 1
                        conn = sqlite3.connect("finanzas.db"); conn.execute("UPDATE gastos_fijos SET Activo=? WHERE id=?", (nuevo, r['id'])); conn.commit(); st.rerun()
                    if st.button("Eliminar", key=f"df{r['id']}"):
                        conn = sqlite3.connect("finanzas.db"); conn.execute("DELETE FROM gastos_fijos WHERE id=?", (r['id'],)); conn.commit(); st.rerun()

    # --- LÓGICA DE PROYECCIÓN (REUTILIZABLE) ---
    hoy = datetime.today()
    inicio_p = hoy.replace(day=1) + pd.DateOffset(months=1) if hoy.day >= dia_cierre else hoy.replace(day=1)
    
    proyeccion = []
    df_g_act = cargar_datos()
    df_f_act = cargar_gastos_fijos()
    for i in range(12):
        mes_f = inicio_p + pd.DateOffset(months=i)
        sm, sy = 0.0, 0.0
        for _, f in df_f_act[df_f_act['Activo']==1].iterrows():
            if f['Persona'] == "Marcelo": sm += f['Monto']
            else: sy += f['Monto']
        for _, g in df_g_act.iterrows():
            if i < (g['CuotasTotales'] - g['CuotasPagadas']):
                if g['Persona'] == "Marcelo": sm += g['Monto']
                else: sy += g['Monto']
        proyeccion.append({"Mes": f"{MESES_NOMBRE[mes_f.month]} '{str(mes_f.year)[2:]}", "Marcelo": f"${float_a_monto_uy(sm)}", "Yenny": f"${float_a_monto_uy(sy)}", "Total Mes": f"${float_a_monto_uy(sm+sy)}"})

    # --- TAB 3: PAGOS FUTUROS ---
    with tab3:
        st.header(f"Pagos: {MESES_NOMBRE[hoy.month]}")
        st.table(pd.DataFrame(proyeccion))
        st.divider()
        tm = sum([monto_uy_a_float(x['Marcelo']) for x in proyeccion]) / 12
        ty = sum([monto_uy_a_float(x['Yenny']) for x in proyeccion]) / 12
        c1, c2, c3 = st.columns(3); c1.metric("Promedio Marcelo", f"${float_a_monto_uy(tm)}"); c2.metric("Promedio Yenny", f"${float_a_monto_uy(ty)}"); c3.metric("Total", f"${float_a_monto_uy(tm+ty)}")

    # --- TAB 4: RESPALDO Y REPORTES ---
    with tab4:
        st.header("Herramientas de Datos")
        c_r1, c_r2 = st.columns(2)
        with c_r1:
            st.subheader("📄 Exportar PDF")
            if st.button("Generar Reporte 12 Meses"):
                pdf = FPDF()
                pdf.add_page(); pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, "Proyeccion Financiera M&Y", 0, 1, "C"); pdf.ln(5)
                pdf.set_font("Arial", "B", 10); pdf.cell(40, 8, "Mes", 1); pdf.cell(50, 8, "Marcelo", 1); pdf.cell(50, 8, "Yenny", 1); pdf.cell(50, 8, "Total", 1); pdf.ln()
                pdf.set_font("Arial", "", 10)
                for f in proyeccion:
                    pdf.cell(40, 8, f["Mes"], 1); pdf.cell(50, 8, f["Marcelo"], 1); pdf.cell(50, 8, f["Yenny"], 1); pdf.cell(50, 8, f["Total Mes"], 1); pdf.ln()
                st.download_button("Descargar PDF", pdf.output(dest='S').encode('latin-1'), "Reporte.pdf", "application/pdf")
        with c_r2:
            st.subheader("💾 Backup")
            if os.path.exists("finanzas.db"):
                with open("finanzas.db", "rb") as f:
                    st.download_button("Descargar Base de Datos (.db)", f, "finanzas.db")

if __name__ == "__main__":
    main()
