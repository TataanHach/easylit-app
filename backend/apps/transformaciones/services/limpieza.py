"""
Servicio de limpieza de datos (determinista, sin IA).

Lee el Excel origen y lo normaliza. Detecta el formato automáticamente:
  - TABLA: encabezados arriba, datos en filas.
  - VERTICAL: formulario "etiqueta | dato".

Al leer todas las hojas (multi-hoja), SALTA las hojas de ITEMIZADO (tablas de
partidas: materiales, personal), porque esas no son campos de formulario y las
procesa aparte el generador. Así no ensucian el mapeo ni bajan la confianza.
"""
import re
import unicodedata
from decimal import Decimal, InvalidOperation

import pandas as pd
from openpyxl import load_workbook


def _a_numero(valor):
    """Convierte a número entendiendo formato chileno (1.240,50 → 1240.50)."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip()
    if not s:
        return None
    s = re.sub(r"[^\d.,\-]", "", s)
    if not s:
        return None
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif "." in s:
        partes = s.split(".")
        if len(partes) > 2:
            s = s.replace(".", "")
        elif len(partes[1]) == 3:
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def normalizar_unidad(texto, catalogo):
    if not texto:
        return None
    t = str(texto).strip().lower()
    for unidad in catalogo:
        if t == unidad["simbolo"].lower():
            return unidad["simbolo"]
        if t in [a.lower() for a in unidad.get("alias", [])]:
            return unidad["simbolo"]
    return None


# ─────────────────────────────────────────────────────────────
# DETECCIÓN DE FORMATO Y DE ITEMIZADOS
# ─────────────────────────────────────────────────────────────

def _texto(c):
    return "" if c is None else str(c).strip()


def _norm_tabla(s):
    s = str(s).lower().strip()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", " ", s).strip()


# Palabras que delatan el encabezado de una tabla de itemizado.
_PALABRAS_TABLA = [
    "descripcion", "cantidad", "precio", "valor", "total", "unidad",
    "cargo", "rol", "remuneracion", "item", "detalle", "personas", "monto", "pagar",
]


def es_hoja_itemizado(ws):
    """
    Una hoja es ITEMIZADO si tiene una fila con 3+ columnas de texto y al menos
    2 de ellas son palabras típicas de tabla de partidas (Descripción, Cantidad,
    Precio...). Esas hojas NO se leen como campos: las vuelca el generador.
    """
    for fila in ws.iter_rows(values_only=True):
        celdas = [_texto(c) for c in fila]
        con_texto = [c for c in celdas if c]
        if len(con_texto) >= 3:
            coinc = sum(1 for c in con_texto if any(p in _norm_tabla(c) for p in _PALABRAS_TABLA))
            if coinc >= 2:
                return True
    return False


def _detectar_formato(ws):
    """Decide si una hoja es TABLA o VERTICAL."""
    filas = [f for f in ws.iter_rows(values_only=True) if any(_texto(c) for c in f)]
    if not filas:
        return "vacia"
    ancho = max(sum(1 for c in f if _texto(c)) for f in filas)
    filas_par = sum(1 for f in filas if len([c for c in f if _texto(c)]) == 2)
    if ancho <= 3 and filas_par >= max(3, len(filas) * 0.6):
        return "vertical"
    return "tabla"


def _leer_vertical(ws):
    datos = {}
    for fila in ws.iter_rows(values_only=True):
        celdas = [_texto(c) for c in fila if _texto(c)]
        if len(celdas) >= 2:
            etiqueta = celdas[0].rstrip(":").strip()
            valor = celdas[1]
            if etiqueta and etiqueta not in datos:
                datos[etiqueta] = valor
    return pd.DataFrame([datos]) if datos else pd.DataFrame()


def _leer_una_hoja(ruta_archivo, hoja):
    try:
        wb = load_workbook(ruta_archivo, data_only=True)
        ws = wb[hoja] if (hoja and hoja in wb.sheetnames) else wb.active
        tipo = _detectar_formato(ws)
        if tipo == "vertical":
            df = _leer_vertical(ws)
            wb.close()
            if not df.empty:
                return df, "vertical"
        wb.close()
    except Exception:
        pass
    df = pd.read_excel(ruta_archivo, sheet_name=hoja if hoja else 0, dtype=str)
    return df, "tabla"


def _leer_todas_las_hojas(ruta_archivo):
    """
    Lee todas las hojas de FORMULARIO y combina sus campos. SALTA las hojas de
    itemizado (tablas de partidas), que las procesa el generador aparte.
    """
    # Primero, detectar qué hojas son itemizado (para saltarlas).
    itemizados = set()
    try:
        wb = load_workbook(ruta_archivo, data_only=True)
        for nombre in wb.sheetnames:
            if es_hoja_itemizado(wb[nombre]):
                itemizados.add(nombre)
        nombres = wb.sheetnames
        wb.close()
    except Exception:
        nombres = []

    combinado = {}
    for hoja in nombres:
        if hoja in itemizados:
            continue   # saltar hojas de itemizado
        df, _tipo = _leer_una_hoja(ruta_archivo, hoja)
        if df.empty:
            continue
        fila = df.iloc[0]
        for col in df.columns:
            clave = str(col)
            if clave in combinado:
                clave = f"{hoja} · {col}"
            combinado[clave] = fila[col]

    return pd.DataFrame([combinado]) if combinado else pd.DataFrame()


def limpiar_excel(ruta_archivo, opciones, catalogo_unidades=None, hoja=None,
                  todas_las_hojas=False):
    catalogo_unidades = catalogo_unidades or []
    resumen = {
        "filas_originales": 0,
        "formato_detectado": "tabla",
        "hojas_leidas": 1,
        "duplicados_eliminados": 0,
        "espacios_corregidos": 0,
        "unidades_normalizadas": 0,
        "montos_convertidos": 0,
        "celdas_sin_interpretar": 0,
    }

    if todas_las_hojas:
        df = _leer_todas_las_hojas(ruta_archivo)
        resumen["formato_detectado"] = "multi-hoja"
        try:
            wb = load_workbook(ruta_archivo, read_only=True)
            resumen["hojas_leidas"] = len(wb.sheetnames)
            wb.close()
        except Exception:
            pass
    else:
        df, tipo = _leer_una_hoja(ruta_archivo, hoja=hoja)
        resumen["formato_detectado"] = tipo

    resumen["filas_originales"] = len(df)

    if df.empty:
        return df, resumen

    if opciones.get("espacios", True):
        df.columns = [str(c).strip() for c in df.columns]
        for col in df.select_dtypes(include="object").columns:
            antes = df[col].copy()
            df[col] = df[col].apply(lambda x: str(x).strip() if pd.notna(x) else x)
            resumen["espacios_corregidos"] += int((antes != df[col]).sum())

    if opciones.get("duplicados", True):
        n_antes = len(df)
        df = df.drop_duplicates().reset_index(drop=True)
        resumen["duplicados_eliminados"] = n_antes - len(df)

    if opciones.get("vacias", False):
        df = df.dropna(how="all").reset_index(drop=True)

    return df, resumen


def detectar_columnas_numericas(df):
    columnas = []
    for col in df.columns:
        muestra = df[col].dropna().head(20)
        if len(muestra) == 0:
            continue
        convertibles = sum(1 for v in muestra if _a_numero(v) is not None)
        if convertibles / len(muestra) > 0.7:
            columnas.append(col)
    return columnas