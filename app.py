import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import json
import os
from fpdf import FPDF
import logging
from dateutil.relativedelta import relativedelta
import warnings
warnings.simplefilter(action="ignore", category=FutureWarning)

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler('finanzas_debug.log', maxBytes=10*1024*1024, backupCount=5),
        logging.StreamHandler()
    ]
)

# Cache para formateo de moneda
_format_cache = {}

MESES_NUMERO = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}

MESES_ABREVIATURA = {
    1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr',
    5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Ago',
    9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'
}

def monto_uy_a_float(t):
    if t is None or (isinstance(t, float) and pd.isna(t)):
        return 0.0
    if isinstance(t, (int, float)):
        return float(t)
    
    s = str(t).strip()
    s = s.replace("$", "").replace(" ", "")
    
    if not s:
        return 0.0
    
    try:
        return float(s)
    except ValueError:
        pass
    
    tiene_punto = "." in s
    tiene_coma = "," in s
    
    if not tiene_punto and not tiene_coma:
        try:
            return float(s)
        except:
            return 0.0
    
    elif tiene_coma and not tiene_punto:
        try:
            return float(s.replace(",", "."))
        except:
            return 0.0
    
    elif tiene_punto and not tiene_coma:
        partes = s.split(".")
        if len(partes) > 2:
            if len(partes[-1]) == 2:
                enteros = "".join(partes[:-1])
                decimales = partes[-1]
                return float(f"{enteros}.{decimales}")
            else:
                return float("".join(partes))
        else:
            return float(s)
    
    else:
        s_sin_puntos = s.replace(".", "")
        s_final = s_sin_puntos.replace(",", ".")
        try:
            return float(s_final)
        except:
            return 0.0

def limpiar_texto_pdf(texto):
    if not isinstance(texto, str):
        texto = str(texto)
    import re
    texto = ''.join(c for c in texto if ord(c) < 256)
    return texto

