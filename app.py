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

# --- FUNCIONES DE APOYO ---
def ejecutar_query(q, p=()):
    conn = sqlite3.connect("finanzas.db")
    cursor = conn.cursor()
    cursor.execute(q, p)
    conn.commit()
    conn.close()

def float_a_uy(v):
    return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def generar_pdf_pro(df, titulo_reporte):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, titulo_reporte, ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 10, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
    pdf.ln(5)

    # Encabezados
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(230, 230, 230)
    anchos = [25, 65, 30, 30, 40]
    cols = ["Fecha", "Descripcion", "Monto", "Persona", "Medio"]
    for i, c in enumerate(cols):
        pdf.cell(anchos[i], 8, c, border=1, fill=True, align="C")
    pdf.ln()

    # Filas
    pdf.set_font("Arial", "", 8)
    for _, r in df.iterrows():
        pdf.cell(anchos[0], 7, str(r["Fecha"]), border=1)
        pdf.cell(anchos[1], 7, str(r["Descripcion"])[:35], border=1)
        pdf.cell(anchos[2], 7, f"$ {float_a_uy(r['Monto'])}", border=1, align="R")
        pdf.cell(anchos[3], 7, str(r["Persona"]), border=1)
        pdf.cell(anchos[4], 7, str(r["Medio"]), border=1)
        pdf.ln()

    # Resumen Final
    pdf.ln(10)
    pdf.set_font("Arial", "B", 11)
    m_tot = df[df['Persona'] == 'Marcelo']['Monto'].sum()
    y_tot = df[df['Persona'] == 'Yenny']['Monto'].sum()
    pdf.cell(0, 8, f"Resumen por Persona:", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 7, f"Marcelo: $ {float_a_uy(m_tot)}", ln=True)
    pdf.cell(0, 7, f"Yenny: $ {float_a_uy(y_tot)}", ln=True)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 10, f"TOTAL GENERAL: $ {float_a_uy(m_tot + y_tot)}", ln=True)
    
    return pdf.output(dest="S").encode("latin-1", "replace")

