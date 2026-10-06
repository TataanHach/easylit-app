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
from datetime import date, datetime

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
        # Se guarda el valor ORIGINAL (fecha, número o texto), no su texto:
        # convertir todo a str perdía las fechas y los números.
        if cols and len(fila) > cols[0][0] and _texto(fila[cols[0][0]]):
            partidas.append({nom: (fila[idx] if idx < len(fila) else None) for idx, nom in cols})
    if not partidas:
        return None
    return {"hoja": ws.title, "encabezados": [n for _, n in cols], "partidas": partidas}


def clave_ia_tabla(hoja, columna):
    """Clave con que se guardan los valores limpiados por IA de una columna de tabla."""
    return f"{hoja}::{columna}"


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


# Tipos de columna, reconocidos por palabras de su encabezado.
_COL_DINERO = ["valor", "precio", "total", "remuneracion", "monto", "pagar", "venta",
               "costo", "neto", "iva", "subtotal", "importe", "sueldo", "pago"]
_COL_CANTIDAD = ["cantidad", "cant", "personas", "unidades"]
_COL_FECHA = ["fecha", "inicio", "termino", "vencimiento", "emision"]

# Errores de fórmula de Excel: no son datos, la celda queda vacía.
_ERRORES_EXCEL = {"#VALUE!", "#DIV/0!", "#N/A", "#REF!", "#NAME?", "#NUM!", "#NULL!", "#SPILL!", "#CALC!"}

_FORMATOS_FECHA_TEXTO = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y",
                         "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M")


def _tipo_columna(nombre_columna):
    n = _normalizar(nombre_columna)
    palabras = n.split()
    if any(p in n for p in _COL_FECHA):
        return "fecha"
    if palabras and palabras[0] in _COL_CANTIDAD:   # "cantidad total" es cantidad
        return "cantidad"
    if any(p in n for p in _COL_DINERO):
        return "dinero"
    if any(p in palabras or n.startswith(p) for p in _COL_CANTIDAD):
        return "cantidad"
    return "texto"


def _entero_si_exacto(num):
    return int(num) if float(num).is_integer() else num


def _fecha_desde_texto(s):
    for fmt in _FORMATOS_FECHA_TEXTO:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _limpiar_celda_tabla(valor, nombre_columna):
    """
    Limpia una celda de itemizado y devuelve el valor con su tipo real
    (date, int/float o str), o None si queda vacía.
      - Errores de Excel (#VALUE!, #DIV/0!…) → vacía.
      - Fechas → date (sin la hora 00:00:00).
      - Columnas de dinero/cantidad → número, aunque venga con símbolos ("1.500+", "$ 2.000").
      - Texto que es un número limpio ("100") → número.
      - Resto → texto sin espacios de más.
    """
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date() if (valor.hour, valor.minute, valor.second) == (0, 0, 0) else valor
    if isinstance(valor, date):
        return valor
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return _entero_si_exacto(valor)

    s = re.sub(r"\s+", " ", str(valor)).strip()
    if not s or s.upper() in _ERRORES_EXCEL:
        return None

    tipo = _tipo_columna(nombre_columna)
    if tipo == "fecha":
        f = _fecha_desde_texto(s)
        if f:
            return f
    if tipo in ("dinero", "cantidad"):
        # En cantidades se toma el número aunque venga con palabras: "cien (100)" → 100.
        num = _a_numero(_limpiar_cantidad(s) if tipo == "cantidad" else s)
        if num is not None:
            return _entero_si_exacto(num)
        return s
    # Número escrito como texto ("100", "2,5"); sin ceros a la izquierda para no
    # romper códigos como "007".
    if re.fullmatch(r"-?(0|[1-9]\d*)([.,]\d+)?", s):
        return _entero_si_exacto(float(s.replace(",", ".")))
    return s


def texto_celda_tabla(valor, nombre_columna):
    """Cómo se ve una celda limpia en la vista previa (formato chileno)."""
    v = _limpiar_celda_tabla(valor, nombre_columna)
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%d-%m-%Y %H:%M")
    if isinstance(v, date):
        return v.strftime("%d-%m-%Y")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        miles = f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"
        miles = miles.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"${miles}" if _tipo_columna(nombre_columna) == "dinero" else miles
    return str(v)


def _es_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def columnas_calculo_total(cols_dest):
    """
    Columnas para calcular total = precio × cantidad, si la tabla las tiene:
    (total, cantidad, precio) o None.
    """
    total = next((c for c in cols_dest
                  if "total" in _normalizar(c).split() and _tipo_columna(c) == "dinero"), None)
    cantidad = next((c for c in cols_dest if _tipo_columna(c) == "cantidad"), None)
    precio = next((c for c in cols_dest
                   if c != total and _tipo_columna(c) == "dinero"
                   and any(p in _normalizar(c) for p in ["precio", "unitario", "valor", "venta"])), None)
    return (total, cantidad, precio) if total and cantidad and precio else None


