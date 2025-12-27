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
    """Repara la estructura de forma segura para evitar OperationalError"""
    conn = sqlite3.connect("finanzas.db")
    c = conn.cursor()
    
    # 1. [span_2](start_span)[span_3](start_span)Asegurar existencia de tablas base[span_2](end_span)[span_3](end_span)
    c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, Fecha TEXT, Monto REAL, Persona TEXT, Descripcion TEXT, Tarjeta TEXT, CuotasTotales INTEGER, CuotasPagadas INTEGER, MesesPagados TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos_fijos (id INTEGER PRIMARY KEY AUTOINCREMENT, Descripcion TEXT, Monto REAL, Persona TEXT, Cuenta TEXT, Activo BOOLEAN, MesesPagados TEXT)")
    
    # 2. [span_4](start_span)Verificar columnas actuales en gastos_fijos[span_4](end_span)
    c.execute("PRAGMA table_info(gastos_fijos)")
    cols = [col[1] for col in c.fetchall()]
    
    # Crear 'Cuenta' si no existe
    if 'Cuenta' not in cols:
        c.execute("ALTER TABLE gastos_fijos ADD COLUMN Cuenta TEXT DEFAULT 'DÉBITO'")
        conn.commit()
    
    # 3. [span_5](start_span)MIGRACIÓN SEGURA: Rescatar datos de 'OTRA' o 'CuentaDebito'[span_5](end_span)
    # Si existe CuentaDebito, movemos esos valores a Cuenta primero
    if 'CuentaDebito' in cols:
        c.execute("UPDATE gastos_fijos SET Cuenta = CuentaDebito WHERE Cuenta IS NULL OR Cuenta = ''")
    
    # [span_6](start_span)[span_7](start_span)Luego convertimos cualquier valor 'OTRA' o vacío a 'DÉBITO' para visibilidad[span_6](end_span)[span_7](end_span)
    c.execute("UPDATE gastos_fijos SET Cuenta = 'DÉBITO' WHERE Cuenta IN ('OTRA', 'Otra', '', None)")
    
    # 4. [span_8](start_span)Limpieza final de nombres[span_8](end_span)
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

    # Carga de datos unificada
    conn = sqlite3.connect("finanzas.db")
    df_g = pd.read_sql_query("SELECT * FROM gastos", conn)
    df_f = pd.read_sql_query("SELECT * FROM gastos_fijos", conn)
    conn.close()

    t1, t2, t3, t4 = st.tabs(["➕ Nuevo", "📋 Mis Cuentas", "📊 Proyección", "💾 Backup"])

    # --- TAB 1: INGRESO ---
    with t1:
        with st.form("form_ingreso", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            tipo = col_a.radio("Tipo", ["Gasto Fijo", "Compra en Cuotas"])
            desc = col_b.text_input("Descripción")
            monto = col_a.number_input("Monto ($)", min_value=0.0)
            pers = col_b.selectbox("Responsable", ["Marcelo", "Yenny"])
            
            if tipo == "Compra en Cuotas":
                medio = col_a.selectbox("Tarjeta", ["SANTANDER", "BROU", "OCA"])
                cuotas = col_b.number_input("Cuotas totales", 1, 36, 1)
            else:
                medio = col_a.selectbox("Medio de Pago", ["DÉBITO", "SANTANDER", "BROU", "OCA"])
                cuotas = 1
            
            if st.form_submit_button("💾 GUARDAR"):
                if tipo == "Compra en Cuotas":
                    ejecutar_query("INSERT INTO gastos (Fecha, Monto, Persona, Descripcion, Tarjeta, CuotasTotales, CuotasPagadas) VALUES (?,?,?,?,?,?,?)",
                                  (datetime.today().strftime("%d/%m/%Y"), monto, pers, desc, medio, cuotas, 0))
                else:
                    ejecutar_query("INSERT INTO gastos_fijos (Descripcion, Monto, Persona, Cuenta, Activo) VALUES (?,?,?,?,?)",
                                  (desc, monto, pers, medio, 1))
                st.success("Guardado")
                st.rerun()

    # --- TAB 2: GESTIÓN ---
    with t2:
        medios = ["DÉBITO", "SANTANDER", "BROU", "OCA"]
        for m in medios:
            f_m = df_f[(df_f['Cuenta'] == m) & (df_f['Activo'] == 1)]
            g_m = df_g[df_g['Tarjeta'] == m]
            total = f_m['Monto'].sum() + g_m['Monto'].sum()
            
            with st.expander(f"🏦 {m} — TOTAL: ${float_a_uy(total)}"):
                if not f_m.empty:
                    st.write("**Gastos Fijos**")
                    for _, r in f_m.iterrows():
                        c1, c2, c3 = st.columns([3, 1.5, 0.5])
                        c1.write(f"{r['Descripcion']}: ${float_a_uy(r['Monto'])} ({r['Persona']})")
                        nuevo = c2.selectbox("Mover:", medios, key=f"f_{r['id']}", index=medios.index(m))
                        if nuevo != m:
                            ejecutar_query("UPDATE gastos_fijos SET Cuenta=? WHERE id=?", (nuevo, r['id']))
                            st.rerun()
                        if c3.button("🗑️", key=f"df_{r['id']}"):
                            ejecutar_query("DELETE FROM gastos_fijos WHERE id=?", (r['id'],))
                            st.rerun()
                
                if not g_m.empty:
                    st.write("**Cuotas**")
                    for _, r in g_m.iterrows():
                        c1, c2, c3 = st.columns([3, 1.5, 0.5])
                        c1.write(f"{r['Descripcion']}: ${float_a_uy(r['Monto'])} ({r['Persona']})")
                        if c3.button("🗑️", key=f"dg_{r['id']}"):
                            ejecutar_query("DELETE FROM gastos WHERE id=?", (r['id'],))
                            st.rerun()

    # --- TAB 3: PROYECCIÓN ---
    with t3:
        hoy = datetime.today()
        inicio = hoy.replace(day=1) + pd.DateOffset(months=1) if hoy.day >= dia_cierre else hoy.replace(day=1)
        for i in range(6):
            mes_act = inicio + pd.DateOffset(months=i)
            m_m, m_y = 0.0, 0.0
            for _, r in df_f[df_f['Activo']==1].iterrows():
                if r['Persona'] == "Marcelo": m_m += r['Monto']
                else: m_y += r['Monto']
            for _, r in df_g.iterrows():
                if i < (r['CuotasTotales'] - r['CuotasPagadas']):
                    if r['Persona'] == "Marcelo": m_m += r['Monto']
                    else: m_y += r['Monto']
            
            with st.container(border=True):
                st.write(f"#### 📅 {MESES_NOMBRE[mes_act.month]} {mes_act.year}")
                st.write(f"Marcelo: ${float_a_uy(m_m)} | Yenny: ${float_a_uy(m_y)}")

    # --- TAB 4: BACKUP ---
    with t4:
        if os.path.exists("finanzas.db"):
            with open("finanzas.db", "rb") as f:
                st.download_button("📥 Descargar DB", f, "finanzas.db")

if __name__ == "__main__":
    main()
