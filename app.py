import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os

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

def corregir_base_datos():
    """Crea columnas faltantes y normaliza datos secuencialmente"""
    conn = sqlite3.connect("finanzas.db")
    c = conn.cursor()
    
    # 1. Asegurar tablas
    c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, Fecha TEXT, Monto REAL, Persona TEXT, Descripcion TEXT, Tarjeta TEXT, CuotasTotales INTEGER, CuotasPagadas INTEGER, MesesPagados TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos_fijos (id INTEGER PRIMARY KEY AUTOINCREMENT, Descripcion TEXT, Monto REAL, Persona TEXT, Cuenta TEXT, Activo BOOLEAN, MesesPagados TEXT)")
    
    # 2. Verificar y Crear Columna Cuenta si no existe
    c.execute("PRAGMA table_info(gastos_fijos)")
    cols = [col[1] for col in c.fetchall()]
    if 'Cuenta' not in cols:
        c.execute("ALTER TABLE gastos_fijos ADD COLUMN Cuenta TEXT DEFAULT 'DÉBITO'")
        conn.commit()

    # 3. Migrar de CuentaDebito a Cuenta si existe la columna vieja
    if 'CuentaDebito' in cols:
        c.execute("UPDATE gastos_fijos SET Cuenta = CuentaDebito WHERE Cuenta IS NULL OR Cuenta = ''")
    
    # 4. Limpieza de valores nulos o 'OTRA'
    c.execute("UPDATE gastos_fijos SET Cuenta = 'DÉBITO' WHERE Cuenta IN ('OTRA', 'Otra', '') OR Cuenta IS NULL")
    
    # 5. Normalizar para filtros
    c.execute("UPDATE gastos SET Tarjeta = UPPER(TRIM(Tarjeta)) WHERE Tarjeta IS NOT NULL")
    c.execute("UPDATE gastos_fijos SET Cuenta = UPPER(TRIM(Cuenta)) WHERE Cuenta IS NOT NULL")
    
    conn.commit()
    conn.close()

def float_a_uy(v):
    return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def main():
    corregir_base_datos()
    
    st.sidebar.title("⚙️ Configuración")
    dia_cierre = st.sidebar.slider("Día de cierre", 1, 28, 10)

    # Carga de datos
    conn = sqlite3.connect("finanzas.db")
    df_g = pd.read_sql_query("SELECT * FROM gastos", conn)
    df_f = pd.read_sql_query("SELECT * FROM gastos_fijos", conn)
    conn.close()

    t1, t2, t3 = st.tabs(["➕ Nuevo", "📋 Mis Cuentas", "📊 Proyección"])

    # --- TAB 1: NUEVO ---
    with t1:
        with st.form("form_ingreso", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            tipo = col_a.radio("Tipo de Gasto", ["Gasto Fijo", "Compra en Cuotas"])
            desc = col_b.text_input("Descripción")
            monto = col_a.number_input("Monto ($)", min_value=0.0)
            pers = col_b.selectbox("Responsable", ["Marcelo", "Yenny"])
            
            if tipo == "Compra en Cuotas":
                medio = col_a.selectbox("Tarjeta", ["SANTANDER", "BROU", "OCA"])
                cuotas = col_b.number_input("Cuotas totales", 1, 36, 1)
            else:
                medio = col_a.selectbox("Medio de Pago", ["DÉBITO", "SANTANDER", "BROU", "OCA"])
                cuotas = 1
            
            if st.form_submit_button("✅ GUARDAR", use_container_width=True):
                if tipo == "Compra en Cuotas":
                    ejecutar_query("INSERT INTO gastos (Fecha, Monto, Persona, Descripcion, Tarjeta, CuotasTotales, CuotasPagadas) VALUES (?,?,?,?,?,?,?)",
                                  (datetime.today().strftime("%d/%m/%Y"), monto, pers, desc, medio, cuotas, 0))
                else:
                    ejecutar_query("INSERT INTO gastos_fijos (Descripcion, Monto, Persona, Cuenta, Activo) VALUES (?,?,?,?,?)",
                                  (desc, monto, pers, medio, 1))
                st.rerun()

    # --- TAB 2: MIS CUENTAS ---
    with t2:
        # Totales del mes
        total_f = df_f[df_f['Activo'] == 1]['Monto'].sum()
        total_g = df_g['Monto'].sum()
        total_total = total_f + total_g
        
        m_marcelo = df_f[(df_f['Activo']==1) & (df_f['Persona']=='Marcelo')]['Monto'].sum() + df_g[df_g['Persona']=='Marcelo']['Monto'].sum()
        m_yenny = df_f[(df_f['Activo']==1) & (df_f['Persona']=='Yenny')]['Monto'].sum() + df_g[df_g['Persona']=='Yenny']['Monto'].sum()

        st.markdown("### 📊 Totales del Mes")
        c1, c2, c3 = st.columns(3)
        c1.metric("TOTAL GENERAL", f"${float_a_uy(total_total)}")
        c2.metric("Marcelo", f"${float_a_uy(m_marcelo)}")
        c3.metric("Yenny", f"${float_a_uy(m_yenny)}")
        st.divider()

        medios = ["DÉBITO", "SANTANDER", "BROU", "OCA"]
        for m in medios:
            sub_f = df_f[(df_f['Cuenta'] == m) & (df_f['Activo'] == 1)]
            sub_g = df_g[df_g['Tarjeta'] == m]
            sub_total = sub_f['Monto'].sum() + sub_g['Monto'].sum()
            
            with st.expander(f"🏦 {m} — Subtotal: ${float_a_uy(sub_total)}"):
                if not sub_f.empty:
                    st.write("**Gastos Fijos**")
                    for _, r in sub_f.iterrows():
                        cx, cy = st.columns([4, 1])
                        cx.write(f"• {r['Descripcion']} ({r['Persona']}): ${float_a_uy(r['Monto'])}")
                        if cy.button("🗑️", key=f"f{r['id']}"):
                            ejecutar_query("DELETE FROM gastos_fijos WHERE id=?", (r['id'],)); st.rerun()
                
                if not sub_g.empty:
                    st.write("**Cuotas**")
                    for _, r in sub_g.iterrows():
                        cx, cy = st.columns([4, 1])
                        cx.write(f"• {r['Descripcion']} ({r['Persona']}): ${float_a_uy(r['Monto'])}")
                        if cy.button("🗑️", key=f"g{r['id']}"):
                            ejecutar_query("DELETE FROM gastos WHERE id=?", (r['id'],)); st.rerun()

    # --- TAB 3: PROYECCIÓN ---
    with t3:
        hoy = datetime.today()
        ini = hoy.replace(day=1) + pd.DateOffset(months=1) if hoy.day >= dia_cierre else hoy.replace(day=1)
        for i in range(6):
            m_f = ini + pd.DateOffset(months=i)
            sm, sy = 0.0, 0.0
            for _, r in df_f[df_f['Activo']==1].iterrows():
                if r['Persona'] == "Marcelo": sm += r['Monto']
                else: sy += r['Monto']
            for _, r in df_g.iterrows():
                if i < (r['CuotasTotales'] - r['CuotasPagadas']):
                    if r['Persona'] == "Marcelo": sm += r['Monto']
                    else: sy += r['Monto']
            
            with st.container(border=True):
                st.write(f"#### 📅 {MESES_NOMBRE[m_f.month]} {m_f.year}")
                st.write(f"Marcelo: ${float_a_uy(sm)} | Yenny: ${float_a_uy(sy)} | **Total: ${float_a_uy(sm+sy)}**")

if __name__ == "__main__":
    main()
