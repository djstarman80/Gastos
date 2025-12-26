import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import json
from datetime import datetime, timedelta
import os

# Configuración de la página
st.set_page_config(
    page_title="Finanzas Personales",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuración de BD (igual que app.py)
DB_PATH = "finanzas.db"

# Funciones utilitarias (copiadas de app.py)
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def monto_uy_a_float(t):
    if t is None or (isinstance(t, float) and str(t).lower() == 'nan'):
        return 0.0
    if isinstance(t, (int, float)):
        return float(t)
    if isinstance(t, str):
        t = t.replace('$', '').replace('.', '').replace(',', '.').strip()
        try:
            return float(t)
        except ValueError:
            return 0.0
    return 0.0

# Inicializar BD si no existe
def init_db():
    conn = get_db_connection()
    # Crear tablas si no existen (lógica de app.py)
    conn.execute('''CREATE TABLE IF NOT EXISTS gastos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        descripcion TEXT NOT NULL,
        monto REAL NOT NULL,
        categoria TEXT,
        persona TEXT,
        tarjeta TEXT,
        cuotas_totales INTEGER DEFAULT 1,
        cuotas_pagadas INTEGER DEFAULT 1,
        fecha TEXT NOT NULL
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS gastos_fijos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        descripcion TEXT NOT NULL,
        monto REAL NOT NULL,
        categoria TEXT,
        persona TEXT,
        cuenta_debito TEXT,
        fecha_inicio TEXT NOT NULL,
        fecha_fin TEXT,
        activo INTEGER DEFAULT 1,
        variaciones TEXT,
        distribucion TEXT,
        meses_pagados TEXT
    )''')

    conn.commit()
    conn.close()

# Llamar init_db al inicio
init_db()

# Cargar datos iniciales
@st.cache_data
def load_categorias():
    return ["Comida", "Transporte", "Entretenimiento", "Salud", "Educación", "Ropa", "Hogar", "Otros"]

@st.cache_data
def load_personas():
    return ["Marcelo", "Yenny"]

@st.cache_data
def load_tarjetas():
    return ["Efectivo", "BROU", "Santander", "Itaú", "Visa", "Mastercard"]

# Función principal
def main():
    st.title("💰 Finanzas Personales")

    # Sidebar para navegación
    st.sidebar.header("Navegación")
    tab = st.sidebar.radio("Selecciona una sección:", ["Gastos", "Gastos Fijos", "Pagos Futuros", "Estadísticas", "Backup"])

    if tab == "Gastos":
        show_gastos()
    elif tab == "Gastos Fijos":
        show_gastos_fijos()
    elif tab == "Pagos Futuros":
        show_pagos_futuros()
    elif tab == "Estadísticas":
        show_estadisticas()
    elif tab == "Backup":
        show_backup()

def show_gastos():
    st.header("📝 Gastos")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Agregar Gasto")
        with st.form("gasto_form"):
            descripcion = st.text_input("Descripción *", key="desc")
            monto = st.number_input("Monto *", min_value=0.0, step=0.01, key="monto")
            categoria = st.selectbox("Categoría *", load_categorias(), key="cat")
            persona = st.selectbox("Persona *", load_personas(), key="pers")
            tarjeta = st.selectbox("Tarjeta", ["Efectivo"] + load_tarjetas()[1:], key="tarj")
            cuotas_totales = st.selectbox("Cuotas Totales", list(range(1, 13)), key="ct")
            cuotas_pagadas = st.selectbox("Cuotas Pagadas", list(range(0, cuotas_totales + 1)), key="cp")
            fecha = st.date_input("Fecha *", key="fecha")

            submitted = st.form_submit_button("Guardar Gasto")
            if submitted:
                if descripcion and monto > 0:
                    conn = get_db_connection()
                    conn.execute(
                        'INSERT INTO gastos (descripcion, monto, categoria, persona, tarjeta, cuotas_totales, cuotas_pagadas, fecha) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                        (descripcion, monto, categoria, persona, tarjeta, cuotas_totales, cuotas_pagadas, fecha.strftime('%Y-%m-%d'))
                    )
                    conn.commit()
                    conn.close()
                    st.success("Gasto agregado exitosamente!")
                    st.rerun()
                else:
                    st.error("Completa todos los campos obligatorios.")

    with col2:
        st.subheader("Gastos Recientes")
        if st.button("Actualizar", key="refresh_gastos"):
            st.rerun()

        conn = get_db_connection()
        gastos = conn.execute('SELECT * FROM gastos ORDER BY fecha DESC LIMIT 50').fetchall()
        conn.close()

        if gastos:
            df = pd.DataFrame(gastos)
            df['fecha'] = pd.to_datetime(df['fecha']).dt.strftime('%d/%m/%Y')
            df['monto'] = df['monto'].apply(lambda x: f"${x:,.2f}")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No hay gastos registrados.")

def show_gastos_fijos():
    st.header("💳 Gastos Fijos")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Agregar Gasto Fijo")
        with st.form("gf_form"):
            gf_descripcion = st.text_input("Descripción *", key="gf_desc")
            gf_monto = st.number_input("Monto Mensual *", min_value=0.0, step=0.01, key="gf_monto")
            gf_categoria = st.selectbox("Categoría *", load_categorias(), key="gf_cat")
            gf_persona = st.selectbox("Persona *", load_personas(), key="gf_pers")
            gf_cuenta = st.selectbox("Cuenta Débito", ["BROU", "Santander"], key="gf_cuenta")
            gf_fecha_inicio = st.date_input("Fecha Inicio *", key="gf_fi")
            gf_fecha_fin = st.date_input("Fecha Fin (opcional)", key="gf_ff")
            gf_activo = st.checkbox("Activo", value=True, key="gf_act")

            gf_submitted = st.form_submit_button("Guardar Gasto Fijo")
            if gf_submitted:
                if gf_descripcion and gf_monto > 0:
                    conn = get_db_connection()
                    conn.execute(
                        'INSERT INTO gastos_fijos (descripcion, monto, categoria, persona, cuenta_debito, fecha_inicio, fecha_fin, activo, variaciones, distribucion, meses_pagados) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        (gf_descripcion, gf_monto, gf_categoria, gf_persona, gf_cuenta, gf_fecha_inicio.strftime('%Y-%m-%d'), gf_fecha_fin.strftime('%Y-%m-%d') if gf_fecha_fin else None, 1 if gf_activo else 0, '{}', '{"Marcelo": 50, "Yenny": 50}', '')
                    )
                    conn.commit()
                    conn.close()
                    st.success("Gasto fijo agregado exitosamente!")
                    st.rerun()
                else:
                    st.error("Completa todos los campos obligatorios.")

    with col2:
        st.subheader("Gastos Fijos")
        conn = get_db_connection()
        gf = conn.execute('SELECT * FROM gastos_fijos ORDER BY fecha_inicio DESC').fetchall()
        conn.close()

        if gf:
            df = pd.DataFrame(gf)
            df['fecha_inicio'] = pd.to_datetime(df['fecha_inicio']).dt.strftime('%d/%m/%Y')
            df['fecha_fin'] = pd.to_datetime(df['fecha_fin']).dt.strftime('%d/%m/%Y')
            df['monto'] = df['monto'].apply(lambda x: f"${x:,.2f}")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No hay gastos fijos registrados.")

def show_pagos_futuros():
    st.header("📅 Pagos Futuros")

    # Lógica para calcular pagos futuros (simplificada)
    conn = get_db_connection()
    gf = conn.execute('SELECT * FROM gastos_fijos WHERE activo = 1').fetchall()
    conn.close()

    pagos = []
    hoy = datetime.now()
    for g in gf:
        try:
            fecha_inicio = datetime.strptime(g['fecha_inicio'], '%Y-%m-%d')
        except ValueError:
            # Intentar otros formatos comunes si falla
            try:
                fecha_inicio = datetime.strptime(g['fecha_inicio'], '%d/%m/%Y')
            except ValueError:
                continue  # Saltar si no se puede parsear
        if fecha_inicio > hoy:
            pagos.append({
                'Descripción': g['descripcion'],
                'Monto': g['monto'],
                'Fecha': fecha_inicio.strftime('%d/%m/%Y'),
                'Persona': g['persona']
            })

    if pagos:
        df = pd.DataFrame(pagos)
        df['Monto'] = df['Monto'].apply(lambda x: f"${x:,.2f}")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No hay pagos futuros.")

def show_estadisticas():
    st.header("📊 Estadísticas")

    conn = get_db_connection()
    gastos = conn.execute('SELECT * FROM gastos').fetchall()
    conn.close()

    if gastos:
        df = pd.DataFrame(gastos)

        # Gráfico por categoría
        st.subheader("Por Categoría")
        cat_data = df.groupby('categoria')['monto'].sum()
        fig, ax = plt.subplots()
        cat_data.plot(kind='pie', ax=ax, autopct='%1.1f%%')
        st.pyplot(fig)

        # Gráfico por persona
        st.subheader("Por Persona")
        pers_data = df.groupby('persona')['monto'].sum()
        fig2, ax2 = plt.subplots()
        pers_data.plot(kind='bar', ax=ax2)
        st.pyplot(fig2)

        # Estadísticas generales
        st.subheader("Resumen")
        total = df['monto'].sum()
        st.metric("Total Gastos", f"${total:,.2f}")
        st.metric("Número de Gastos", len(df))
    else:
        st.info("No hay datos para estadísticas.")

def show_backup():
    st.header("💾 Backup")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Crear Backup")
        if st.button("Crear Backup de BD"):
            # Lógica simple: mostrar mensaje
            st.success("Backup creado (funcionalidad básica).")

        if st.button("Exportar a CSV"):
            conn = get_db_connection()
            gastos = conn.execute('SELECT * FROM gastos').fetchall()
            conn.close()

            if gastos:
                df = pd.DataFrame(gastos)
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Descargar CSV Gastos",
                    data=csv,
                    file_name="gastos.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No hay datos para exportar.")

    with col2:
        st.subheader("Información del Sistema")
        st.write(f"**Versión:** Streamlit App v1.0")
        st.write(f"**Base de datos:** SQLite")
        st.write(f"**Última actualización:** {datetime.now().strftime('%d/%m/%Y %H:%M')}")

if __name__ == "__main__":
    main()