def float_a_monto_uy(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "0,00"

    cache_key = round(float(v), 2) if isinstance(v, (int, float)) else str(v)
    if cache_key in _format_cache:
        return _format_cache[cache_key]

    try:
        v = float(v)

        if abs(v) < 0.01 and abs(v) > 0:
            result = f"{v:.4f}".replace(".", ",")
        else:
            parte_entera = int(abs(v))
            parte_decimal = round(abs(v) - parte_entera, 2)

            parte_entera_str = f"{parte_entera:,}".replace(",", ".")
            decimal_str = f"{parte_decimal:.2f}".split(".")[1]

            result = f"{parte_entera_str},{decimal_str}"

            if v < 0:
                result = f"-{result}"

        _format_cache[cache_key] = result
        return result

    except Exception:
        return str(v)

def fecha_obj_a_uy(f):
    if pd.isna(f) or f is None: return ""
    return f.strftime("%d/%m/%Y")

def init_db():
    conn = sqlite3.connect("finanzas.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Fecha TEXT,
            Monto REAL,
            Categoria TEXT,
            Persona TEXT,
            Descripcion TEXT,
            Tarjeta TEXT,
            CuotasTotales INTEGER,
            CuotasPagadas INTEGER,
            MesesPagados TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos_fijos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Descripcion TEXT NOT NULL,
            Monto REAL NOT NULL,
            Categoria TEXT,
            Persona TEXT,
            CuentaDebito TEXT,
            FechaInicio TEXT,
            FechaFin TEXT,
            Activo BOOLEAN DEFAULT 1,
            Variaciones TEXT,
            Distribucion TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS presupuestos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Mes TEXT NOT NULL,
            Categoria TEXT NOT NULL,
            MontoPresupuesto REAL NOT NULL,
            UNIQUE(Mes, Categoria)
        )
    """)

    cursor.execute("PRAGMA table_info(gastos)")
    columnas = cursor.fetchall()
    nombres_columnas = [col[1] for col in columnas]
    
    if "MesesPagados" not in nombres_columnas:
        cursor.execute("ALTER TABLE gastos ADD COLUMN MesesPagados TEXT DEFAULT ''")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gastos_fecha ON gastos(Fecha)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gastos_persona ON gastos(Persona)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gastos_tarjeta ON gastos(Tarjeta)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gastos_categoria ON gastos(Categoria)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gastos_fijos_activo ON gastos_fijos(Activo)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gastos_fijos_persona ON gastos_fijos(Persona)")

    cursor.execute("PRAGMA table_info(gastos_fijos)")
    columnas_fijos = cursor.fetchall()
    nombres_columnas_fijos = [col[1] for col in columnas_fijos]

    if "MesesPagados" not in nombres_columnas_fijos:
        cursor.execute("ALTER TABLE gastos_fijos ADD COLUMN MesesPagados TEXT DEFAULT ''")

    conn.commit()
    conn.close()

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, limpiar_texto_pdf('Reporte Financiero - Marcelo & Yenny'), 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, limpiar_texto_pdf(f'Generado el: {datetime.now().strftime("%d/%m/%Y %H:%M")}'), 0, 1, 'C')
        self.ln(10)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')
    
    def add_section_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, limpiar_texto_pdf(title), 0, 1, 'L')
        self.ln(2)

    def add_table_header(self, headers, col_widths):
        self.set_font('Arial', 'B', 10)
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 10, limpiar_texto_pdf(header), 1, 0, 'C')
        self.ln()

    def add_table_row(self, data, col_widths):
        self.set_font('Arial', '', 9)
        for i, cell in enumerate(data):
            self.cell(col_widths[i], 8, limpiar_texto_pdf(cell), 1, 0, 'L')
        self.ln()

    def add_summary_box(self, title, value):
        self.set_font('Arial', 'B', 10)
        self.cell(40, 10, limpiar_texto_pdf(title), 1, 0, 'L')
        self.set_font('Arial', '', 10)
        self.cell(0, 10, limpiar_texto_pdf(value), 1, 1, 'R')

def cargar_datos():
    conn = sqlite3.connect("finanzas.db")
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gastos'")
        tabla_existe = cursor.fetchone() is not None
        
        if not tabla_existe:
            init_db()
            df = pd.DataFrame(columns=[
                "id", "Fecha", "Monto", "Categoria", "Persona", 
                "Descripcion", "Tarjeta", "CuotasTotales", "CuotasPagadas", "MesesPagados"
            ])
        else:
            cursor.execute("PRAGMA table_info(gastos)")
            columnas = cursor.fetchall()
            nombres_columnas = [col[1] for col in columnas]
            
            if "MesesPagados" not in nombres_columnas:
                cursor.execute("ALTER TABLE gastos ADD COLUMN MesesPagados TEXT DEFAULT ''")
                conn.commit()
            
            df = pd.read_sql_query("SELECT * FROM gastos", conn)
            
            if df.empty:
                df = pd.DataFrame(columns=[
                    "id", "Fecha", "Monto", "Categoria", "Persona", 
                    "Descripcion", "Tarjeta", "CuotasTotales", "CuotasPagadas", "MesesPagados"
                ])
            else:
                df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
                if "MesesPagados" not in df.columns:
                    df["MesesPagados"] = ""
    
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        df = pd.DataFrame(columns=[
            "id", "Fecha", "Monto", "Categoria", "Persona", 
            "Descripcion", "Tarjeta", "CuotasTotales", "CuotasPagadas", "MesesPagados"
        ])
    
    finally:
        conn.close()
    
    return df

def cargar_gastos_fijos():
    conn = sqlite3.connect("finanzas.db")
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gastos_fijos'")
        tabla_existe = cursor.fetchone() is not None
        
        if not tabla_existe:
            init_db()
            df = pd.DataFrame(columns=[
                "id", "Descripcion", "Monto", "Categoria", "Persona",
                "CuentaDebito", "FechaInicio", "FechaFin", "Activo",
                "Variaciones", "Distribucion", "MesesPagados"
            ])
        else:
            cursor.execute("PRAGMA table_info(gastos_fijos)")
            columnas_db = cursor.fetchall()
            nombres_columnas_db = [col[1] for col in columnas_db]
            
            mapeo_columnas = {
                'id': 'id',
                'Descripcion': None,
                'Monto': 'Monto',
                'Categoria': None,
                'Persona': 'Persona',
                'CuentaDebito': None,
                'FechaInicio': 'FechaInicio',
                'FechaFin': 'FechaFin',
                'Activo': 'Activo',
                'Variaciones': 'Variaciones',
                'Distribucion': None,
                'MesesPagados': 'MesesPagados'
            }
            
            for nombre_col in ['Descripción', 'Descripcion']:
                if nombre_col in nombres_columnas_db:
                    mapeo_columnas['Descripcion'] = nombre_col
                    break
            
            for nombre_col in ['Categoría', 'Categoria']:
                if nombre_col in nombres_columnas_db:
                    mapeo_columnas['Categoria'] = nombre_col
                    break
            
            for nombre_col in ['CuentaDébito', 'CuentaDebito']:
                if nombre_col in nombres_columnas_db:
                    mapeo_columnas['CuentaDebito'] = nombre_col
                    break
            
            for nombre_col in ['Distribución', 'Distribucion']:
                if nombre_col in nombres_columnas_db:
                    mapeo_columnas['Distribucion'] = nombre_col
                    break
            
            columnas_select = []
            for col_interna, col_real in mapeo_columnas.items():
                if col_real:
                    if col_real != col_interna:
                        columnas_select.append(f'"{col_real}" as "{col_interna}"')
                    else:
                        columnas_select.append(f'"{col_real}"')
            
            if columnas_select:
                query = f"SELECT {', '.join(columnas_select)} FROM gastos_fijos"
                df = pd.read_sql_query(query, conn)
            else:
                df = pd.DataFrame(columns=[
                    "id", "Descripcion", "Monto", "Categoria", "Persona",
                    "CuentaDebito", "FechaInicio", "FechaFin", "Activo",
                    "Variaciones", "Distribucion"
                ])
            
            if df.empty:
                df = pd.DataFrame(columns=[
                    "id", "Descripcion", "Monto", "Categoria", "Persona",
                    "CuentaDebito", "FechaInicio", "FechaFin", "Activo",
                    "Variaciones", "Distribucion"
                ])
            else:
                columnas_esperadas = [
                    "id", "Descripcion", "Monto", "Categoria", "Persona",
                    "CuentaDebito", "FechaInicio", "FechaFin", "Activo",
                    "Variaciones", "Distribucion", "MesesPagados"
                ]
                
                for col in columnas_esperadas:
                    if col not in df.columns:
                        df[col] = None
                
                for idx in df.index:
                    try:
                        variaciones_str = df.loc[idx, 'Variaciones']
                        if pd.isna(variaciones_str) or variaciones_str == '' or variaciones_str is None:
                            df.at[idx, 'Variaciones'] = {}
                        else:
                            try:
                                df.at[idx, 'Variaciones'] = json.loads(str(variaciones_str))
                            except:
                                df.at[idx, 'Variaciones'] = {}
                        
                        distribucion_str = df.loc[idx, 'Distribucion']
                        if pd.isna(distribucion_str) or distribucion_str == '' or distribucion_str is None:
                            df.at[idx, 'Distribucion'] = {"Marcelo": 50, "Yenny": 50}
                        else:
                            try:
                                df.at[idx, 'Distribucion'] = json.loads(str(distribucion_str))
                            except:
                                df.at[idx, 'Distribucion'] = {"Marcelo": 50, "Yenny": 50}
                    except Exception as e:
                        df.at[idx, 'Variaciones'] = {}
                        df.at[idx, 'Distribucion'] = {"Marcelo": 50, "Yenny": 50}
                
                if 'Monto' in df.columns:
                    df['Monto'] = pd.to_numeric(df['Monto'], errors='coerce').fillna(0)
                if 'Activo' in df.columns:
                    def to_bool(val):
                        if isinstance(val, bool):
                            return val
                        elif isinstance(val, (int, float)):
                            return bool(val)
                        elif isinstance(val, str):
                            return val.lower() in ['true', '1', 'yes', 'sí', 'si', 't', 'y']
                        else:
                            return False
                    
                    df['Activo'] = df['Activo'].apply(to_bool)
    
    except Exception as e:
        st.error(f"Error al cargar gastos fijos: {e}")
        df = pd.DataFrame(columns=[
            "id", "Descripcion", "Monto", "Categoria", "Persona",
            "CuentaDebito", "FechaInicio", "FechaFin", "Activo",
            "Variaciones", "Distribucion", "MesesPagados"
        ])
    
    finally:
        conn.close()
    
    return df

def guardar_gasto(gasto):
    conn = sqlite3.connect("finanzas.db")
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(gastos)")
    columnas = cursor.fetchall()
    nombres_columnas = [col[1] for col in columnas]
    
    if "MesesPagados" not in nombres_columnas:
        cursor.execute("ALTER TABLE gastos ADD COLUMN MesesPagados TEXT DEFAULT ''")
        conn.commit()
    
    fecha_gasto = gasto["Fecha"]
    dia_gasto = fecha_gasto.day
    
    if dia_gasto >= 5:
        primer_mes_pago = fecha_gasto.replace(day=1) + pd.DateOffset(months=1)
        
        cuotas_pagadas = gasto["CuotasPagadas"]
        if cuotas_pagadas > 0:
            meses_pagados = []
            for i in range(cuotas_pagadas):
                mes_pagado = primer_mes_pago + pd.DateOffset(months=i)
                meses_pagados.append(mes_pagado.strftime("%Y-%m"))
            gasto["MesesPagados"] = ",".join(meses_pagados)
        else:
            gasto["MesesPagados"] = ""
    else:
        gasto["MesesPagados"] = ""
    
    cursor.execute("""
        INSERT INTO gastos (Fecha, Monto, Categoria, Persona, Descripcion, Tarjeta, CuotasTotales, CuotasPagadas, MesesPagados)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        gasto["Fecha"].strftime("%d/%m/%Y"), 
        gasto["Monto"], 
        gasto["Categoría"], 
        gasto["Persona"],
        gasto["Descripción"], 
        gasto["Tarjeta"], 
        gasto["CuotasTotales"], 
        gasto["CuotasPagadas"], 
        gasto.get("MesesPagados", "")
    ))
    conn.commit()
    conn.close()