def main():
    # 1. Asegurar estructura de base de datos (Solución al KeyError)
    conn = sqlite3.connect("finanzas.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, Fecha TEXT, Monto REAL, Persona TEXT, Descripcion TEXT, Tarjeta TEXT, CuotasTotales INTEGER, CuotasPagadas INTEGER, MesesPagados TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos_fijos (id INTEGER PRIMARY KEY AUTOINCREMENT, Descripcion TEXT, Monto REAL, Persona TEXT, Cuenta TEXT, Activo BOOLEAN, MesesPagados TEXT)")
    
    c.execute("PRAGMA table_info(gastos_fijos)")
    cols_f = [col[1] for col in c.fetchall()]
    if 'MesesPagados' not in cols_f:
        c.execute("ALTER TABLE gastos_fijos ADD COLUMN MesesPagados TEXT DEFAULT ''")
    if 'Cuenta' not in cols_f:
        c.execute("ALTER TABLE gastos_fijos ADD COLUMN Cuenta TEXT DEFAULT 'DÉBITO'")
    
    conn.commit()
    conn.close()

    # 2. Cargar datos
    conn = sqlite3.connect("finanzas.db")
    df_g = pd.read_sql_query("SELECT * FROM gastos", conn)
    df_f = pd.read_sql_query("SELECT * FROM gastos_fijos", conn)
    conn.close()

    st.sidebar.title("Configuración")
    dia_cierre = st.sidebar.slider("Día de cierre tarjeta", 1, 28, 10)

    t1, t2, t3, t4 = st.tabs(["➕ Nuevo", "📋 Mis Cuentas", "📊 Proyección", "💾 Exportar y Backup"])

    # --- TAB 1: NUEVO ---
    with t1:
        st.subheader("Registrar Movimiento")
        tipo = st.radio("Tipo:", ["Gasto Fijo / Débito", "Compra en Cuotas"], horizontal=True)
        with st.form("f_nuevo", clear_on_submit=True):
            col1, col2 = st.columns(2)
            desc = col1.text_input("Descripción")
            monto = col2.number_input("Valor de la Cuota o Monto ($)", min_value=0.0)
            pers = col1.selectbox("Persona", ["Marcelo", "Yenny"])
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
                st.success("Guardado correctamente")
                st.rerun()

    # --- TAB 2: CUENTAS ---
    with t2:
        st.subheader("Estado Actual")
        m_tot_m = df_f[(df_f['Activo']==1) & (df_f['Persona']=='Marcelo')]['Monto'].sum() + df_g[df_g['Persona']=='Marcelo']['Monto'].sum()
        m_tot_y = df_f[(df_f['Activo']==1) & (df_f['Persona']=='Yenny')]['Monto'].sum() + df_g[df_g['Persona']=='Yenny']['Monto'].sum()
        
        c1, c2 = st.columns(2)
        c1.metric("Total Marcelo", f"$ {float_a_uy(m_tot_m)}")
        c2.metric("Total Yenny", f"$ {float_a_uy(m_tot_y)}")

        for m in ["DÉBITO", "SANTANDER", "BROU", "OCA"]:
            with st.expander(f"🏦 {m}"):
                sf = df_f[(df_f['Cuenta']==m) & (df_f['Activo']==1)]
                sg = df_g[df_g['Tarjeta']==m]
                for _, r in sf.iterrows():
                    st.write(f"🏠 {r['Descripcion']}: ${float_a_uy(r['Monto'])} ({r['Persona']})")
                for _, r in sg.iterrows():
                    st.write(f"💳 {r['Descripcion']}: ${float_a_uy(r['Monto'])} ({r['Persona']})")

    # --- TAB 3: PROYECCIÓN (RESTAURADA) ---
    with t3:
        st.subheader("Proyección a 6 Meses")
        hoy = datetime.today()
        # Ajuste por día de cierre
        inicio = hoy.replace(day=1) + pd.DateOffset(months=1) if hoy.day >= dia_cierre else hoy.replace(day=1)
        
        for i in range(6):
            mes_f = inicio + pd.DateOffset(months=i)
            suma_m, suma_y = 0.0, 0.0
            
            # Sumar fijos activos
            for _, r in df_f[df_f['Activo']==1].iterrows():
                if r['Persona'] == "Marcelo": suma_m += r['Monto']
                else: suma_y += r['Monto']
            
            # Sumar cuotas pendientes
            for _, r in df_g.iterrows():
                if i < (r['CuotasTotales'] - r['CuotasPagadas']):
                    if r['Persona'] == "Marcelo": suma_m += r['Monto']
                    else: suma_y += r['Monto']
            
            with st.container(border=True):
                col_m, col_t = st.columns([1, 2])
                col_m.write(f"### {MESES_NOMBRE[mes_f.month]} {mes_f.year}")
                col_t.write(f"Marcelo: **${float_a_uy(suma_m)}** | Yenny: **${float_a_uy(suma_y)}** | **Total: ${float_a_uy(suma_m+suma_y)}**")

    # --- TAB 4: EXPORTAR ---
    with t4:
        st.subheader("Generar Reporte PDF")
        df_f_act = df_f[df_f['Activo'] == 1].copy()
        
        # Normalizar columna fecha para fijos
        if 'MesesPagados' in df_f_act.columns:
            df_f_act = df_f_act.rename(columns={'MesesPagados': 'Fecha'})
        else:
            df_f_act['Fecha'] = datetime.today().strftime("%d/%m/%Y")
            
        df_f_exp = df_f_act[['Fecha', 'Descripcion', 'Monto', 'Persona', 'Cuenta']].rename(columns={'Cuenta':'Medio'})
        df_g_exp = df_g[['Fecha', 'Descripcion', 'Monto', 'Persona', 'Tarjeta']].rename(columns={'Tarjeta':'Medio'})
        df_master = pd.concat([df_f_exp, df_g_exp])

        p_rep = st.multiselect("Incluir en reporte:", ["Marcelo", "Yenny"], default=["Marcelo", "Yenny"])
        df_rep = df_master[df_master['Persona'].isin(p_rep)]

        if not df_rep.empty:
            pdf_data = generar_pdf_pro(df_rep, "Reporte Mensual M&Y")
            st.download_button("📥 DESCARGAR PDF", pdf_data, f"Reporte_{datetime.now().strftime('%m_%y')}.pdf", "application/pdf")
            st.dataframe(df_rep)

if __name__ == "__main__":
    main()
