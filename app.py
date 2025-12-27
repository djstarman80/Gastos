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
    conn = sqlite3.connect("finanzas.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, Fecha TEXT, Monto REAL, Persona TEXT, Descripcion TEXT, Tarjeta TEXT, CuotasTotales INTEGER, CuotasPagadas INTEGER, MesesPagados TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos_fijos (id INTEGER PRIMARY KEY AUTOINCREMENT, Descripcion TEXT, Monto REAL, Persona TEXT, Cuenta TEXT, Activo BOOLEAN, MesesPagados TEXT)")
    
    # Limpieza de nulos y normalización
    c.execute("UPDATE gastos_fijos SET Cuenta = 'DÉBITO' WHERE Cuenta IN ('OTRA', 'Otra', '') OR Cuenta IS NULL")
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

    conn = sqlite3.connect("finanzas.db")
    df_g = pd.read_sql_query("SELECT * FROM gastos", conn)
    df_f = pd.read_sql_query("SELECT * FROM gastos_fijos", conn)
    conn.close()

    t1, t2, t3 = st.tabs(["➕ Nuevo", "📋 Mis Cuentas", "📊 Proyección"])

    # --- TAB 1: NUEVO (CON CUOTAS) ---
    with t1:
        with st.form("form_ingreso", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            tipo = col_a.radio("Tipo de Gasto", ["Gasto Fijo", "Compra en Cuotas"])
            desc = col_b.text_input("Descripción")
            monto = col_a.number_input("Monto total ($)", min_value=0.0)
            pers = col_b.selectbox("Responsable", ["Marcelo", "Yenny"])
            
            # Lógica de cuotas restaurada
            if tipo == "Compra en Cuotas":
                medio = col_a.selectbox("Tarjeta", ["SANTANDER", "BROU", "OCA"])
                cuotas = col_b.number_input("Cantidad de cuotas", 1, 36, 1)
            else:
                medio = col_a.selectbox("Medio de Pago", ["DÉBITO", "SANTANDER", "BROU", "OCA"])
                cuotas = 1
            
            if st.form_submit_button("💾 GUARDAR GASTO", use_container_width=True):
                if tipo == "Compra en Cuotas":
                    ejecutar_query("INSERT INTO gastos (Fecha, Monto, Persona, Descripcion, Tarjeta, CuotasTotales, CuotasPagadas) VALUES (?,?,?,?,?,?,?)",
                                  (datetime.today().strftime("%d/%m/%Y"), monto, pers, desc, medio, cuotas, 0))
                else:
                    ejecutar_query("INSERT INTO gastos_fijos (Descripcion, Monto, Persona, Cuenta, Activo) VALUES (?,?,?,?,?)",
                                  (desc, monto, pers, medio, 1))
                st.success("Guardado correctamente")
                st.rerun()

    # --- TAB 2: MIS CUENTAS (RESUMEN TOTAL) ---
    with t2:
        # Cálculo de Totales Generales (Mes actual)
        total_fijos = df_f[df_f['Activo'] == 1]['Monto'].sum()
        total_cuotas = df_g['Monto'].sum()
        total_gral = total_fijos + total_cuotas
        
        t_marcelo = df_f[(df_f['Activo']==1) & (df_f['Persona']=='Marcelo')]['Monto'].sum() + df_g[df_g['Persona']=='Marcelo']['Monto'].sum()
        t_yenny = df_f[(df_f['Activo']==1) & (df_f['Persona']=='Yenny')]['Monto'].sum() + df_g[df_g['Persona']=='Yenny']['Monto'].sum()

        st.markdown(f"### 📊 Resumen Mensual General")
        c1, c2, c3 = st.columns(3)
        c1.metric("TOTAL GENERAL", f"${float_a_uy(total_gral)}")
        c2.metric("Marcelo", f"${float_a_uy(t_marcelo)}", delta_color="inverse")
        c3.metric("Yenny", f"${float_a_uy(t_yenny)}", delta_color="inverse")
        st.divider()

        medios = ["DÉBITO", "SANTANDER", "BROU", "OCA"]
        for m in medios:
            f_m = df_f[(df_f['Cuenta'] == m) & (df_f['Activo'] == 1)]
            g_m = df_g[df_g['Tarjeta'] == m]
            total_banco = f_m['Monto'].sum() + g_m['Monto'].sum()
            
            with st.expander(f"🏦 {m} — Subtotal: ${float_a_uy(total_banco)}"):
                if not f_m.empty:
                    st.write("**Gastos Fijos**")
                    for _, r in f_m.iterrows():
                        col_x, col_y = st.columns([4, 1])
                        col_x.write(f"• {r['Descripcion']} ({r['Persona']}): ${float_a_uy(r['Monto'])}")
                        if col_y.button("🗑️", key=f"df_{r['id']}"):
                            ejecutar_query("DELETE FROM gastos_fijos WHERE id=?", (r['id'],))
                            st.rerun()
                
                if not g_m.empty:
                    st.write("**Cuotas**")
                    for _, r in g_m.iterrows():
                        col_x, col_y = st.columns([4, 1])
                        col_x.write(f"• {r['Descripcion']} ({r['Persona']}): ${float_a_uy(r['Monto'])}")
                        if col_y.button("🗑️", key=f"dg_{r['id']}"):
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
                st.write(f"Marcelo: **${float_a_uy(m_m)}** | Yenny: **${float_a_uy(m_y)}**")
                st.write(f"Total: **${float_a_uy(m_m + m_y)}**")

if __name__ == "__main__":
    main()
