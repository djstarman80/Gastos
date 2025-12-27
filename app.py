import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os
from fpdf import FPDF

# --- CONFIGURACIÓN DE PÁGINA ---
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

# --- BASE DE DATOS CON PARCHE DE SEGURIDAD ---
def init_db():
    conn = sqlite3.connect("finanzas.db")
    cursor = conn.cursor()
    # Crear tablas base
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Fecha TEXT, Monto REAL, Persona TEXT, Descripcion TEXT, 
            Tarjeta TEXT, CuotasTotales INTEGER, CuotasPagadas INTEGER, MesesPagados TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos_fijos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Descripcion TEXT, Monto REAL, Persona TEXT, 
            Cuenta TEXT, Activo BOOLEAN, MesesPagados TEXT
        )
    """)
    # PARCHE: Verificar columnas nuevas para evitar KeyError
    cursor.execute("PRAGMA table_info(gastos)")
    cols_g = [c[1] for c in cursor.fetchall()]
    if 'Tarjeta' not in cols_g:
        cursor.execute("ALTER TABLE gastos ADD COLUMN Tarjeta TEXT DEFAULT 'BROU'")
        
    cursor.execute("PRAGMA table_info(gastos_fijos)")
    cols_f = [c[1] for c in cursor.fetchall()]
    if 'Cuenta' not in cols_f:
        cursor.execute("ALTER TABLE gastos_fijos ADD COLUMN Cuenta TEXT DEFAULT 'DÉBITO'")
        
    conn.commit()
    conn.close()

def cargar_datos(tabla):
    conn = sqlite3.connect("finanzas.db")
    df = pd.read_sql_query(f"SELECT * FROM {tabla}", conn)
    conn.close()
    return df

# --- LÓGICA DE AUTOCIERRE ---
def aplicar_autocierre(dia_limite):
    hoy = datetime.today()
    if hoy.day >= dia_limite:
        mes_id = hoy.strftime("%Y-%m")
        conn = sqlite3.connect("finanzas.db")
        cursor = conn.cursor()
        # Cuotas
        cursor.execute("""
            UPDATE gastos SET CuotasPagadas = CuotasPagadas + 1,
            MesesPagados = CASE WHEN MesesPagados='' OR MesesPagados IS NULL THEN ? ELSE MesesPagados||','||? END
            WHERE CuotasPagadas < CuotasTotales AND (MesesPagados NOT LIKE ? OR MesesPagados IS NULL)
        """, (mes_id, mes_id, f"%{mes_id}%"))
        # Fijos
        cursor.execute("""
            UPDATE gastos_fijos SET 
            MesesPagados = CASE WHEN MesesPagados='' OR MesesPagados IS NULL THEN ? ELSE MesesPagados||','||? END
            WHERE Activo=1 AND (MesesPagados NOT LIKE ? OR MesesPagados IS NULL)
        """, (mes_id, mes_id, f"%{mes_id}%"))
        conn.commit()
        conn.close()

# --- INTERFAZ ---
def main():
    init_db()
    
    st.sidebar.title("⚙️ Configuración")
    dia_cierre = st.sidebar.slider("Día de Autocierre Mensual", 1, 28, 10)
    aplicar_autocierre(dia_cierre)

    tab1, tab2, tab3, tab4 = st.tabs(["➕ Ingreso", "📋 Gestión", "📊 Pagos Futuros", "💾 Respaldo y Reportes"])

    # --- TAB 1: INGRESO ---
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("💳 Gasto por Cuotas")
            with st.form("f_cuotas"):
                desc = st.text_input("Descripción")
                monto_c = st.text_input("Valor de la Cuota Mensual ($)")
                cuotas_t = st.number_input("Total de Cuotas", 1, 36, 1)
                tarjeta = st.selectbox("Tarjeta", ["BROU", "OCA", "SANTANDER"])
                pers = st.selectbox("A nombre de:", ["Marcelo", "Yenny"], key="p1")
                if st.form_submit_button("Guardar Gasto"):
                    conn = sqlite3.connect("finanzas.db")
                    conn.execute("INSERT INTO gastos (Fecha, Monto, Persona, Descripcion, Tarjeta, CuotasTotales, CuotasPagadas, MesesPagados) VALUES (?,?,?,?,?,?,?,?)",
                                 (datetime.today().strftime("%d/%m/%Y"), monto_uy_a_float(monto_c), pers, desc, tarjeta, cuotas_t, 0, ""))
                    conn.commit(); st.success("Gasto Guardado"); st.rerun()
        with c2:
            st.subheader("🏦 Gasto Fijo")
            with st.form("f_fijos"):
                desc_f = st.text_input("Descripción")
                monto_f = st.text_input("Monto Mensual ($)")
                medio_f = st.selectbox("Medio de Pago", ["DÉBITO", "BROU", "OCA", "SANTANDER"])
                pers_f = st.selectbox("Responsable:", ["Marcelo", "Yenny"], key="p2")
                if st.form_submit_button("Guardar Fijo"):
                    conn = sqlite3.connect("finanzas.db")
                    conn.execute("INSERT INTO gastos_fijos (Descripcion, Monto, Persona, Cuenta, Activo, MesesPagados) VALUES (?,?,?,?,?,?)",
                                 (desc_f, monto_uy_a_float(monto_f), pers_f, medio_f, 1, ""))
                    conn.commit(); st.success("Fijo Guardado"); st.rerun()

    # --- TAB 2: GESTIÓN ---
    with tab2:
        df_g = cargar_datos("gastos")
        df_f = cargar_datos("gastos_fijos")
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.write("### Cuotas Activas")
            for _, r in df_g.iterrows():
                with st.expander(f"{r['Descripcion']} - {r['Persona']} ({r['Tarjeta']})"):
                    st.write(f"Cuota: ${float_a_monto_uy(r['Monto'])} | Pagos: {r['CuotasPagadas']}/{r['CuotasTotales']}")
                    if st.button("Eliminar", key=f"dg{r['id']}"):
                        conn = sqlite3.connect("finanzas.db"); conn.execute("DELETE FROM gastos WHERE id=?", (r['id'],)); conn.commit(); st.rerun()
        with col_g2:
            st.write("### Gastos Fijos")
            for _, r in df_f.iterrows():
                with st.expander(f"{r['Descripcion']} - {r['Persona']} ({r['Cuenta']})"):
                    st.write(f"Monto: ${float_a_monto_uy(r['Monto'])} | {'✅ Activo' if r['Activo'] else '❌ Pausado'}")
                    if st.button("Alternar Estado", key=f"tf{r['id']}"):
                        nuevo = 0 if r['Activo'] else 1
                        conn = sqlite3.connect("finanzas.db"); conn.execute("UPDATE gastos_fijos SET Activo=? WHERE id=?", (nuevo, r['id'])); conn.commit(); st.rerun()
                    if st.button("Borrar Fijo", key=f"bf{r['id']}"):
                        conn = sqlite3.connect("finanzas.db"); conn.execute("DELETE FROM gastos_fijos WHERE id=?", (r['id'],)); conn.commit(); st.rerun()

    # --- TAB 3: PAGOS FUTUROS ---
    with tab3:
        hoy = datetime.today()
        inicio_p = hoy.replace(day=1) + pd.DateOffset(months=1) if hoy.day >= dia_cierre else hoy.replace(day=1)
        
        # Generar Proyección
        proy_list = []
        for i in range(12):
            mes_f = inicio_p + pd.DateOffset(months=i)
            sm, sy = 0.0, 0.0
            # Fijos
            for _, f in df_f[df_f['Activo']==1].iterrows():
                if f['Persona'] == "Marcelo": sm += f['Monto']
                else: sy += f['Monto']
            # Cuotas
            for _, g in df_g.iterrows():
                if i < (g['CuotasTotales'] - g['CuotasPagadas']):
                    if g['Persona'] == "Marcelo": sm += g['Monto']
                    else: sy += g['Monto']
            proy_list.append({"Mes": f"{MESES_NOMBRE[mes_f.month]} '{str(mes_f.year)[2:]}", "Marcelo": f"${float_a_monto_uy(sm)}", "Yenny": f"${float_a_monto_uy(sy)}", "Total Mes": f"${float_a_monto_uy(sm+sy)}"})

        st.table(pd.DataFrame(proy_list))
        
        # Resumen por Tarjeta/Medio para el Mes 1
        st.subheader(f"🔍 Desglose para {proy_list[0]['Mes']}")
        c_tar, c_cue = st.columns(2)
        with c_tar:
            st.write("**💳 Tarjetas (Cuotas)**")
            res_t = {}
            for _, g in df_g.iterrows():
                if 0 < (g['CuotasTotales'] - g['CuotasPagadas']):
                    res_t[g['Tarjeta']] = res_t.get(g['Tarjeta'], 0) + g['Monto']
            for k,v in res_t.items(): st.write(f"- {k}: ${float_a_monto_uy(v)}")
        with c_cue:
            st.write("**🏦 Otros Medios (Fijos)**")
            res_c = {}
            for _, f in df_f[df_f['Activo']==1].iterrows():
                res_c[f['Cuenta']] = res_c.get(f['Cuenta'], 0) + f['Monto']
            for k,v in res_c.items(): st.write(f"- {k}: ${float_a_monto_uy(v)}")

    # --- TAB 4: RESPALDO Y PDF ---
    with tab4:
        st.header("Gestión de Datos")
        if st.button("Generar Reporte PDF de Proyección"):
            pdf = FPDF()
            pdf.add_page(); pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, "Reporte Financiero M&Y", 0, 1, "C"); pdf.ln(10)
            pdf.set_font("Arial", "B", 10); pdf.cell(40, 8, "Mes", 1); pdf.cell(50, 8, "Marcelo", 1); pdf.cell(50, 8, "Yenny", 1); pdf.cell(50, 8, "Total", 1); pdf.ln()
            pdf.set_font("Arial", "", 10)
            for r in proy_list:
                pdf.cell(40, 8, r["Mes"], 1); pdf.cell(50, 8, r["Marcelo"], 1); pdf.cell(50, 8, r["Yenny"], 1); pdf.cell(50, 8, r["Total Mes"], 1); pdf.ln()
            st.download_button("Descargar PDF", pdf.output(dest='S').encode('latin-1'), "Reporte_MY.pdf", "application/pdf")
        
        if os.path.exists("finanzas.db"):
            with open("finanzas.db", "rb") as f:
                st.download_button("📥 Descargar Base de Datos (Backup)", f, "finanzas.db")

if __name__ == "__main__":
    main()
