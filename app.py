import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os

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

def corregir_base_datos():
    """Repara la estructura y rescata datos invisibles"""
    conn = sqlite3.connect("finanzas.db")
    c = conn.cursor()
    
    # Asegurar tablas
    c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, Fecha TEXT, Monto REAL, Persona TEXT, Descripcion TEXT, Tarjeta TEXT, CuotasTotales INTEGER, CuotasPagadas INTEGER, MesesPagados TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos_fijos (id INTEGER PRIMARY KEY AUTOINCREMENT, Descripcion TEXT, Monto REAL, Persona TEXT, Cuenta TEXT, Activo BOOLEAN, MesesPagados TEXT)")
    
    # Verificar columnas
    c.execute("PRAGMA table_info(gastos_fijos)")
    cols = [col[1] for col in c.fetchall()]
    if 'Cuenta' not in cols:
        c.execute("ALTER TABLE gastos_fijos ADD COLUMN Cuenta TEXT DEFAULT 'DÉBITO'")
    
    # MIGRACIÓN: Rescatar registros que dicen 'OTRA' o 'Otra' (como Alquiler/Celular)
    c.execute("UPDATE gastos_fijos SET Cuenta = 'DÉBITO' WHERE Cuenta IN ('OTRA', 'Otra', '', None)")
    
    # Normalizar nombres para filtros
    c.execute("UPDATE gastos SET Tarjeta = UPPER(TRIM(Tarjeta)) WHERE Tarjeta IS NOT NULL")
    c.execute("UPDATE gastos_fijos SET Cuenta = UPPER(TRIM(Cuenta)) WHERE Cuenta IS NOT NULL")
    
    conn.commit()
    conn.close()

def float_a_uy(v):
    return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- INTERFAZ ---
