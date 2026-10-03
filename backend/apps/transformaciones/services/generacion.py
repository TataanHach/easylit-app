"""
Servicio de generación del documento final.

Maneja DOS tipos de hoja en la plantilla destino:
  1. FORMULARIOS verticales (etiqueta | casilla): escribe cada campo mapeado.
  2. ITEMIZADOS (tablas con encabezados): vuelca las partidas del origen,
     emparejando columnas por nombre y limpiando cada celda según su columna.

Preserva el formato del Excel original (colores, títulos, estilos).
"""
import io
import re
import unicodedata

from openpyxl import load_workbook
from openpyxl.utils import coordinate_to_tuple


FORMATOS_EXCEL = {
    "ENTERO":     ("#,##0", False),
    "DECIMAL":    ("#,##0.00", False),
    "PESOS":      ('"$"#,##0', False),
    "PESOS_DEC":  ('"$"#,##0.00', False),
    "PORCENTAJE": ("0.0%", True),
    "UF":         ('#,##0.00" UF"', False),
}


def _normalizar(texto):
    if texto is None:
        return ""
    s = str(texto).strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = "".join(c if c.isalnum() else " " for c in s)
    return " ".join(s.split())


def _a_numero(valor):
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip()
    if not s:
        return None
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"\.?-\s*$", "", s.strip())
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None
    if "." in s and "," in s:
        if s.rfind(",") < s.rfind("."):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        if re.fullmatch(r"\d{1,3}(,\d{3})+", s):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    elif "." in s:
        partes = s.split(".")
        if all(len(g) == 3 for g in partes[1:]):
            s = s.replace(".", "")
        elif len(partes) > 2:
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────
# LIMPIEZA DETERMINISTA (Capa 1) — gratis, sin IA
# ─────────────────────────────────────────────────────────────

def _parece(nombre_o_etiqueta, palabras):
    txt = _normalizar(nombre_o_etiqueta)
    return any(p in txt for p in palabras)


def _limpiar_rut(v):
    s = str(v).strip().replace(" ", "")
    if re.match(r"^[\d.\-]+[kK\d]$", s):
        return s
    return v


def _limpiar_email(v):
    return str(v).replace(" ", "").strip()


def _limpiar_telefono(v):
    s = str(v)
    s = re.split(r"[/,]", s)[0].strip()
    s = re.sub(r"[^\d+]", "", s)
    return s if s else v


def _limpiar_monto(v):
    s = re.sub(r"\([^)]*\)", "", str(v))
    s = re.sub(r"[^\d.,]", "", s)
    if "," in s and "." in s:
        if s.rfind(",") < s.rfind("."):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        if re.fullmatch(r"\d{1,3}(,\d{3})+", s):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    else:
        s = s.replace(".", "")
    s = s.rstrip(".-")
    try:
        num = float(s)
        return str(int(num)) if num == int(num) else str(num)
    except ValueError:
        return v


def _limpiar_numero(v):
    s = str(v)
    if re.search(r"\d{1,3}(\.\d{3})+", s):
        return _limpiar_monto(s)
    m = re.search(r"\d+([.,]\d+)?", s)
    if m:
        num = m.group().replace(".", "").replace(",", ".")
        try:
            f = float(num)
            return str(int(f)) if f == int(f) else str(f)
        except ValueError:
            return m.group()
    return v


def _limpiar_cantidad(v):
    """Cantidad: extrae el número aunque venga con palabras: 'cien (100)' -> 100."""
    s = str(v)
    m = re.search(r"\(?\s*(\d[\d.,]*)\s*\)?", s)
    if m:
        num = m.group(1).replace(".", "").replace(",", ".")
        try:
            f = float(num)
            return str(int(f)) if f == int(f) else str(f)
        except ValueError:
            return m.group(1)
    return v


