"""
Servicio de generación del documento final.

Toma el archivo Excel de la plantilla (con su formato: colores, celdas amarillas,
título) y escribe los datos mapeados DENTRO de él, sin romper el diseño.

Al escribir cada valor, aplica en orden:
  1. LIMPIEZA determinista (Capa 1, gratis, sin IA): según el tipo del campo,
     quita espacios, saca el $ de un monto, arregla el guion de un RUT, etc.
  2. FORMATO numérico del campo (pesos, porcentaje, UF...).
Convierte el texto a número real cuando corresponde.
"""
import io
import re
import unicodedata

from openpyxl import load_workbook
from openpyxl.utils import coordinate_to_tuple


# Mapa: formato del campo -> (number_format de Excel, ¿es porcentaje?)
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
    """Convierte a número entendiendo formato chileno y montos sucios."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip()
    if not s:
        return None
    # Quitar texto entre paréntesis, ej "(ciento cincuenta millones)".
    s = re.sub(r"\([^)]*\)", "", s)
    # Quitar el ".-" o "-" al final (forma chilena de "pesos justos").
    s = re.sub(r"\.?-\s*$", "", s.strip())
    # Dejar solo dígitos, punto y coma.
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
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
    """¿El nombre/etiqueta del campo contiene alguna de estas palabras clave?"""
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
    s = re.split(r"[/,]", s)[0].strip()   # si hay varios, toma el primero
    s = re.sub(r"[^\d+]", "", s)
    return s if s else v


def _limpiar_monto(v):
    """Monto: quita $, paréntesis, .-, y arma el número completo con miles."""
    s = re.sub(r"\([^)]*\)", "", str(v))
    s = re.sub(r"[^\d.,]", "", s).replace(".", "").replace(",", ".").rstrip(".-")
    try:
        num = float(s)
        return str(int(num)) if num == int(num) else str(num)
    except ValueError:
        return v


def _limpiar_numero(v):
    """
    Número 'simple' (plazo, años, %). Decide inteligentemente:
      - Si tiene separadores de miles (1.234.567), lo trata como monto completo.
      - Si es un número suelto dentro de texto ('sesenta ( 60 ) Días'), lo extrae.
    """
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


def _limpiar_texto(v):
    return re.sub(r"\s+", " ", str(v).strip())


# Formatos que representan MONTOS (limpian el número completo con miles).
_FORMATOS_MONTO = {"PESOS", "PESOS_DEC", "UF"}
# Formatos de número simple.
_FORMATOS_NUMERO = {"ENTERO", "DECIMAL", "PORCENTAJE"}


def limpiar_valor(valor, campo):
    """
    Limpieza determinista (Capa 1, gratis, sin IA). Decide qué hacer según el
    FORMATO del campo (no el tipo) y pistas de su nombre. Lo que no puede
    resolver con seguridad, lo deja tal cual.
    """
    if valor is None:
        return valor
    s = str(valor).strip()
    if not s:
        return valor

    formato = getattr(campo, "formato_numero", "") or "NINGUNO"
    ref = f"{getattr(campo, 'nombre', '')} {getattr(campo, 'etiqueta_busqueda', '')}"

    # Por nombre/etiqueta (más específico): RUT, email, teléfono.
    if _parece(ref, ["rut", "rol unico"]):
        return _limpiar_rut(s)
    if _parece(ref, ["email", "correo", "mail"]):
        return _limpiar_email(s)
    if _parece(ref, ["telefono", "fono", "celular", "movil"]):
        return _limpiar_telefono(s)

    # Por FORMATO del campo (no por tipo).
    if formato in _FORMATOS_MONTO:
        return _limpiar_monto(s)
    if formato in _FORMATOS_NUMERO:
        return _limpiar_numero(s)

    # Sin formato numérico: texto (colapsar espacios).
    return _limpiar_texto(s)


# ─────────────────────────────────────────────────────────────
# BÚSQUEDA DE LA CASILLA Y ESCRITURA
# ─────────────────────────────────────────────────────────────

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
    Escribe el valor: primero LIMPIA (Capa 1), luego aplica formato numérico.
    """
    # 1. Limpieza determinista según el tipo del campo.
    valor = limpiar_valor(valor, campo)

    # 2. Formato numérico.
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