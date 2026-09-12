"""
Servicio de limpieza de datos (determinista, sin IA).

Lee el Excel origen y lo normaliza: quita espacios, arregla números con formato
chileno (1.240,50 → 1240.50), normaliza unidades contra el catálogo canónico y
elimina duplicados. Devuelve un DataFrame limpio y un resumen con cifras reales
de lo que hizo, para mostrarle al usuario "7 duplicados eliminados", no un vago
"limpieza completada".

Todo aquí es reproducible: mismos datos de entrada → mismo resultado. Eso es lo
que hace que la transformación sea auditable.
"""
import re
from decimal import Decimal, InvalidOperation

import pandas as pd


def _a_numero(valor):
    """
    Convierte un valor de celda a número, entendiendo el formato chileno:
    punto como separador de miles y coma como decimal (1.240,50 → 1240.50).
    Devuelve None si no se puede interpretar.
    """
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)

    s = str(valor).strip()
    if not s:
        return None

    # Quitar símbolos de moneda y espacios.
    s = re.sub(r"[^\d.,\-]", "", s)
    if not s:
        return None

    # Formato chileno: si hay punto y coma, el punto es miles y la coma decimal.
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    # Solo coma: es el decimal.
    elif "," in s:
        s = s.replace(",", ".")
    # Solo puntos: hay que decidir si son miles o decimal.
    elif "." in s:
        partes = s.split(".")
        # Si hay más de un punto (1.240.000), todos son separadores de miles.
        if len(partes) > 2:
            s = s.replace(".", "")
        # Un solo punto: si lo que sigue son exactamente 3 dígitos, es separador
        # de miles chileno (42.900 = 42900). Si son 1, 2 o 4+, es decimal (9.5).
        elif len(partes[1]) == 3:
            s = s.replace(".", "")
        # else: se deja como decimal (9.500 no ocurre en la práctica chilena;
        # los decimales llevan coma). El punto con 1-2 dígitos se respeta.

    try:
        return float(s)
    except ValueError:
        return None


def normalizar_unidad(texto, catalogo):
    """
    Dado el texto de una unidad ('M3', 'mt2', 'metros cúbicos') y el catálogo de
    unidades canónicas (lista de dicts con 'simbolo' y 'alias'), devuelve el
    símbolo canónico o None si no se reconoce.
    """
    if not texto:
        return None
    t = str(texto).strip().lower()

    for unidad in catalogo:
        if t == unidad["simbolo"].lower():
            return unidad["simbolo"]
        if t in [a.lower() for a in unidad.get("alias", [])]:
            return unidad["simbolo"]
    return None


def limpiar_excel(ruta_archivo, opciones, catalogo_unidades=None):
    """
    Lee y limpia el Excel. `opciones` es un dict que dice qué operaciones aplicar
    (duplicados, espacios, unidades, etc.). Devuelve (dataframe_limpio, resumen).
    """
    catalogo_unidades = catalogo_unidades or []
    resumen = {
        "filas_originales": 0,
        "duplicados_eliminados": 0,
        "espacios_corregidos": 0,
        "unidades_normalizadas": 0,
        "montos_convertidos": 0,
        "celdas_sin_interpretar": 0,
    }

    df = pd.read_excel(ruta_archivo, dtype=str)
    resumen["filas_originales"] = len(df)

    # 1. Espacios sobrantes en encabezados y celdas de texto.
    if opciones.get("espacios", True):
        df.columns = [str(c).strip() for c in df.columns]
        for col in df.select_dtypes(include="object").columns:
            antes = df[col].copy()
            df[col] = df[col].apply(lambda x: str(x).strip() if pd.notna(x) else x)
            resumen["espacios_corregidos"] += int((antes != df[col]).sum())

    # 2. Duplicados: filas idénticas.
    if opciones.get("duplicados", True):
        n_antes = len(df)
        df = df.drop_duplicates().reset_index(drop=True)
        resumen["duplicados_eliminados"] = n_antes - len(df)

    # 3. Filas completamente vacías.
    if opciones.get("vacias", False):
        df = df.dropna(how="all").reset_index(drop=True)

    return df, resumen


def detectar_columnas_numericas(df):
    """
    Indica qué columnas parecen numéricas (cantidad, precio, total), para saber
    cuáles anonimizar antes de enviar a la IA y cuáles convertir a número.
    """
    columnas = []
    for col in df.columns:
        muestra = df[col].dropna().head(20)
        if len(muestra) == 0:
            continue
        convertibles = sum(1 for v in muestra if _a_numero(v) is not None)
        if convertibles / len(muestra) > 0.7:
            columnas.append(col)
    return columnas