def _limpiar_nombre(v):
    s = re.sub(r"\([^)]*\)", "", str(v))
    s = re.sub(r"\bRUT\b.*", "", s, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", s).strip()


def _limpiar_texto(v):
    return re.sub(r"\s+", " ", str(v).strip())


_FORMATOS_MONTO = {"PESOS", "PESOS_DEC", "UF"}
_FORMATOS_NUMERO = {"ENTERO", "DECIMAL", "PORCENTAJE"}


def limpiar_valor(valor, campo):
    if valor is None:
        return valor
    s = str(valor).strip()
    if not s:
        return valor

    formato = getattr(campo, "formato_numero", "") or "NINGUNO"
    ref = f"{getattr(campo, 'nombre', '')} {getattr(campo, 'etiqueta_busqueda', '')}"

    if _parece(ref, ["rut", "rol unico"]):
        return _limpiar_rut(s)
    if _parece(ref, ["email", "correo", "mail"]):
        return _limpiar_email(s)
    if _parece(ref, ["telefono", "fono", "celular", "movil"]):
        return _limpiar_telefono(s)
    if _parece(ref, ["representante", "contacto", "persona"]):
        return _limpiar_nombre(s)

    if formato in _FORMATOS_MONTO:
        return _limpiar_monto(s)
    if formato in _FORMATOS_NUMERO:
        return _limpiar_numero(s)

    return _limpiar_texto(s)


# ─────────────────────────────────────────────────────────────
# ITEMIZADOS (tablas) — leer, emparejar, limpiar y volcar
# ─────────────────────────────────────────────────────────────

# Palabras que delatan el encabezado de una tabla de itemizado.
_PALABRAS_TABLA = [
    "descripcion", "cantidad", "precio", "valor", "total", "unidad",
    "cargo", "rol", "remuneracion", "item", "detalle", "personas", "monto", "pagar",
]


def _texto(c):
    return "" if c is None else str(c).strip()


def _detectar_encabezado_tabla(ws):
    """
    Busca la fila que parece ENCABEZADO de una tabla (3+ columnas con texto, y
    al menos 2 palabras típicas de itemizado). Devuelve (fila, [columnas]) o None.
    """
    for i, fila in enumerate(ws.iter_rows(values_only=True), start=1):
        celdas = [_texto(c) for c in fila]
        con_texto = [c for c in celdas if c]
        if len(con_texto) >= 3:
            coinc = sum(1 for c in con_texto if any(p in _normalizar(c) for p in _PALABRAS_TABLA))
            if coinc >= 2:
                return i, celdas
    return None


def _leer_itemizado_origen(ws):
    """Lee una tabla de partidas del origen. Devuelve dict o None."""
    r = _detectar_encabezado_tabla(ws)
    if not r:
        return None
    fila_enc, encabezados = r
    cols = [(idx, nom) for idx, nom in enumerate(encabezados) if nom]
    partidas = []
    for fila in ws.iter_rows(min_row=fila_enc + 1, values_only=True):
        celdas = [_texto(c) for c in fila]
        if cols and len(celdas) > cols[0][0] and celdas[cols[0][0]]:
            partidas.append({nom: (celdas[idx] if idx < len(celdas) else "") for idx, nom in cols})
    if not partidas:
        return None
    return {"encabezados": [n for _, n in cols], "partidas": partidas}


def _emparejar_columnas(cols_origen, cols_destino):
    """Para cada columna destino, la columna origen que más palabras comparte."""
    mapa = {}
    for col_dest in cols_destino:
        nd = set(_normalizar(col_dest).split())
        mejor, mejor_score = None, 0
        for col_ori in cols_origen:
            no = set(_normalizar(col_ori).split())
            comunes = nd & no
            if comunes and len(comunes) > mejor_score:
                mejor, mejor_score = col_ori, len(comunes)
        mapa[col_dest] = mejor
    return mapa


def _limpiar_celda_tabla(valor, nombre_columna):
    """Limpia una celda de itemizado según qué tipo de columna es (por su nombre)."""
    if not valor or not str(valor).strip():
        return valor
    n = _normalizar(nombre_columna)
    if any(p in n for p in ["valor", "precio", "total", "remuneracion", "monto", "pagar"]):
        return _limpiar_monto(valor)
    if any(p in n for p in ["cantidad", "personas"]):
        return _limpiar_cantidad(valor)
    return _limpiar_texto(valor)


def _volcar_itemizado(ws_destino, datos_origen):
    """
    Escribe las partidas del origen en la tabla del destino, emparejando columnas
    y limpiando cada celda. Devuelve cuántas partidas escribió.
    """
    r = _detectar_encabezado_tabla(ws_destino)
    if not r:
        return 0
    fila_enc, encabezados_dest = r
    cols_dest = [(idx, nom) for idx, nom in enumerate(encabezados_dest) if nom]
    nombres_dest = [n for _, n in cols_dest]

    mapa = _emparejar_columnas(datos_origen["encabezados"], nombres_dest)

    fila_actual = fila_enc + 1
    escritas = 0
    for partida in datos_origen["partidas"]:
        for idx_col, nom_dest in cols_dest:
            col_origen = mapa.get(nom_dest)
            if col_origen and col_origen in partida:
                valor = _limpiar_celda_tabla(partida[col_origen], nom_dest)
                # Si la columna es de dinero/cantidad y quedó numérica, escribir como número.
                num = _a_numero(valor)
                celda = ws_destino.cell(row=fila_actual, column=idx_col + 1)
                nd = _normalizar(nom_dest)
                es_dinero = any(p in nd for p in ["valor", "precio", "total", "remuneracion", "monto", "pagar"])
                if es_dinero and num is not None:
                    celda.value = num
                    celda.number_format = '"$"#,##0'
                elif num is not None and any(p in nd for p in ["cantidad", "personas"]):
                    celda.value = num
                else:
                    celda.value = valor
        fila_actual += 1
        escritas += 1
    return escritas


# ─────────────────────────────────────────────────────────────
# BÚSQUEDA DE CASILLA Y ESCRITURA (formularios verticales)
# ─────────────────────────────────────────────────────────────

def _buscar_etiqueta(ws, texto):
    RELLENO = {"de", "del", "la", "el", "los", "las", "y", "o", "a"}

    def palabras_clave(s):
        return {p for p in _normalizar(s).split() if p not in RELLENO}

    objetivo_norm = _normalizar(texto)
    objetivo_clave = palabras_clave(texto)
    if not objetivo_norm:
        return None

    mejor_puntaje = 0
    mejor_pos = None

    for fila in ws.iter_rows():
        for celda in fila:
            if celda.value is None:
                continue
            valor_norm = _normalizar(celda.value)
            if not valor_norm:
                continue
            if valor_norm == objetivo_norm:
                return celda.row, celda.column + 1
            valor_clave = palabras_clave(celda.value)
            comunes = objetivo_clave & valor_clave
            if comunes:
                puntaje = len(comunes)
                if objetivo_clave and objetivo_clave <= valor_clave:
                    puntaje += 10
                if puntaje > mejor_puntaje:
                    mejor_puntaje = puntaje
                    mejor_pos = (celda.row, celda.column + 1)

    return mejor_pos


def _escribir_valor(celda, valor, campo):
    valor = limpiar_valor(valor, campo)
    formato = getattr(campo, "formato_numero", "") or "NINGUNO"
    if formato in FORMATOS_EXCEL:
        code, es_pct = FORMATOS_EXCEL[formato]
        num = _a_numero(valor)
        if num is not None:
            if es_pct:
                num = num / 100.0
            celda.value = num
            celda.number_format = code
            return
    celda.value = valor


def generar_documento(ruta_plantilla, mapeos_con_valor, ruta_origen=None):
    """
    ruta_plantilla: .xlsx de la plantilla destino.
    mapeos_con_valor: lista de {campo, valor} para los campos de FORMULARIO.
    ruta_origen: (opcional) .xlsx del origen, para volcar los ITEMIZADOS.
                 Si se pasa, busca tablas en el origen y las vuelca a las hojas
                 del destino que tengan tabla.
    """
    wb = load_workbook(ruta_plantilla)

    # 1. Escribir los campos de formulario (como siempre).
    for item in mapeos_con_valor:
        campo = item["campo"]
        valor = item["valor"]
        if valor is None:
            continue
        if campo.hoja_destino and campo.hoja_destino in wb.sheetnames:
            ws = wb[campo.hoja_destino]
        else:
            ws = wb.active
        destino = None
        if campo.celda_destino:
            destino = coordinate_to_tuple(campo.celda_destino)
        if destino is None and campo.etiqueta_busqueda:
            destino = _buscar_etiqueta(ws, campo.etiqueta_busqueda)
        if destino is None:
            destino = _buscar_etiqueta(ws, campo.nombre.replace("_", " "))
        if destino is None:
            continue
        fila, col = destino
        celda = ws.cell(row=fila, column=col)
        _escribir_valor(celda, valor, campo)

    # 2. Volcar los ITEMIZADOS: para cada hoja del destino que tenga tabla,
    #    buscar en el origen una tabla (preferir la hoja del mismo nombre).
    if ruta_origen:
        try:
            wb_origen = load_workbook(ruta_origen, data_only=True)
            for nombre_hoja in wb.sheetnames:
                ws_dest = wb[nombre_hoja]
                # ¿La hoja destino tiene una tabla de itemizado?
                if _detectar_encabezado_tabla(ws_dest) is None:
                    continue
                # Buscar la tabla en el origen: primero en la hoja del mismo nombre.
                datos = None
                if nombre_hoja in wb_origen.sheetnames:
                    datos = _leer_itemizado_origen(wb_origen[nombre_hoja])
                # Si no, buscar en cualquier hoja del origen que tenga tabla.
                if datos is None:
                    for hoja_ori in wb_origen.sheetnames:
                        d = _leer_itemizado_origen(wb_origen[hoja_ori])
                        if d:
                            datos = d
                            break
                if datos:
                    _volcar_itemizado(ws_dest, datos)
            wb_origen.close()
        except Exception:
            # Si falla el volcado de itemizados, no rompe la generación de campos.
            pass

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()