def main():
    corregir_base_datos()
    
    st.sidebar.title("⚙️ Configuración")
    dia_cierre = st.sidebar.slider("Día de cierre de tarjetas", 1, 28, 10)

    # Carga de datos
    conn = sqlite3.connect("finanzas.db")
    df_g = pd.read_sql_query("SELECT * FROM gastos", conn)
    df_f = pd.read_sql_query("SELECT * Silvia, f FROM gastos_fijos", conn)
    conn.close()

    t1, t2, t3, t4 = st.tabs(["➕ Nuevo", "📋 Mis Cuentas", "📊 Proyección", "💾 Backup"])

    # --- TAB 1: INGRESO ---
    with t1:
        with st.form("form_ingreso", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            tipo = col_a.radio("Tipo", ["Gasto Fijo", "Compra en Cuotas"])
            desc = col_b.text_input("Descripción (ej: Alquiler, Supermercado)")
            monto = col_a.number_input("Monto ($)", min_value=0.0, step=100.0)
            pers = col_b.selectbox("Responsable", ["Marcelo", "Yenny"])
            
            if tipo == "Compra en Cuotas":
                medio = col_a.selectbox("Tarjeta", ["SANTANDER", "BROU", "OCA"])
                cuotas = col_b.number_input("Cuotas totales", 1, 36, 1)
            else:
                medio = col_a.selectbox("Medio de Pago", ["DÉBITO", "SANTANDER", "BROU", "OCA"])
                cuotas = 1
            
            if st.form_submit_button("💾 GUARDAR GASTO"):
                if tipo == "Compra en Cuotas":
                    ejecutar_query("INSERT INTO gastos (Fecha, Monto, Persona, Descripcion, Tarjeta, CuotasTotales, CuotasPagadas) VALUES (?,?,?,?,?,?,?)",
                                  (datetime.today().strftime("%d/%m/%Y"), monto, pers, desc, medio, cuotas, 0))
                else:
                    ejecutar_query("INSERT INTO gastos_fijos (Descripcion, Monto, Persona, Cuenta, Activo) VALUES (?,?,?,?,?)",
                                  (desc, monto, pers, medio, 1))
                st.success("Guardado correctamente")
                st.rerun()

    # --- TAB 2: GESTIÓN POR TARJETA ---
    with t2:
        medios = ["DÉBITO", "SANTANDER", "BROU", "OCA"]
        for m in medios:
            # [span_2](start_span)[span_3](start_span)[span_4](start_span)Filtrar datos de la DB[span_2](end_span)[span_3](end_span)[span_4](end_span)
            f_m = df_f[(df_f['Cuenta'] == m) & (df_f['Activo'] == 1)]
            g_m = df_g[df_g['Tarjeta'] == m]
            total = f_m['Monto'].sum() + g_m['Monto'].sum()
            
            with st.expander(f"🏦 {m} — TOTAL ESTIMADO: ${float_a_uy(total)}"):
                st.subheader("🏠 Gastos Fijos / Débitos")
                if f_m.empty: st.info("No hay gastos fijos.")
                for _, r in f_m.iterrows():
                    c1, c2, c3 = st.columns([3, 1.5, 0.5])
                    c1.write(f"**{r['Descripcion']}**: ${float_a_uy(r['Monto'])} ({r['Persona']})")
                    nuevo_m = c2.selectbox("Mover a:", medios, key=f"mf_{r['id']}", index=medios.index(m))
                    if nuevo_m != m:
                        ejecutar_query("UPDATE gastos_fijos SET Cuenta=? WHERE id=?", (nuevo_m, r['id']))
                        st.rerun()
                    if c3.button("🗑️", key=f"df_{r['id']}"):
                        ejecutar_query("DELETE FROM gastos_fijos WHERE id=?", (r['id'],))
                        st.rerun()

                st.divider()
                st.subheader("💳 Compras en Cuotas")
                if g_m.empty: st.info("No hay cuotas pendientes.")
                for _, r in g_m.iterrows():
                    c1, c2, c3 = st.columns([3, 1.5, 0.5])
                    c1.write(f"**{r['Descripcion']}**: ${float_a_uy(r['Monto'])} ({r['Persona']})")
                    nuevo_m = c2.selectbox("Mover a:", ["SANTANDER", "BROU", "OCA"], key=f"mg_{r['id']}", index=["SANTANDER", "BROU", "OCA"].index(m) if m in ["SANTANDER", "BROU", "OCA"] else 0)
                    if nuevo_m != m:
                        ejecutar_query("UPDATE gastos SET Tarjeta=? WHERE id=?", (nuevo_m, r['id']))
                        st.rerun()
                    if c3.button("🗑️", key=f"dg_{r['id']}"):
                        ejecutar_query("DELETE FROM gastos WHERE id=?", (r['id'],))
                        st.rerun()

    # --- TAB 3: PROYECCIÓN ---
    with t3:
        st.subheader("📈 Proyección de Pagos Mensuales")
        hoy = datetime.today()
        # Determinar el primer mes de pago según el cierre
        inicio = hoy.replace(day=1) + pd.DateOffset(months=1) if hoy.day >= dia_cierre else hoy.replace(day=1)
        
        for i in range(6):
            mes_act = inicio + pd.DateOffset(months=i)
            m_marcelo, m_yenny = 0.0, 0.0
            
            # Sumar fijos
            for _, r in df_f[df_f['Activo']==1].iterrows():
                if r['Persona'] == "Marcelo": m_marcelo += r['Monto']
                else: m_yenny += r['Monto']
            
            # Sumar cuotas que aún no terminaron
            for _, r in df_g.iterrows():
                if i < (r['CuotasTotales'] - r['CuotasPagadas']):
                    if r['Persona'] == "Marcelo": m_marcelo += r['Monto']
                    else: m_yenny += r['Monto']
            
            with st.container(border=True):
                st.write(f"### 📅 {MESES_NOMBRE[mes_act.month]} {mes_act.year}")
                c1, c2 = st.columns(2)
                c1.metric("Marcelo", f"${float_a_uy(m_marcelo)}")
                c2.metric("Yenny", f"${float_a_uy(m_yenny)}")
                st.write(f"**Total combinado: ${float_a_uy(m_marcelo + m_yenny)}**")

    # --- TAB 4: BACKUP ---
    with t4:
        st.info("Descarga tu base de datos para tener un respaldo.")
        if os.path.exists("finanzas.db"):
            with open("finanzas.db", "rb") as f:
                st.download_button("📥 Descargar finanzas.db", f, file_name="finanzas_backup.db")

if __name__ == "__main__":
    main()
