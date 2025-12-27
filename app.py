import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="M&Y Finanzas", layout="wide", page_icon="💰")

if 'ultimo_borrado' not in st.session_state: st.session_state.ultimo_borrado = None

MESES_NOMBRE = {1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 
                7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'}

# --- FUNCIONES DE APOYO ---
def monto_uy_a_float(t):
    if not t: return 0.0
    try:
        # Limpia formatos tipo $ 1.250,50
        s = str(t).replace("$", "").replace(".", "").replace(",", ".").strip()
        return float(s)
    except: return 0.0

def float_a_monto_uy(v):
    return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def ejecutar_query(q, p=()):
    conn = sqlite3.connect("finanzas.db")
    conn.execute(q, p); conn.commit(); conn.close()

# --- REPARACIÓN Y MIGRACIÓN ROBUSTA DE BASE DE DATOS ---
def corregir_base_datos():
    conn = sqlite3.connect("finanzas.db")
    c = conn.cursor()
    
    # 1. Asegurar tablas base
    c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, Fecha TEXT, Monto REAL, Persona TEXT, Descripcion TEXT, Tarjeta TEXT, CuotasTotales INTEGER, CuotasPagadas INTEGER, MesesPagados TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos_fijos (id INTEGER PRIMARY KEY AUTOINCREMENT, Descripcion TEXT, Monto REAL, Persona TEXT, Cuenta TEXT, Activo BOOLEAN, MesesPagados TEXT)")
    
    # 2. Agregar columnas faltantes dinámicamente (Evita el OperationalError)
    # Para GASTOS
    c.execute("PRAGMA table_info(gastos)")
    cols_g = [col[1] for col in c.fetchall()]
    if 'Tarjeta' not in cols_g:
        c.execute("ALTER TABLE gastos ADD COLUMN Tarjeta TEXT DEFAULT 'BROU'")
        
    # Para GASTOS FIJOS
    c.execute("PRAGMA table_info(gastos_fijos)")
    cols_f_info = c.fetchall()
    cols_f = [col[1] for col in cols_f_info]
    
    if 'Cuenta' not in cols_f:
        c.execute("ALTER TABLE gastos_fijos ADD COLUMN Cuenta TEXT DEFAULT 'DÉBITO'")
    
    # 3. Migrar datos de la columna vieja 'CuentaDebito' si existe
    if 'CuentaDebito' in cols_f:
        c.execute("UPDATE gastos_fijos SET Cuenta = CuentaDebito WHERE (Cuenta IS NULL OR Cuenta = '' OR Cuenta = 'DÉBITO') AND CuentaDebito IS NOT NULL")

    # 4. Limpieza de datos (Normalización)
    c.execute("UPDATE gastos SET Tarjeta = UPPER(TRIM(Tarjeta)) WHERE Tarjeta IS NOT NULL")
    c.execute("UPDATE gastos_fijos SET Cuenta = UPPER(TRIM(Cuenta)) WHERE Cuenta IS NOT NULL")
    
    conn.commit()
    conn.close()

# --- INTERFAZ PRINCIPAL ---
def main():
    corregir_base_datos()
    st.sidebar.title("⚙️ Ajustes")
    dia_cierre = st.sidebar.slider("Día de Cierre", 1, 28, 10)

    # BANNER DESHACER (Papelera de reciclaje)
    if st.session_state.ultimo_borrado:
        b = st.session_state.ultimo_borrado
        with st.container():
            col_inf, col_undo = st.columns([3, 1])
            col_inf.warning(f"⚠️ Eliminado: {b['nombre']}")
            if col_undo.button("↩️ DESHACER"):
                # Re-insertar usando diccionario para evitar errores de columnas
                tabla = b['tabla']
                datos = b['datos']
                # Eliminar ID para que SQL genere uno nuevo
                if 'id' in datos: del datos['id']
                columnas = ', '.join(datos.keys())
                placeholders = ', '.join(['?'] * len(datos))
                ejecutar_query(f"INSERT INTO {tabla} ({columnas}) VALUES ({placeholders})", tuple(datos.values()))
                st.session_state.ultimo_borrado = None
                st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["➕ Ingreso", "📋 Por Tarjeta", "📊 Proyección", "💾 Backup"])

    # --- TAB 1: INGRESO UNIFICADO ---
    with tab1:
        with st.form("f_uni", clear_on_submit=True):
            tipo = st.radio("Tipo de Gasto", ["Gasto en Cuotas", "Gasto Fijo"], horizontal=True)
            desc = st.text_input("Descripción")
            monto = st.text_input("Monto ($)")
            c1, c2 = st.columns(2)
            pers = c1.selectbox("Responsable", ["Marcelo", "Yenny"])
            if tipo == "Gasto en Cuotas":
                medio = c2.selectbox("Tarjeta", ["BROU", "OCA", "SANTANDER"])
                cuotas = st.number_input("Cuotas Totales", 1, 36, 1)
            else:
                medio = c2.selectbox("Medio", ["DÉBITO", "BROU", "OCA", "SANTANDER"])
                cuotas = 1
            if st.form_submit_button("✅ GUARDAR", use_container_width=True):
                m_f = monto_uy_a_float(monto)
                if tipo == "Gasto en Cuotas":
                    ejecutar_query("INSERT INTO gastos (Fecha, Monto, Persona, Descripcion, Tarjeta, CuotasTotales, CuotasPagadas, MesesPagados) VALUES (?,?,?,?,?,?,?,?)", (datetime.today().strftime("%d/%m/%Y"), m_f, pers, desc, medio, cuotas, 0, ""))
                else:
                    ejecutar_query("INSERT INTO gastos_fijos (Descripcion, Monto, Persona, Cuenta, Activo, MesesPagados) VALUES (?,?,?,?,?,?)", (desc, m_f, pers, medio, 1, ""))
                st.rerun()

    # --- TAB 2: GESTIÓN POR TARJETA (CON TOTALES Y EDICIÓN) ---
    with tab2:
        conn = sqlite3.connect("finanzas.db")
        df_g = pd.read_sql_query("SELECT * FROM gastos", conn)
        df_f = pd.read_sql_query("SELECT * FROM gastos_fijos", conn)
        conn.close()

        lista_medios = ["DÉBITO", "BROU", "OCA", "SANTANDER"]
        for m in lista_medios:
            sub_g = df_g[df_g['Tarjeta'].str.upper() == m.upper()]
            sub_f_act = df_f[(df_f['Cuenta'].str.upper() == m.upper()) & (df_f['Activo'] == 1)]
            total = sub_g['Monto'].sum() + sub_f_act['Monto'].sum()
            
            with st.expander(f"🏦 {m} — TOTAL: ${float_a_monto_uy(total)}"):
                # Cuotas
                st.write("**💳 Cuotas**")
                for _, r in sub_g.iterrows():
                    c_txt, c_sel, c_del = st.columns([3, 1.5, 0.5])
                    c_txt.write(f"• {r['Descripcion']} ({r['Persona']}): ${float_a_monto_uy(r['Monto'])}")
                    nueva = c_sel.selectbox("Mover:", lista_medios, key=f"selg{r['id']}", index=lista_medios.index(m) if m in lista_medios else 0)
                    if nueva != m:
                        ejecutar_query("UPDATE gastos SET Tarjeta=? WHERE id=?", (nueva, r['id'])); st.rerun()
                    if c_del.button("🗑️", key=f"delg{r['id']}"):
                        st.session_state.ultimo_borrado = {'tabla':'gastos', 'datos':r.to_dict(), 'nombre':r['Descripcion']}
                        ejecutar_query("DELETE FROM gastos WHERE id=?", (r['id'],)); st.rerun()
                
                st.divider()
                # Fijos
                st.write("**🏠 Gastos Fijos**")
                sub_f_all = df_f[df_f['Cuenta'].str.upper() == m.upper()]
                for _, r in sub_f_all.iterrows():
                    c_txt, c_sel, c_del = st.columns([3, 1.5, 0.5])
                    icon = "✅" if r['Activo'] else "❌"
                    c_txt.write(f"{icon} {r['Descripcion']} ({r['Persona']}): ${float_a_monto_uy(r['Monto'])}")
                    nueva = c_sel.selectbox("Mover:", lista_medios, key=f"self{r['id']}", index=lista_medios.index(m) if m in lista_medios else 0)
                    if nueva != m:
                        ejecutar_query("UPDATE gastos_fijos SET Cuenta=? WHERE id=?", (nueva, r['id'])); st.rerun()
                    if c_del.button("🗑️", key=f"delf{r['id']}"):
                        st.session_state.ultimo_borrado = {'tabla':'gastos_fijos', 'datos':r.to_dict(), 'nombre':r['Descripcion']}
                        ejecutar_query("DELETE FROM gastos_fijos WHERE id=?", (r['id'],)); st.rerun()

    # --- TAB 3: PROYECCIÓN MENSUAL ---
    with tab3:
        hoy = datetime.today()
        # Si hoy es después del cierre, la proyección arranca el mes que viene
        inicio_p = hoy.replace(day=1) + pd.DateOffset(months=1) if hoy.day >= dia_cierre else hoy.replace(day=1)
        
        for i in range(6):
            mes_f = inicio_p + pd.DateOffset(months=i)
            sm, sy = 0.0, 0.0
            # Sumar Fijos Activos
            for _, f in df_f[df_f['Activo']==1].iterrows():
                if f['Persona'] == "Marcelo": sm += f['Monto']
                else: sy += f['Monto']
            # Sumar Cuotas Pendientes
            for _, g in df_g.iterrows():
                if i < (g['CuotasTotales'] - g['CuotasPagadas']):
                    if g['Persona'] == "Marcelo": sm += g['Monto']
                    else: sy += g['Monto']
            
            with st.container(border=True):
                st.markdown(f"#### 📅 {MESES_NOMBRE[mes_f.month]} {mes_f.year}")
                c_m, c_y = st.columns(2)
                c_m.metric("Marcelo", f"${float_a_monto_uy(sm)}")
                c_y.metric("Yenny", f"${float_a_monto_uy(sy)}")
                st.write(f"**Total Mensual: ${float_a_monto_uy(sm+sy)}**")

    # --- TAB 4: BACKUP ---
    with tab4:
        if os.path.exists("finanzas.db"):
            with open("finanzas.db", "rb") as f:
                st.download_button("📥 Descargar Base de Datos", f, "finanzas.db")

if __name__ == "__main__":
    main()
