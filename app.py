import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="M&Y Finanzas", layout="wide", page_icon="💰")

# --- FUNCIONES DE APOYO ---
def monto_uy_a_float(t):
    if not t: return 0.0
    try:
        s = str(t).replace("$", "").replace(".", "").replace(",", ".").strip()
        return float(s)
    except: return 0.0

def float_a_monto_uy(v):
    return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def ejecutar_query(q, p=()):
    conn = sqlite3.connect("finanzas.db")
    conn.execute(q, p); conn.commit(); conn.close()

# --- REPARACIÓN DE BASE DE DATOS ---
def corregir_base_datos():
    conn = sqlite3.connect("finanzas.db")
    c = conn.cursor()
    
    # 1. Asegurar que la columna 'Cuenta' existe (basado en tu esquema detectado)
    c.execute("PRAGMA table_info(gastos_fijos)")
    cols = [col[1] for col in c.fetchall()]
    if 'Cuenta' not in cols:
        c.execute("ALTER TABLE gastos_fijos ADD COLUMN Cuenta TEXT DEFAULT 'DÉBITO'")
    
    # 2. MIGRACIÓN CRÍTICA: Mover datos de 'CuentaDebito' o 'Otra' a la columna 'Cuenta'
    # [span_3](start_span)Esto rescata Alquiler, Celular, etc., que actualmente están como 'OTRA' [cite: 181-184]
    c.execute("""
        UPDATE gastos_fijos 
        SET Cuenta = 'DÉBITO' 
        WHERE (Cuenta IS NULL OR Cuenta = '' OR Cuenta = 'OTRA' OR Cuenta = 'Otra')
    """)
    
    # 3. Normalizar nombres a mayúsculas para evitar fallos de filtro
    c.execute("UPDATE gastos SET Tarjeta = UPPER(TRIM(Tarjeta)) WHERE Tarjeta IS NOT NULL")
    c.execute("UPDATE gastos_fijos SET Cuenta = UPPER(TRIM(Cuenta)) WHERE Cuenta IS NOT NULL")
    
    conn.commit()
    conn.close()

def main():
    corregir_base_datos()
    st.sidebar.title("⚙️ Ajustes")
    
    # Cargar Datos
    conn = sqlite3.connect("finanzas.db")
    df_g = pd.read_sql_query("SELECT * FROM gastos", conn)
    df_f = pd.read_sql_query("SELECT * FROM gastos_fijos", conn)
    conn.close()

    tab1, tab2, tab3 = st.tabs(["➕ Ingreso", "📋 Por Tarjeta", "📊 Proyección"])

    with tab2:
        # Lista de medios que la app mostrará
        lista_medios = ["DÉBITO", "BROU", "OCA", "SANTANDER"]
        
        for m in lista_medios:
            # Filtrar gastos por el medio actual
            sub_g = df_g[df_g['Tarjeta'].str.upper() == m.upper()]
            sub_f = df_f[(df_f['Cuenta'].str.upper() == m.upper()) & (df_f['Activo'] == 1)]
            
            total_seccion = sub_g['Monto'].sum() + sub_f['Monto'].sum()
            
            with st.expander(f"🏦 {m} — TOTAL: ${float_a_monto_uy(total_seccion)}"):
                # Mostrar Gastos Fijos (Aquí aparecerán Alquiler, Celular, etc.)
                st.write("**🏠 Gastos Fijos Activos**")
                if sub_f.empty:
                    st.info(f"No hay gastos fijos asignados a {m}")
                else:
                    for _, r in sub_f.iterrows():
                        col1, col2 = st.columns([4, 1])
                        col1.write(f"✅ {r['Descripcion']} ({r['Persona']}): ${float_a_monto_uy(r['Monto'])}")
                        # Opción para cambiarlo de cuenta si 'DÉBITO' no es la correcta
                        nueva_cta = col2.selectbox("Mover a:", lista_medios, key=f"f{r['id']}", index=lista_medios.index(m))
                        if nueva_cta != m:
                            ejecutar_query("UPDATE gastos_fijos SET Cuenta=? WHERE id=?", (nueva_cta, r['id']))
                            st.rerun()

                st.divider()
                
                # Mostrar Compras en Cuotas
                st.write("**💳 Cuotas**")
                if sub_g.empty:
                    st.info(f"No hay compras en cuotas en {m}")
                else:
                    for _, r in sub_g.iterrows():
                        st.write(f"• {r['Descripcion']} ({r['Persona']}): ${float_a_monto_uy(r['Monto'])}")

if __name__ == "__main__":
    main()
