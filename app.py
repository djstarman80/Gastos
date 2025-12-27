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
    # Tablas
    c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, Fecha TEXT, Monto REAL, Persona TEXT, Descripcion TEXT, Tarjeta TEXT, CuotasTotales INTEGER, CuotasPagadas INTEGER, MesesPagados TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos_fijos (id INTEGER PRIMARY KEY AUTOINCREMENT, Descripcion TEXT, Monto REAL, Persona TEXT, Cuenta TEXT, Activo BOOLEAN, MesesPagados TEXT)")
    
    # Columnas
    c.execute("PRAGMA table_info(gastos_fijos)")
    cols = [col[1] for col in c.fetchall()]
    if 'Cuenta' not in cols:
        c.execute("ALTER TABLE gastos_fijos ADD COLUMN Cuenta TEXT DEFAULT 'DÉBITO'")
        conn.commit()

    # Normalización
    c.execute("UPDATE gastos_fijos SET Cuenta = 'DÉBITO' WHERE Cuenta IN ('OTRA', 'Otra', '') OR Cuenta IS NULL")
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

    conn = sqlite3.connect("finanzas.db")
    df_g = pd.read_sql_query("SELECT * FROM gastos", conn)
    df_f = pd.read_sql_query("SELECT * FROM gastos_fijos", conn)
    conn.close()

    t1, t2, t3 = st.tabs(["➕ Nuevo Gasto", "📋 Mis Cuentas", "📊 Proyección"])

    # --- TAB 1: NUEVO ---
    with t1:
        st.subheader("Registrar Movimiento")
        tipo_gasto = st.radio("Selecciona el tipo:", ["Gasto Fijo / Débito", "Compra en Cuotas"], horizontal=True)
        
        with st.form("form_nuevo_gasto", clear_on_submit=True):
            col1, col2 = st.columns(2)
            desc = col1.text_input("Descripción")
            
            label_monto = "Valor de la Cuota ($)" if tipo_gasto == "Compra en Cuotas" else "Monto Mensual ($)"
            monto = col2.number_input(label_monto, min_value=0.0, step=100.0)
            
            pers = col1.selectbox("Responsable", ["Marcelo", "Yenny"])
            
            if tipo_gasto == "Compra en Cuotas":
                medio = col2.selectbox("Tarjeta", ["SANTANDER", "BROU", "OCA"])
                n_cuotas = col1.number_input("Cantidad de Cuotas totales", min_value=1, max_value=48, value=1)
            else:
                medio = col2.selectbox("Medio de Pago", ["DÉBITO", "SANTANDER", "BROU", "OCA"])
                n_cuotas = 1

            if st.form_submit_button("✅ GUARDAR", use_container_width=True):
                if not desc or monto <= 0:
                    st.error("Completa descripción y monto.")
                else:
                    if tipo_gasto == "Compra en Cuotas":
                        ejecutar_query("INSERT INTO gastos (Fecha, Monto, Persona, Descripcion, Tarjeta, CuotasTotales, CuotasPagadas) VALUES (?,?,?,?,?,?,?)",
                                      (datetime.today().strftime("%d/%m/%Y"), monto, pers, desc, medio, n_cuotas, 0))
                    else:
                        ejecutar_query("INSERT INTO gastos_fijos (Descripcion, Monto, Persona, Cuenta, Activo) VALUES (?,?,?,?,?)",
                                      (desc, monto, pers, medio, 1))
                    st.success("¡Guardado!")
                    st.rerun()

    # --- TAB 2: MIS CUENTAS ---
    with t2:
        m_m = df_f[(df_f['Activo']==1) & (df_f['Persona']=='Marcelo')]['Monto'].sum() + df_g[df_g['Persona']=='Marcelo']['Monto'].sum()
        m_y = df_f[(df_f['Activo']==1) & (df_f['Persona']=='Yenny')]['Monto'].sum() + df_g[df_g['Persona']=='Yenny']['Monto'].sum()

        st.markdown("### 📊 Resumen del Mes")
        c1, c2, c3 = st.columns(3)
        c1.metric("TOTAL GENERAL", f"${float_a_uy(m_m + m_y)}")
        c2.metric("Marcelo", f"${float_a_uy(m_m)}")
        c3.metric("Yenny", f"${float_a_uy(m_y)}")
        st.divider()

        medios = ["DÉBITO", "SANTANDER", "BROU", "OCA"]
        for m in medios:
            sub_f = df_f[(df_f['Cuenta'] == m) & (df_f['Activo'] == 1)]
            sub_g = df_g[df_g['Tarjeta'] == m]
            sub_t = sub_f['Monto'].sum() + sub_g['Monto'].sum()
            
            with st.expander(f"🏦 {m} — Subtotal: ${float_a_uy(sub_t)}"):
                if not sub_f.empty:
                    st.write("**🏠 Gastos Fijos**")
                    for _, r in sub_f.iterrows():
                        cx, cy = st.columns([4, 1])
                        cx.write(f"• {r['Descripcion']} ({r['Persona']}): ${float_a_uy(r['Monto'])}")
                        if cy.button("🗑️", key=f"f{r['id']}"):
                            ejecutar_query("DELETE FROM gastos_fijos WHERE id=?", (r['id'],)); st.rerun()
                
                if not sub_g.empty:
                    st.write("**💳 Cuotas**")
                    for _, r in sub_g.iterrows():
                        cx, cy = st.columns([4, 1])
                        faltantes = r['CuotasTotales'] - r['CuotasPagadas']
                        deuda_total = r['Monto'] * faltantes
                        cx.write(f"• **{r['Descripcion']}** ({r['Persona']}): ${float_a_uy(r['Monto'])}")
                        cx.caption(f"Cuotas restantes: {faltantes} | Deuda pendiente: ${float_a_uy(deuda_total)}")
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
                st.write(f"Marcelo: **${float_a_uy(sm)}** | Yenny: **${float_a_uy(sy)}**")
                st.write(f"Total: **${float_a_uy(sm+sy)}**")

if __name__ == "__main__":
    main()
