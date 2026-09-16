"""
Servicio de generación del documento final.

Toma el archivo Excel de la plantilla (con su formato: colores, celdas amarillas,
título) y escribe los datos mapeados DENTRO de él, sin romper el diseño.

Además del valor, aplica el FORMATO NUMÉRICO del campo (pesos, porcentaje, etc.),
convirtiendo el texto a número real cuando corresponde, para que Excel lo trate
como número y lo muestre con su símbolo.
"""
import io
import re
import unicodedata

from openpyxl import load_workbook
from openpyxl.utils import coordinate_to_tuple


# Mapa: formato del campo -> (number_format de Excel, ¿es porcentaje?)
# El number_format es el código que Excel entiende para mostrar el número.
FORMATOS_EXCEL = {
    "ENTERO":     ("#,##0", False),
    "DECIMAL":    ("#,##0.00", False),
    "PESOS":      ('"$"#,##0', False),
    "PESOS_DEC":  ('"$"#,##0.00', False),
    "PORCENTAJE": ("0.0%", True),      # Excel multiplica x100 al mostrar %
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
    """Convierte un valor a número (float) entendiendo formato chileno. None si no puede."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip()
    if not s:
        return None
    s = re.sub(r"[^\d.,\-]", "", s)   # quitar $, %, espacios, letras
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


def _buscar_etiqueta(ws, texto):
    RELLENO = {"de", "del", "la", "el", "los", "las", "y", "o", "a", "nombre"}

    def palabras_clave(s):
        return {p for p in _normalizar(s).split() if p not in RELLENO}

    objetivo_norm = _normalizar(texto)
    objetivo_clave = palabras_clave(texto)
    if not objetivo_norm:
        return None

    candidato_contiene = None
    candidato_palabras = None

    for fila in ws.iter_rows():
        for celda in fila:
            if celda.value is None:
                continue
            valor_norm = _normalizar(celda.value)
            if not valor_norm:
                continue
            if valor_norm == objetivo_norm:
                return celda.row, celda.column + 1
            if candidato_contiene is None and (objetivo_norm in valor_norm or valor_norm in objetivo_norm):
                candidato_contiene = (celda.row, celda.column + 1)
            if candidato_palabras is None:
                valor_clave = palabras_clave(celda.value)
                if objetivo_clave and valor_clave and (
                    objetivo_clave <= valor_clave or valor_clave <= objetivo_clave
                ):
                    candidato_palabras = (celda.row, celda.column + 1)

    return candidato_contiene or candidato_palabras


def _escribir_valor(celda, valor, campo):
    """
    Escribe el valor en la celda, aplicando el formato numérico del campo si lo
    tiene. Si el formato es numérico, convierte el texto a número real para que
    Excel lo trate como número (no como texto) y muestre el símbolo.
    """
    formato = getattr(campo, "formato_numero", "") or "NINGUNO"

    if formato in FORMATOS_EXCEL:
        code, es_pct = FORMATOS_EXCEL[formato]
        num = _a_numero(valor)
        if num is not None:
            # Para porcentaje: si viene "12.5" (o 12,5), Excel con formato 0.0%
            # espera 0.125. Convertimos dividiendo por 100.
            if es_pct:
                num = num / 100.0
            celda.value = num
            celda.number_format = code
            return

    # Sin formato numérico (o valor no numérico): escribir tal cual.
    celda.value = valor


def generar_documento(ruta_plantilla, mapeos_con_valor):
    """
    ruta_plantilla: ruta al .xlsx de la plantilla (formato destino).
    mapeos_con_valor: lista de dicts con 'campo' (CampoPlantilla) y 'valor'.
    Devuelve los bytes del Excel generado.
    """
    wb = load_workbook(ruta_plantilla)

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

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()