def filas_itemizado(datos_origen, cols_dest, calcular_totales=False, valores_ia=None):
    """
    Filas limpias de una tabla, listas para la vista previa o el documento.
    Devuelve (filas, faltantes): cada fila es (valores {columna: valor},
    columnas_calculadas, columnas_limpiadas_por_ia). `faltantes` = filas sin
    total pero con precio y cantidad; si `calcular_totales`, a esas se les pone
    precio × cantidad. `valores_ia` = {clave_ia_tabla: {original: limpio}}.
    """
    mapa = _emparejar_columnas(datos_origen["encabezados"], cols_dest)
    calc = columnas_calculo_total(cols_dest)
    valores_ia = valores_ia or {}
    hoja = datos_origen.get("hoja", "")
    filas, faltantes = [], 0
    for partida in datos_origen["partidas"]:
        valores, por_ia = {}, set()
        for col in cols_dest:
            ori = mapa.get(col)
            if not ori:
                valores[col] = None
                continue
            crudo = partida.get(ori)
            limpios = valores_ia.get(clave_ia_tabla(hoja, ori), {})
            if isinstance(crudo, str) and crudo.strip() in limpios:
                nuevo = limpios[crudo.strip()]
                if nuevo != crudo.strip():
                    por_ia.add(col)
                crudo = nuevo
            valores[col] = _limpiar_celda_tabla(crudo, col)
        calculadas = set()
        if calc:
            tot, cant, pre = calc
            if valores.get(tot) is None and _es_num(valores.get(cant)) and _es_num(valores.get(pre)):
                faltantes += 1
                if calcular_totales:
                    valores[tot] = _entero_si_exacto(round(valores[cant] * valores[pre], 2))
                    calculadas.add(tot)
        filas.append((valores, calculadas, por_ia))
    return filas, faltantes


def textos_para_ia(datos_origen, maximo=300):
    """
    Valores de texto de una tabla que vale la pena mandar a la IA: solo columnas
    de texto y fecha (nunca dinero ni cantidad), sin repetidos y solo los que la
    limpieza normal deja como texto. Devuelve [(clave, columna, tipo, valor)].
    """
    hoja = datos_origen.get("hoja", "")
    vistos, salida = set(), []
    for col in datos_origen["encabezados"]:
        tipo = _tipo_columna(col)
        if tipo in ("dinero", "cantidad"):
            continue   # privacidad: montos y cantidades no salen de la empresa
        for partida in datos_origen["partidas"]:
            crudo = partida.get(col)
            if not isinstance(crudo, str) or not crudo.strip():
                continue
            if not isinstance(_limpiar_celda_tabla(crudo, col), str):
                continue   # ya quedó como número o fecha: no hace falta la IA
            clave = clave_ia_tabla(hoja, col)
            if (clave, crudo.strip()) in vistos:
                continue
            vistos.add((clave, crudo.strip()))
            salida.append((clave, col, "FECHA" if tipo == "fecha" else "TEXTO", crudo.strip()))
            if len(salida) >= maximo:
                return salida
    return salida


def _volcar_itemizado(ws_destino, datos_origen, calcular_totales=False, valores_ia=None):
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

    filas, _ = filas_itemizado(datos_origen, nombres_dest, calcular_totales, valores_ia)

    fila_actual = fila_enc + 1
    escritas = 0
    for valores, _calculadas, _por_ia in filas:
        for idx_col, nom_dest in cols_dest:
            valor = valores.get(nom_dest)
            if valor is not None:
                celda = ws_destino.cell(row=fila_actual, column=idx_col + 1)
                celda.value = valor
                es_numero = isinstance(valor, (int, float)) and not isinstance(valor, bool)
                if isinstance(valor, datetime):
                    celda.number_format = "DD-MM-YYYY HH:MM"
                elif isinstance(valor, date):
                    celda.number_format = "DD-MM-YYYY"
                elif es_numero and _tipo_columna(nom_dest) == "dinero":
                    celda.number_format = '"$"#,##0' if float(valor).is_integer() else '"$"#,##0.00'
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


def buscar_tabla_origen(wb_origen, nombre_hoja):
    """Tabla del origen para una hoja de tabla de la plantilla: primero la hoja
    del mismo nombre; si no, la primera hoja del origen que tenga tabla."""
    if nombre_hoja in wb_origen.sheetnames:
        datos = _leer_itemizado_origen(wb_origen[nombre_hoja])
        if datos:
            return datos
    for hoja_ori in wb_origen.sheetnames:
        datos = _leer_itemizado_origen(wb_origen[hoja_ori])
        if datos:
            return datos
    return None


def emparejamiento_tablas(ruta_plantilla, ruta_origen):
    """
    Qué tan bien se emparejan las columnas de cada tabla de la plantilla con las
    del origen. Por hoja: {columnas, emparejadas, sin_pareja, puntajes}, donde
    cada puntaje es 100 (mismo nombre), 70 (nombre parecido) o 0 (sin pareja).
    """
    resultado = {}
    try:
        wb_dest = load_workbook(ruta_plantilla)
        wb_ori = load_workbook(ruta_origen, data_only=True)
    except Exception:
        return resultado
    for nombre in wb_dest.sheetnames:
        enc = _detectar_encabezado_tabla(wb_dest[nombre])
        if not enc:
            continue
        datos = buscar_tabla_origen(wb_ori, nombre)
        if not datos:
            continue
        cols = [c for c in enc[1] if c]
        mapa = _emparejar_columnas(datos["encabezados"], cols)
        puntajes = [
            100 if mapa[c] and _normalizar(mapa[c]) == _normalizar(c) else (70 if mapa[c] else 0)
            for c in cols
        ]
        resultado[nombre] = {
            "columnas": len(cols),
            "emparejadas": sum(1 for c in cols if mapa[c]),
            "sin_pareja": [c for c in cols if not mapa[c]],
            "puntajes": puntajes,
        }
    wb_dest.close()
    wb_ori.close()
    return resultado


def generar_documento(ruta_plantilla, mapeos_con_valor, ruta_origen=None, calcular_totales=False,
                      valores_ia_tablas=None):
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
                datos = buscar_tabla_origen(wb_origen, nombre_hoja)
                if datos:
                    _volcar_itemizado(ws_dest, datos, calcular_totales, valores_ia_tablas)
            wb_origen.close()
        except Exception:
            # Si falla el volcado de itemizados, no rompe la generación de campos.
            pass

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()