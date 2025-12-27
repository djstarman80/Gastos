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

# --- FUNCIONES DE BASE DE DATOS ---
def ejecutar_query(q, p=()):
    conn = sqlite3.connect("finanzas.db")
    cursor = conn.cursor()
    cursor.execute(q, p)
    conn.commit()
    conn.close()

def float_a_uy(v):
    return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- GENERADOR DE PDF PROFESIONAL ---
def generar_pdf_pro(df, titulo_reporte):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado
    pdf.set_font("Arial", "B", 18)
    pdf.set_text_color(33, 37, 41)
    pdf.cell(0, 15, f"Reporte: {titulo_reporte}", ln=True, align="C")
    
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 5, f"Fecha de emision: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
    pdf.ln(10)

    # Tabla de Gastos
    pdf.set_font("Arial", "B", 10)
    pdf.set_fill_color(52, 58, 64) # Gris oscuro
    pdf.set_text_color(255, 255, 255) # Blanco
    
    columnas = ["Fecha", "Descripcion", "Monto", "Persona", "Medio"]
    anchos = [25, 65, 30, 30, 40]
    
    for i, col in enumerate(columnas):
        pdf.cell(anchos[i], 10, col, border=1, fill=True, align="C")
    pdf.ln()

    # Contenido de la Tabla
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(0, 0, 0)
    
    for _, fila in df.iterrows():
        pdf.cell(anchos[0], 8, str(fila["Fecha"]), border=1, align="C")
        pdf.cell(anchos[1], 8, str(fila["Descripcion"])[:35], border=1)
        pdf.cell(anchos[2], 8, f"$ {float_a_uy(fila['Monto'])}", border=1, align="R")
        pdf.cell(anchos[3], 8, str(fila["Persona"]), border=1, align="C")
        pdf.cell(anchos[4], 8, str(fila["Medio"]), border=1, align="C")
        pdf.ln()

    pdf.ln(10)

    # --- RECUADRO DE DESGLOSE FINAL ---
    pdf.set_font("Arial", "B", 12)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 10, "RESUMEN DE GASTOS", ln=True, fill=True, align="L")
    
    pdf.set_font("Arial", "", 11)
    # Cálculos para el resumen
    total_marcelo = df[df['Persona'] == 'Marcelo']['Monto'].sum()
    total_yenny = df[df['Persona'] == 'Yenny']['Monto'].sum()
    total_gral = total_marcelo + total_yenny

    pdf.cell(100, 10, f"Gastos Marcelo:", border="B")
    pdf.cell(0, 10, f"$ {float_a_uy(total_marcelo)}", border="B", ln=True, align="R")
    
    pdf.cell(100, 10, f"Gastos Yenny:", border="B")
    pdf.cell(0, 10, f"$ {float_a_uy(total_yenny)}", border="B", ln=True, align="R")
    
    pdf.set_font("Arial", "B", 13)
    pdf.set_text_color(0, 102, 204) # Azul
    pdf.cell(100, 12, f"TOTAL GENERAL:", border=0)
    pdf.cell(0, 12, f"$ {float_a_uy(total_gral)}", border=0, ln=True, align="R")
    
    # Manejo de caracteres para evitar errores en latin-1
    return pdf.output(dest="S").encode("latin-1", "replace")

# --- LÓGICA DE LA APP ---
def main():
    # Asegurar tablas existentes
    ejecutar_query("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, Fecha TEXT, Monto REAL, Persona TEXT, Descripcion TEXT, Tarjeta TEXT, CuotasTotales INTEGER, CuotasPagadas INTEGER, MesesPagados TEXT)")
    ejecutar_query("CREATE TABLE IF NOT EXISTS gastos_fijos (id INTEGER PRIMARY KEY AUTOINCREMENT, Descripcion TEXT, Monto REAL, Persona TEXT, Cuenta TEXT, Activo BOOLEAN, MesesPagados TEXT)")

    conn = sqlite3.connect("finanzas.db")
    df_g = pd.read_sql_query("SELECT * FROM gastos", conn)
    df_f = pd.read_sql_query("SELECT * FROM gastos_fijos WHERE Activo=1", conn)
    conn.close()

    t1, t2, t3, t4 = st.tabs(["➕ Nuevo", "📋 Mis Cuentas", "📊 Proyección", "💾 Exportar y Backup"])

    # (Tabs 1, 2 y 3 permanecen con la lógica dinámica que ya establecimos)
    # ... 

    with t4:
        st.subheader("📄 Reporte PDF con Desglose")
        
        # Unificar datos para reporte
        df_f_m = df_f[['MesesPagados', 'Descripcion', 'Monto', 'Persona', 'Cuenta']].rename(columns={'MesesPagados':'Fecha', 'Cuenta':'Medio'})
        df_g_m = df_g[['Fecha', 'Descripcion', 'Monto', 'Persona', 'Tarjeta']].rename(columns={'Tarjeta':'Medio'})
        df_master = pd.concat([df_f_m, df_g_m])

        c_f1, c_f2 = st.columns(2)
        p_sel = c_f1.multiselect("Personas en el reporte:", ["Marcelo", "Yenny"], default=["Marcelo", "Yenny"])
        m_sel = c_f2.multiselect("Medios de pago:", ["DÉBITO", "SANTANDER", "BROU", "OCA"], default=["DÉBITO", "SANTANDER", "BROU", "OCA"])

        df_filtrado = df_master[df_master['Persona'].isin(p_sel) & df_master['Medio'].isin(m_sel)]

        st.divider()
        
        if not df_filtrado.empty:
            col_btn, col_info = st.columns([1, 1])
            with col_btn:
                # El botón mágico
                pdf_bytes = generar_pdf_pro(df_filtrado, "M&Y Finanzas Mensual")
                st.download_button(
                    label="📥 DESCARGAR REPORTE PDF",
                    data=pdf_bytes,
                    file_name=f"Reporte_Finanzas_{datetime.now().strftime('%Y_%m')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            with col_info:
                st.write(f"**Total calculado para el PDF:** ${float_a_uy(df_filtrado['Monto'].sum())}")
        else:
            st.warning("No hay datos para exportar con los filtros seleccionados.")

        # Backup de DB
        with st.expander("⚙️ Opciones Avanzadas (Backup DB)"):
            if os.path.exists("finanzas.db"):
                with open("finanzas.db", "rb") as f:
                    st.download_button("Descargar Base de Datos (.db)", f, "finanzas.db")

if __name__ == "__main__":
    main()