def guardar_gasto_fijo(gasto_fijo):
    conn = sqlite3.connect("finanzas.db")
    cursor = conn.cursor()
    
    variaciones_json = json.dumps(gasto_fijo.get("Variaciones", {}))
    distribucion_json = json.dumps(gasto_fijo.get("Distribucion", {"Marcelo": 50, "Yenny": 50}))
    
    cursor.execute("PRAGMA table_info(gastos_fijos)")
    columnas_db = cursor.fetchall()
    nombres_columnas_db = [col[1] for col in columnas_db]
    
    descripcion_col = 'Descripcion' if 'Descripcion' in nombres_columnas_db else 'Descripción'
    categoria_col = 'Categoria' if 'Categoria' in nombres_columnas_db else 'Categoría'
    cuenta_col = 'CuentaDebito' if 'CuentaDebito' in nombres_columnas_db else 'CuentaDébito'
    distribucion_col = 'Distribucion' if 'Distribucion' in nombres_columnas_db else 'Distribución'
    
    cursor.execute(f"""
        INSERT INTO gastos_fijos (
            {descripcion_col},
            Monto,
            {categoria_col},
            Persona,
            {cuenta_col},
            FechaInicio,
            FechaFin,
            Activo,
            Variaciones,
            {distribucion_col},
            MesesPagados
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        gasto_fijo["Descripcion"],
        gasto_fijo["Monto"],
        gasto_fijo["Categoria"],
        gasto_fijo["Persona"],
        gasto_fijo["CuentaDebito"],
        gasto_fijo["FechaInicio"],
        gasto_fijo.get("FechaFin", ""),
        1 if gasto_fijo.get("Activo", True) else 0,
        variaciones_json,
        distribucion_json,
        gasto_fijo.get("MesesPagados", "")
    ))
    
    conn.commit()
    conn.close()

def actualizar_gasto_fijo(id, gasto_fijo):
    conn = sqlite3.connect("finanzas.db")
    cursor = conn.cursor()
    
    cursor.execute("""SELECT id FROM gastos_fijos WHERE id=?""", (id,))
    if not cursor.fetchone():
        raise ValueError(f"Gasto fijo con ID {id} no encontrado")
    
    variaciones_json = json.dumps(gasto_fijo.get("Variaciones", {}))
    distribucion_json = json.dumps(gasto_fijo.get("Distribucion", {"Marcelo": 50, "Yenny": 50}))
    
    cursor.execute("PRAGMA table_info(gastos_fijos)")
    columnas_db = cursor.fetchall()
    nombres_columnas_db = [col[1] for col in columnas_db]
    
    descripcion_col = 'Descripcion' if 'Descripcion' in nombres_columnas_db else 'Descripción'
    categoria_col = 'Categoria' if 'Categoria' in nombres_columnas_db else 'Categoría'
    cuenta_col = 'CuentaDebito' if 'CuentaDebito' in nombres_columnas_db else 'CuentaDébito'
    distribucion_col = 'Distribucion' if 'Distribucion' in nombres_columnas_db else 'Distribución'
    
    cursor.execute(f"""
        UPDATE gastos_fijos SET
            {descripcion_col}=?,
            Monto=?,
            {categoria_col}=?,
            Persona=?,
            {cuenta_col}=?,
            FechaInicio=?,
            FechaFin=?,
            Activo=?,
            Variaciones=?,
            {distribucion_col}=?,
            MesesPagados=?
        WHERE id=?
    """, (
        gasto_fijo["Descripcion"],
        gasto_fijo["Monto"],
        gasto_fijo["Categoria"],
        gasto_fijo["Persona"],
        gasto_fijo["CuentaDebito"],
        gasto_fijo["FechaInicio"],
        gasto_fijo.get("FechaFin", ""),
        1 if gasto_fijo.get("Activo", True) else 0,
        variaciones_json,
        distribucion_json,
        gasto_fijo.get("MesesPagados", ""),
        id
    ))
    
    conn.commit()
    conn.close()

def eliminar_gasto_fijo_db(id):
    conn = sqlite3.connect("finanzas.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM gastos_fijos WHERE id=?", (id,))
    conn.commit()
    conn.close()

def actualizar_gasto(id, gasto):
    conn = sqlite3.connect("finanzas.db")
    cursor = conn.cursor()
    
    fecha_gasto = gasto["Fecha"]
    dia_gasto = fecha_gasto.day
    
    if dia_gasto >= 5:
        primer_mes_pago = fecha_gasto.replace(day=1) + pd.DateOffset(months=1)
        
        cuotas_pagadas = gasto["CuotasPagadas"]
        if cuotas_pagadas > 0:
            meses_pagados = []
            for i in range(cuotas_pagadas):
                mes_pagado = primer_mes_pago + pd.DateOffset(months=i)
                meses_pagados.append(mes_pagado.strftime("%Y-%m"))
            meses_pagados_str = ",".join(meses_pagados)
        else:
            meses_pagados_str = ""
    else:
        meses_pagados_str = ""
    
    cursor.execute("""
        UPDATE gastos SET 
            Fecha=?, 
            Monto=?, 
            Categoria=?, 
            Persona=?, 
            Descripcion=?, 
            Tarjeta=?, 
            CuotasTotales=?, 
            CuotasPagadas=?,
            MesesPagados=?
        WHERE id=?
    """, (
        gasto["Fecha"].strftime("%d/%m/%Y"), 
        gasto["Monto"], 
        gasto["Categoría"], 
        gasto["Persona"],
        gasto["Descripción"], 
        gasto["Tarjeta"], 
        gasto["CuotasTotales"], 
        gasto["CuotasPagadas"],
        meses_pagados_str,
        id
    ))
    
    conn.commit()
    conn.close()

def eliminar_gasto(id):
    conn = sqlite3.connect("finanzas.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM gastos WHERE id=?", (id,))
    conn.commit()
    conn.close()

def marcar_pagos_mes_actual():
    hoy = datetime.today()
    mes_actual = hoy.strftime("%Y-%m")
    
    conn = sqlite3.connect("finanzas.db")
    cursor = conn.cursor()
    
    # Marcar gastos normales
    cursor.execute("SELECT id, MesesPagados FROM gastos WHERE MesesPagados NOT LIKE ?", (f"%{mes_actual}%",))
    gastos_pendientes = cursor.fetchall()
    
    for gasto_id, meses_pagados in gastos_pendientes:
        meses_lista = meses_pagados.split(",") if meses_pagados else []
        if mes_actual not in meses_lista:
            meses_lista.append(mes_actual)
            nuevos_meses = ",".join(sorted(set(meses_lista)))
            cursor.execute("UPDATE gastos SET MesesPagados=? WHERE id=?", (nuevos_meses, gasto_id))
    
    # Marcar gastos fijos
    cursor.execute("SELECT id, MesesPagados FROM gastos_fijos WHERE Activo=1 AND MesesPagados NOT LIKE ?", (f"%{mes_actual}%",))
    fijos_pendientes = cursor.fetchall()
    
    for fijo_id, meses_pagados in fijos_pendientes:
        meses_lista = meses_pagados.split(",") if meses_pagados else []
        if mes_actual not in meses_lista:
            meses_lista.append(mes_actual)
            nuevos_meses = ",".join(sorted(set(meses_lista)))
            cursor.execute("UPDATE gastos_fijos SET MesesPagados=? WHERE id=?", (nuevos_meses, fijo_id))
    
    conn.commit()
    conn.close()

def generar_reporte_pdf(df_gastos, df_fijos, filtros_aplicados):
    pdf = PDFReport()
    pdf.add_page()
    
    # Título del reporte
    pdf.add_section_title("Resumen de Gastos")
    
    # Filtros aplicados
    if filtros_aplicados:
        pdf.add_section_title("Filtros Aplicados:")
        for filtro, valor in filtros_aplicados.items():
            pdf.cell(0, 8, limpiar_texto_pdf(f"{filtro}: {valor}"), 0, 1)
        pdf.ln(5)
    
    # Gastos normales
    if not df_gastos.empty:
        pdf.add_section_title("Gastos Normales")
        headers = ["Fecha", "Descripción", "Categoría", "Persona", "Monto", "Cuotas"]
        col_widths = [25, 60, 30, 25, 25, 25]
        pdf.add_table_header(headers, col_widths)
        
        for _, row in df_gastos.iterrows():
            data = [
                fecha_obj_a_uy(row["Fecha"]),
                row["Descripcion"][:30] if len(str(row["Descripcion"])) > 30 else str(row["Descripcion"]),
                str(row["Categoria"]),
                str(row["Persona"]),
                f"${float_a_monto_uy(row['Monto'])}",
                f"{int(row['CuotasPagadas'])}/{int(row['CuotasTotales'])}"
            ]
            pdf.add_table_row(data, col_widths)
        
        total_gastos = df_gastos["Monto"].sum()
        pdf.add_summary_box("Total Gastos:", f"${float_a_monto_uy(total_gastos)}")
    
    pdf.add_page()
    
    # Gastos fijos
    if not df_fijos.empty:
        pdf.add_section_title("Gastos Fijos")
        headers = ["Descripción", "Monto", "Categoría", "Persona", "Estado"]
        col_widths = [60, 25, 30, 25, 25]
        pdf.add_table_header(headers, col_widths)
        
        for _, row in df_fijos.iterrows():
            estado = "Activo" if row["Activo"] else "Inactivo"
            data = [
                str(row["Descripcion"])[:30],
                f"${float_a_monto_uy(row['Monto'])}",
                str(row["Categoria"]),
                str(row["Persona"]),
                estado
            ]
            pdf.add_table_row(data, col_widths)
        
        total_fijos = df_fijos["Monto"].sum()
        pdf.add_summary_box("Total Gastos Fijos:", f"${float_a_monto_uy(total_fijos)}")
    
    return pdf

def main():
    st.set_page_config(page_title="💰 Finanzas Personales - Marcelo & Yenny", layout="wide")
    
    init_db()
    
st.title("💰 Finanzas Personales - Marcelo & Yenny")

# Inicializar estado de sesión
if 'df_gastos' not in st.session_state:
    st.session_state.df_gastos = cargar_datos()
if 'df_fijos' not in st.session_state:
    st.session_state.df_fijos = cargar_gastos_fijos()

# Sidebar con acciones
with st.sidebar:
    st.header("⚡ Acciones")
    accion = st.selectbox("Seleccionar acción", ["Seleccionar", "Exportar PDF", "Backup BD", "Restaurar BD"], key="menu_acciones")
    
    if accion == "Exportar PDF":
        if st.button("Generar PDF", key="gen_pdf"):
            pdf = generar_reporte_pdf(st.session_state.df_gastos, st.session_state.df_fijos, {})
            pdf_output = pdf.output(dest='S').encode('latin-1')
            st.download_button("Descargar PDF", pdf_output, "reporte_financiero.pdf", "application/pdf", key="download_pdf")
    
    elif accion == "Backup BD":
        if st.button("Generar Backup", key="gen_backup"):
            try:
                with open("finanzas.db", "rb") as f:
                    db_data = f.read()
                st.download_button("Descargar Backup", db_data, "finanzas_backup.db", "application/octet-stream", key="download_backup")
            except FileNotFoundError:
                st.error("Base de datos no encontrada")
    
    elif accion == "Restaurar BD":
        uploaded_file = st.file_uploader("Seleccionar archivo .db", type=["db"], key="upload_db")
        if uploaded_file is not None:
            if st.button("Confirmar Restauración", key="restore_btn"):
                try:
                    with open("finanzas.db", "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    st.session_state.df_gastos = cargar_datos()
                    st.session_state.df_fijos = cargar_gastos_fijos()
                    st.success("Base de datos restaurada")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al restaurar: {e}")

# Tabs principales
tab1, tab2, tab3 = st.tabs(["📋 Gastos", "💳 Gastos Fijos", "⏰ Pagos Futuros"])

with tab1:
        st.header("📋 Gestión de Gastos")
        
        # Sidebar para formulario
        with st.sidebar:
            st.header("➕ Agregar/Editar Gasto")
            
            with st.form("gasto_form"):
                fecha = st.date_input("Fecha", datetime.today())
                monto = st.text_input("Monto", "0,00")
                categoria = st.selectbox("Categoría", ["Compras", "Cargo fijo", "Otros", "Supermercado", "Servicios", "Salidas", "Educación", "Salud", "Transporte", "Regalos"])
                persona = st.selectbox("Persona", ["Marcelo", "Yenny"])
                descripcion = st.text_input("Descripción")
                tarjeta = st.selectbox("Tarjeta", ["BROU", "Santander", "OCA", "Otra", "Efectivo", "Transferencia"])
                cuotas_totales = st.selectbox("Cuotas Totales", list(range(1, 13)), index=0)
                cuotas_pagadas = st.selectbox("Cuotas Pagadas", list(range(0, 13)), index=0)
                
                submitted = st.form_submit_button("Guardar Gasto")
                
                if submitted:
                    try:
                        gasto = {
                            "Fecha": fecha,
                            "Monto": monto_uy_a_float(monto),
                            "Categoria": categoria,
                            "Persona": persona,
                            "Descripcion": descripcion,
                            "Tarjeta": tarjeta,
                            "CuotasTotales": cuotas_totales,
                            "CuotasPagadas": cuotas_pagadas
                        }
                        guardar_gasto(gasto)
                        st.session_state.df_gastos = cargar_datos()
                        st.success("✓ Gasto guardado correctamente")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        # Menú de acciones
        st.header("⚡ Acciones")
        accion = st.selectbox("Seleccionar acción", ["Seleccionar", "Exportar PDF", "Backup BD", "Restaurar BD"], key="menu_acciones")
        
        if accion == "Exportar PDF":
            if st.button("Generar PDF", key="gen_pdf"):
                pdf = generar_reporte_pdf(st.session_state.df_gastos, st.session_state.df_fijos, {})
                pdf_output = pdf.output(dest='S').encode('latin-1')
                st.download_button("Descargar PDF", pdf_output, "reporte_financiero.pdf", "application/pdf", key="download_pdf")
        
        elif accion == "Backup BD":
            if st.button("Generar Backup", key="gen_backup"):
                try:
                    with open("finanzas.db", "rb") as f:
                        db_data = f.read()
                    st.download_button("Descargar Backup", db_data, "finanzas_backup.db", "application/octet-stream", key="download_backup")
                except FileNotFoundError:
                    st.error("Base de datos no encontrada")
        
        elif accion == "Restaurar BD":
            uploaded_file = st.file_uploader("Seleccionar archivo .db", type=["db"], key="upload_db")
            if uploaded_file is not None:
                if st.button("Confirmar Restauración", key="restore_btn"):
                    try:
                        with open("finanzas.db", "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        st.session_state.df_gastos = cargar_datos()
                        st.session_state.df_fijos = cargar_gastos_fijos()
                        st.success("Base de datos restaurada")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al restaurar: {e}")
        
        # Filtros
        st.subheader("🔍 Filtros")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            filtro_persona = st.selectbox("Persona", ["Todos"] + ["Marcelo", "Yenny"], key="filtro_persona")
        with col2:
            filtro_tarjeta = st.selectbox("Tarjeta", ["Todos"] + ["BROU", "Santander", "OCA", "Otra", "Efectivo", "Transferencia"], key="filtro_tarjeta")
        with col3:
            hoy = datetime.today()
            meses_opciones = ["Todos"] + [f"{MESES_NUMERO[i]}/{hoy.year}" for i in range(1, 13)]
            filtro_mes = st.selectbox("Mes", meses_opciones, key="filtro_mes")
        with col4:
            categorias_opciones = ["Todos", "Compras", "Cargo fijo", "Otros", "Supermercado", "Servicios", "Salidas", "Educación", "Salud", "Transporte", "Regalos"]
            filtro_categoria = st.selectbox("Categoría", categorias_opciones, key="filtro_categoria")
        
        # Aplicar filtros
        df_filtrado = st.session_state.df_gastos.copy()
        
        if filtro_persona != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Persona"] == filtro_persona]
        
        if filtro_tarjeta != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Tarjeta"] == filtro_tarjeta]
        
        if filtro_mes != "Todos":
            mes_str, año_str = filtro_mes.split("/")
            mes = list(MESES_NUMERO.keys())[list(MESES_NUMERO.values()).index(mes_str)]
            año = int(año_str)
            df_filtrado = df_filtrado[
                (df_filtrado["Fecha"].dt.year == año) &
                (df_filtrado["Fecha"].dt.month == mes)
            ]
        
        if filtro_categoria != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Categoria"] == filtro_categoria]
        
        # Mostrar tabla
        st.subheader("📋 Lista de Gastos")
        
        if not df_filtrado.empty:
            # Formatear datos para display
            df_display = df_filtrado.copy()
            df_display["Fecha"] = df_display["Fecha"].apply(fecha_obj_a_uy)
            df_display["Monto"] = df_display["Monto"].apply(lambda x: f"${float_a_monto_uy(x)}")
            df_display["Cuotas"] = df_display.apply(lambda row: f"{int(row['CuotasPagadas'])}/{int(row['CuotasTotales'])}", axis=1)
            
            st.dataframe(df_display[["id", "Fecha", "Descripcion", "Categoria", "Persona", "Tarjeta", "Monto", "Cuotas"]], use_container_width=True)
            
            # Acciones
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("✏️ Editar Seleccionado"):
                    st.info("Funcionalidad de edición próximamente")
            with col2:
                if st.button("🗑 Eliminar Seleccionado"):
                    st.info("Funcionalidad de eliminación próximamente")
            with col3:
                if st.button("📄 Exportar PDF"):
                    pdf = generar_reporte_pdf(df_filtrado, pd.DataFrame(), {"Persona": filtro_persona, "Tarjeta": filtro_tarjeta, "Mes": filtro_mes, "Categoría": filtro_categoria})
                    pdf_output = pdf.output(dest='S').encode('latin-1')
                    st.download_button("Descargar PDF", pdf_output, "reporte_gastos.pdf", "application/pdf")
        else:
            st.info("No hay gastos que coincidan con los filtros aplicados")
    
    with tab2:
        st.header("💳 Gestión de Gastos Fijos")
        
        # Sidebar para formulario
        with st.sidebar:
            st.header("➕ Agregar/Editar Gasto Fijo")
            
            with st.form("fijo_form"):
                descripcion = st.text_input("Descripción")
                monto = st.text_input("Monto mensual", "0,00")
                categoria = st.selectbox("Categoría", ["Servicios", "Cargo fijo", "Suscripciones", "Educación", "Salud", "Transporte", "Otros"])
                persona = st.selectbox("Persona", ["Marcelo", "Yenny", "Ambos"])
                cuenta_debito = st.selectbox("Cuenta débito", ["BROU", "Santander", "OCA", "Otra"])
                fecha_inicio = st.date_input("Fecha inicio", datetime.today())
                fecha_fin = st.date_input("Fecha fin (opcional)", value=None)
                activo = st.checkbox("Activo", value=True)
                
                submitted = st.form_submit_button("Guardar Gasto Fijo")
                
                if submitted:
                    try:
                        gasto_fijo = {
                            "Descripcion": descripcion,
                            "Monto": monto_uy_a_float(monto),
                            "Categoria": categoria,
                            "Persona": persona,
                            "CuentaDebito": cuenta_debito,
                            "FechaInicio": fecha_inicio.strftime("%d/%m/%Y"),
                            "FechaFin": fecha_fin.strftime("%d/%m/%Y") if fecha_fin else "",
                            "Activo": activo,
                            "Variaciones": {},
                            "Distribucion": {"Marcelo": 50, "Yenny": 50}
                        }
                        guardar_gasto_fijo(gasto_fijo)
                        st.session_state.df_fijos = cargar_gastos_fijos()
                        st.success("✓ Gasto fijo guardado correctamente")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        # Mostrar tabla
        st.subheader("💳 Lista de Gastos Fijos")
        
        if not st.session_state.df_fijos.empty:
            df_fijos_display = st.session_state.df_fijos.copy()
            df_fijos_display["Monto"] = df_fijos_display["Monto"].apply(lambda x: f"${float_a_monto_uy(x)}")
            df_fijos_display["Estado"] = df_fijos_display["Activo"].apply(lambda x: "✅ Activo" if x else "❌ Inactivo")
            df_fijos_display = df_fijos_display.rename(columns={"CuentaDebito": "Cuenta", "FechaInicio": "Inicio", "FechaFin": "Fin"})
            
            st.dataframe(df_fijos_display[["id", "Descripcion", "Monto", "Categoria", "Persona", "Cuenta", "Inicio", "Fin", "Estado"]], use_container_width=True)
        else:
            st.info("No hay gastos fijos registrados")
    
    with tab3:
        st.header("⏰ Pagos Futuros")
        
        # Marcar pagos del mes actual
        if st.button("✅ Marcar pagos del mes actual", key="marcar_pagos"):
            marcar_pagos_mes_actual()
            st.session_state.df_gastos = cargar_datos()
            st.session_state.df_fijos = cargar_gastos_fijos()
            st.success("✓ Pagos del mes marcados")
            st.rerun()
        
        st.subheader("📅 Resumen Mensual de Pagos Futuros")
        
        # Generar tabla horizontal como en el original
        hoy = datetime.today()
        mes_actual = pd.Timestamp(year=hoy.year, month=hoy.month, day=1)
        meses_a_mostrar = 12  # Mostrar 12 meses
        
        # Obtener meses con pagos
        meses_pagos = {}

        # Procesar gastos normales con cuotas pendientes
        for _, gasto in st.session_state.df_gastos.iterrows():
            cuotas_totales = int(gasto["CuotasTotales"] or 1)
            cuotas_pagadas = int(gasto["CuotasPagadas"] or 0)
            if cuotas_pagadas >= cuotas_totales:
                continue

            fecha_gasto = pd.to_datetime(gasto["Fecha"], dayfirst=True, errors="coerce")
            if pd.isna(fecha_gasto):
                continue

            dia_gasto = fecha_gasto.day
            if dia_gasto >= 5:
                primer_mes_pago = fecha_gasto.replace(day=1) + pd.DateOffset(months=1)
            else:
                primer_mes_pago = fecha_gasto.replace(day=1)

            for i in range(cuotas_pagadas, cuotas_totales):
                mes_pago = primer_mes_pago + pd.DateOffset(months=i)
                if mes_pago < mes_actual:
                    continue
                mes_clave = mes_pago.strftime("%Y-%m")

                if mes_clave not in meses_pagos:
                    meses_pagos[mes_clave] = {
                        "mes_nombre": MESES_NUMERO[mes_pago.month],
                        "año": mes_pago.year,
                        "tarjetas": {"BROU": 0, "Santander": 0, "OCA": 0, "Otra": 0, "Efectivo": 0, "Transferencia": 0},
                        "personas": {"Marcelo": 0, "Yenny": 0},
                        "total": 0
                    }

                # Asignar a tarjeta
                tarjeta = gasto["Tarjeta"]
                if tarjeta in meses_pagos[mes_clave]["tarjetas"]:
                    meses_pagos[mes_clave]["tarjetas"][tarjeta] += gasto["Monto"]

                # Asignar a persona
                persona = gasto["Persona"]
                if persona == "Marcelo":
                    meses_pagos[mes_clave]["personas"]["Marcelo"] += gasto["Monto"]
                elif persona == "Yenny":
                    meses_pagos[mes_clave]["personas"]["Yenny"] += gasto["Monto"]
                # No hay "Ambos" en gastos normales

                meses_pagos[mes_clave]["total"] += gasto["Monto"]

        # Procesar gastos fijos
        for _, fijo in st.session_state.df_fijos.iterrows():
            if not fijo["Activo"]:
                continue
            
            fecha_inicio = pd.to_datetime(fijo["FechaInicio"], dayfirst=True, errors="coerce")
            if pd.isna(fecha_inicio):
                continue
            
            fecha_fin = pd.to_datetime(fijo.get("FechaFin"), dayfirst=True, errors="coerce") if fijo.get("FechaFin") else None
            
            for i in range(meses_a_mostrar):
                mes_fecha = mes_actual + pd.DateOffset(months=i)
                mes_clave = mes_fecha.strftime("%Y-%m")
                
                if fecha_inicio > mes_fecha:
                    continue
                if fecha_fin and fecha_fin < mes_fecha:
                    continue
                
                # Verificar si ya pagado
                meses_pagados = str(fijo.get("MesesPagados", ""))
                if mes_clave in meses_pagados:
                    continue
                
                # Obtener monto
                monto_mes = fijo["Monto"]
                if fijo["Variaciones"] and isinstance(fijo["Variaciones"], dict) and mes_clave in fijo["Variaciones"]:
                    monto_mes = fijo["Variaciones"][mes_clave]
                
                if mes_clave not in meses_pagos:
                    meses_pagos[mes_clave] = {
                        "mes_nombre": MESES_NUMERO[mes_fecha.month],
                        "año": mes_fecha.year,
                        "tarjetas": {"BROU": 0, "Santander": 0, "OCA": 0, "Otra": 0, "Efectivo": 0, "Transferencia": 0},
                        "personas": {"Marcelo": 0, "Yenny": 0},
                        "total": 0
                    }
                
                # Asignar a tarjeta
                tarjeta = fijo["CuentaDebito"]
                if tarjeta in meses_pagos[mes_clave]["tarjetas"]:
                    meses_pagos[mes_clave]["tarjetas"][tarjeta] += monto_mes
                
                # Asignar a persona
                persona = fijo["Persona"]
                if persona == "Ambos":
                    # No distribuir, asignar completo a ambos
                    meses_pagos[mes_clave]["personas"]["Marcelo"] += monto_mes
                    meses_pagos[mes_clave]["personas"]["Yenny"] += monto_mes
                elif persona in meses_pagos[mes_clave]["personas"]:
                    meses_pagos[mes_clave]["personas"][persona] += monto_mes
                
                meses_pagos[mes_clave]["total"] += monto_mes
        
        if meses_pagos:
            # Crear DataFrame para la tabla
            data = []
            for mes_clave in sorted(meses_pagos.keys()):
                mes_info = meses_pagos[mes_clave]
                row = {
                    "Mes/Año": f"{mes_info['mes_nombre'][:3]} '{str(mes_info['año'])[2:]}",
                    "BROU": f"${float_a_monto_uy(mes_info['tarjetas']['BROU'])}",
                    "Santander": f"${float_a_monto_uy(mes_info['tarjetas']['Santander'])}",
                    "OCA": f"${float_a_monto_uy(mes_info['tarjetas']['OCA'])}",
                    "Marcelo": f"${float_a_monto_uy(mes_info['personas']['Marcelo'])}",
                    "Yenny": f"${float_a_monto_uy(mes_info['personas']['Yenny'])}",
                    "Total": f"${float_a_monto_uy(mes_info['total'])}"
                }
                data.append(row)
            
            df_pagos = pd.DataFrame(data)
            st.dataframe(df_pagos, use_container_width=True)
        else:
            st.info("✓ No hay pagos futuros pendientes")
        
        # Gastos con cuotas pendientes (adicional)
        st.subheader("📋 Gastos con Cuotas Pendientes")
        gastos_pendientes = st.session_state.df_gastos[
            st.session_state.df_gastos["CuotasPagadas"] < st.session_state.df_gastos["CuotasTotales"]
        ]
        
        if not gastos_pendientes.empty:
            for _, gasto in gastos_pendientes.iterrows():
                cuotas_restantes = int(gasto["CuotasTotales"]) - int(gasto["CuotasPagadas"])
                st.write(f"• {gasto['Descripcion']} - {cuotas_restantes} cuota(s) pendiente(s) - ${float_a_monto_uy(gasto['Monto'])}")
        else:
            st.info("No hay gastos con cuotas pendientes")

if __name__ == "__main__":
    main()