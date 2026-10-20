"""
Normalización determinista de los datos del origen, con pandas (sin IA).

`limpiar_dataframe(df)` limpia columnas COMPLETAS con operaciones de pandas
(`.str.replace`, `pd.to_datetime`, `.map`): fechas en español, RUT con dígito
verificador, correos, plazos y números escritos en palabras, nombres de
personas en mayúsculas y las tildes que se pueden poner sin adivinar.

Se aplica al leer el origen, así que la vista previa, la IA y el documento
reciben los datos ya limpios: la IA queda solo para lo que una regla no puede
resolver (tildes de apellidos, palabras partidas, textos ambiguos).

Ventajas frente a la IA: mismo resultado siempre, instantáneo, sin cuota y sin
que el dato salga de la empresa. Ante la duda, una regla NO toca el dato: es
preferible dejarlo como vino que corregirlo mal.
"""
import re
import unicodedata
from datetime import date, datetime

import pandas as pd


def _sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _clave(texto):
    """Texto comparable: minúsculas, sin tildes ni signos. "Fecha_Apertura:" → "fecha apertura"."""
    s = _sin_tildes(str(texto)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


# ─────────────────────────────────────────────────────────────
# FECHAS
# ─────────────────────────────────────────────────────────────

MESES = {
    "enero": 1, "ene": 1, "febrero": 2, "feb": 2, "marzo": 3, "mar": 3,
    "abril": 4, "abr": 4, "mayo": 5, "may": 5, "junio": 6, "jun": 6,
    "julio": 7, "jul": 7, "agosto": 8, "ago": 8,
    "septiembre": 9, "setiembre": 9, "sept": 9, "sep": 9, "set": 9,
    "octubre": 10, "oct": 10, "noviembre": 11, "nov": 11, "diciembre": 12, "dic": 12,
}
_MES = "|".join(sorted(MESES, key=len, reverse=True))

# Ruido que acompaña a una fecha y no cambia su valor: día de la semana, hora,
# "aprox.", paréntesis.
_RUIDO_FECHA = (
    r"\(.*?\)|\baprox(?:imadamente|\.)?|\ba las\b|\bhrs?\b\.?|\bhoras?\b|"
    r"\d{1,2}:\d{2}(?::\d{2})?|\b(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b"
)
# Fecha completa con el mes en palabras: "15 de agosto de 2024", "15-ago-24".
_DIA_MES_ANIO = rf"^(\d{{1,2}})\s*(?:de\s+|[-/.\s])\s*({_MES})\.?\s*(?:del?\s+|[-/.,\s])\s*(\d{{2,4}})$"
# Fecha completa con números, día primero: "15/08/2024", "15-08-24", "15.08.2024".
_NUMERICA = r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2}|\d{4})$"
_ISO = r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$"
# Solo mes y año: "agosto 2024", "agosto de 2024", "ago-2024", "08/2024".
_MES_ANIO = rf"^({_MES})\.?\s*(?:del?\s+|[-/\s])\s*(\d{{4}})$"
_MES_ANIO_NUM = r"^(0?[1-9]|1[0-2])[/-](\d{4})$"


def _preparar_fechas(serie):
    """Texto de fecha sin tildes, ruido ni espacios de más (vectorizado)."""
    s = serie.astype(str).map(_sin_tildes).str.lower()
    s = s.str.replace(_RUIDO_FECHA, " ", regex=True)
    return s.str.replace(r"\s+", " ", regex=True).str.strip(" ,.-")


def _anios(serie):
    a = pd.to_numeric(serie, errors="coerce")
    return a.where(a >= 100, a + 2000)


def fechas(serie):
    """
    Serie de textos → Serie de fechas en texto chileno ("15-08-2024"; "08-2024"
    si solo hay mes y año, sin inventar el día). NaN donde no hay una fecha.
    Las celdas que ya son fecha de Excel (datetime) también se convierten.
    """
    resultado = pd.Series(pd.NA, index=serie.index, dtype="object")
    es_fecha = serie.map(lambda v: isinstance(v, (datetime, date)))
    resultado[es_fecha] = serie[es_fecha].map(lambda v: v.strftime("%d-%m-%Y"))

    s = _preparar_fechas(serie[~es_fecha])

    def armar(dia, mes, anio, quedan):
        f = pd.to_datetime(
            pd.DataFrame({"year": anio, "month": mes, "day": dia}), errors="coerce")
        resultado.loc[quedan.index] = resultado.loc[quedan.index].where(
            f.isna(), f.dt.strftime("%d-%m-%Y"))

    for patron, orden in ((_NUMERICA, "dma"), (_ISO, "amd")):
        partes = s.str.extract(patron).dropna()
        if len(partes):
            d, m, a = (partes[orden.index(x)] for x in "dma")
            armar(pd.to_numeric(d), pd.to_numeric(m), _anios(a), partes)

    partes = s.str.extract(_DIA_MES_ANIO).dropna()
    if len(partes):
        armar(pd.to_numeric(partes[0]), partes[1].map(MESES), _anios(partes[2]), partes)

    pendientes = resultado.loc[s.index].isna()
    for patron, mes in ((_MES_ANIO, lambda p: p.map(MESES)), (_MES_ANIO_NUM, pd.to_numeric)):
        partes = s[pendientes].str.extract(patron).dropna()
        if len(partes):
            resultado.loc[partes.index] = (
                mes(partes[0]).map(lambda m: f"{int(m):02d}") + "-" + partes[1])
            pendientes = resultado.loc[s.index].isna()
    return resultado


def fecha(valor):
    """Una sola fecha: date si es completa, "08-2024" si es mes y año, None si no es fecha."""
    texto = fechas(pd.Series([valor], dtype="object")).iloc[0]
    if pd.isna(texto):
        return None
    if len(texto) == 10:
        return datetime.strptime(texto, "%d-%m-%Y").date()
    return texto


# ─────────────────────────────────────────────────────────────
# RUT
# ─────────────────────────────────────────────────────────────

def telefono(valor):
    """
    Teléfono chileno en un solo formato: «+56 9 1234 5678» (celular),
    «+56 2 1234 5678» (Santiago) o «+56 41 212 3456» (regiones). Acepta números
    de Excel (56998019366), con o sin +56 y con cualquier espaciado. Devuelve
    None si no es un teléfono chileno reconocible (se deja como venía).
    """
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    digitos = re.sub(r"\D", "", str(valor))
    if len(digitos) == 11 and digitos.startswith("56"):
        digitos = digitos[2:]
    if len(digitos) != 9:
        return None   # 8 dígitos ("9 9999999") es ambiguo: no se adivina
    if digitos[0] in "92":
        return f"+56 {digitos[0]} {digitos[1:5]} {digitos[5:]}"
    if digitos[:2] in _CODIGOS_AREA:
        return f"+56 {digitos[:2]} {digitos[2:5]} {digitos[5:]}"
    return None   # "6 9915 1736": no es un código de área real; no se inventa


# Códigos de área de teléfonos fijos de regiones (Santiago es el 2).
_CODIGOS_AREA = {"32", "33", "34", "35", "41", "42", "43", "45", "51", "52", "53", "55",
                 "57", "58", "61", "63", "64", "65", "67", "71", "72", "73", "75"}


def rut(valor):
    """
    RUT válido → "12.345.678-5". None si no tiene forma de RUT o si el dígito
    verificador no corresponde (un RUT mal escrito no se "arregla").
    """
    s = re.sub(r"[\s.\-‐–]", "", str(valor)).upper()
    s = re.sub(r"^RUT:?", "", s)
    m = re.fullmatch(r"(\d{6,8})([\dK])", s)
    if not m:
        return None
    cuerpo, dv = m.groups()
    suma, mult = 0, 2
    for d in reversed(cuerpo):
        suma += int(d) * mult
        mult = 2 if mult == 7 else mult + 1
    resto = 11 - suma % 11
    esperado = {11: "0", 10: "K"}.get(resto, str(resto))
    if dv != esperado:
        return None
    return f"{int(cuerpo):,}".replace(",", ".") + f"-{dv}"


# ─────────────────────────────────────────────────────────────
# NÚMEROS EN PALABRAS Y PLAZOS
# ─────────────────────────────────────────────────────────────

_NUMEROS = {
    "cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
    "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17,
    "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiun": 21, "veintiuno": 21,
    "veintiuna": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24,
    "veinticinco": 25, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28,
    "veintinueve": 29, "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60,
    "setenta": 70, "ochenta": 80, "noventa": 90, "cien": 100, "ciento": 100,
    "doscientos": 200, "doscientas": 200, "trescientos": 300, "trescientas": 300,
    "cuatrocientos": 400, "cuatrocientas": 400, "quinientos": 500, "quinientas": 500,
    "seiscientos": 600, "seiscientas": 600, "setecientos": 700, "setecientas": 700,
    "ochocientos": 800, "ochocientas": 800, "novecientos": 900, "novecientas": 900,
}
# Palabras que acompañan a un plazo o cantidad y no cambian el número.
_ACOMPANANTES = {
    "y", "dia", "dias", "mes", "meses", "ano", "anos", "semana", "semanas", "hora",
    "horas", "corrido", "corridos", "habil", "habiles", "calendario", "calendarios",
    "unidad", "unidades", "persona", "personas",
}
_UNIDAD_PLAZO = r"(?:dias?|meses|mes|anos?|semanas?|horas?)"


def numero_en_palabras(valor):
    """
    "sesenta días corridos" → 60, "ciento veinte" → 120, "dos mil quinientos" → 2500.
    None si hay cualquier palabra que no sea parte de un número (o de su unidad).
    """
    palabras = re.sub(r"[^a-z\s]", " ", _sin_tildes(str(valor)).lower()).split()
    if not palabras:
        return None
    total, actual, hubo_numero = 0, 0, False
    for p in palabras:
        if p in _NUMEROS:
            actual += _NUMEROS[p]
            hubo_numero = True
        elif p == "mil":
            total, actual, hubo_numero = total + (actual or 1) * 1000, 0, True
        elif p in ("millon", "millones"):
            total, actual, hubo_numero = total + (actual or 1) * 1_000_000, 0, True
        elif p not in _ACOMPANANTES:
            return None
    return total + actual if hubo_numero else None


def plazos(serie):
    """
    Plazos y cantidades en texto → solo el número (como texto). NaN si no se
    reconoce. "sesenta ( 60 ) Días" → "60", "120 dias corridos" → "120",
    "noventa días" → "90".
    """
    s = serie.astype(str).map(_sin_tildes).str.lower().str.strip()
    # 1. El número entre paréntesis manda: "sesenta (60) días".
    resultado = s.str.extract(r"\(\s*(\d+)\s*\)", expand=False)
    # 2. Número seguido de su unidad: "120 dias corridos".
    con_unidad = s.str.extract(rf"^(\d+)\s*{_UNIDAD_PLAZO}\b", expand=False)
    resultado = resultado.where(resultado.notna(), con_unidad)
    # 3. Número escrito en palabras: "noventa días".
    # En un solo paso y como object: si no, pandas pasa los números a decimal
    # ("90.0") y los que no son número a "nan".
    en_palabras = s.map(lambda v: _texto_o_none(numero_en_palabras(v))).astype(object)
    return resultado.where(resultado.notna(), en_palabras)


def _texto_o_none(numero):
    return None if numero is None else str(numero)


# ─────────────────────────────────────────────────────────────
# NOMBRES DE PERSONAS
# ─────────────────────────────────────────────────────────────

_PARTICULAS = {"de", "del", "la", "las", "los", "y", "e", "van", "von", "da", "di"}


def nombre_persona(valor):
    """
    "JUAN PEREZ DE LA FUENTE" → "Juan Perez de la Fuente". Solo cambia nombres
    escritos enteros en mayúsculas o en minúsculas; si ya vienen mezclados se
    respetan (puede ser intencional, ej. "McDonald").
    """
    s = re.sub(r"\s+", " ", str(valor)).strip()
    letras = [c for c in s if c.isalpha()]
    if not letras or not (all(c.isupper() for c in letras) or all(c.islower() for c in letras)):
        return s
    partes = []
    for i, p in enumerate(s.lower().split(" ")):
        if i > 0 and p in _PARTICULAS:
            partes.append(p)
        else:
            # "o'higgins" → "O'Higgins", "maria-jose" → "Maria-Jose"
            partes.append(re.sub(r"(^|['\-])(\w)", lambda m: m.group(1) + m.group(2).upper(), p))
    return " ".join(partes)


# ─────────────────────────────────────────────────────────────
# TILDES
# ─────────────────────────────────────────────────────────────

# Palabras que en español SIEMPRE llevan tilde (sin ella no existen o son otra
# palabra que no aparece en una licitación). Se dejan fuera las ambiguas:
# "mas/más", "esta/está", "tome/Tomé", "publico/público", "ano/año"…
_CON_TILDE = {
    # Licitaciones y obras
    "region": "región", "telefono": "teléfono", "numero": "número", "codigo": "código",
    "area": "área", "pagina": "página", "catalogo": "catálogo", "analisis": "análisis",
    "tecnico": "técnico", "tecnica": "técnica", "tecnicos": "técnicos", "tecnicas": "técnicas",
    "economico": "económico", "economica": "económica", "basico": "básico", "basica": "básica",
    "electrico": "eléctrico", "electrica": "eléctrica", "electricos": "eléctricos",
    "electricas": "eléctricas", "mecanico": "mecánico", "mecanica": "mecánica",
    "hidraulico": "hidráulico", "hidraulica": "hidráulica", "metrico": "métrico",
    "metricos": "métricos", "cubico": "cúbico", "cubicos": "cúbicos", "credito": "crédito",
    "deposito": "depósito", "garantia": "garantía", "garantias": "garantías",
    "dia": "día", "dias": "días", "minimo": "mínimo", "minima": "mínima", "maximo": "máximo",
    "maxima": "máxima", "ultimo": "último", "ultima": "última", "unico": "único",
    "unica": "única", "util": "útil", "utiles": "útiles", "energia": "energía",
    "ingenieria": "ingeniería", "topografia": "topografía", "geologia": "geología",
    "tecnologia": "tecnología", "compania": "compañía", "via": "vía", "vias": "vías",
    "rio": "río", "telefonico": "telefónico", "electronico": "electrónico",
    "electronica": "electrónica", "academico": "académico", "juridico": "jurídico",
    "juridica": "jurídica", "metodo": "método", "transito": "tránsito",
    "albanileria": "albañilería", "carpinteria": "carpintería", "ceramica": "cerámica",
    "ceramico": "cerámico", "tuberia": "tubería", "tuberias": "tuberías",
    "caneria": "cañería", "canerias": "cañerías", "hormigon": "hormigón", "camion": "camión",
    "kilometro": "kilómetro", "kilometros": "kilómetros", "senaletica": "señalética",
    "diseno": "diseño", "articulo": "artículo", "parrafo": "párrafo",
    # Comunas y regiones de Chile (sin ambigüedad)
    "maipu": "Maipú", "nunoa": "Ñuñoa", "penalolen": "Peñalolén", "valparaiso": "Valparaíso",
    "chillan": "Chillán", "curico": "Curicó", "copiapo": "Copiapó", "quilpue": "Quilpué",
    "pucon": "Pucón", "penaflor": "Peñaflor", "conchali": "Conchalí", "aysen": "Aysén",
    "biobio": "Biobío", "nuble": "Ñuble", "araucania": "Araucanía", "tarapaca": "Tarapacá",
    "antartica": "Antártica", "vilcun": "Vilcún", "pitrufquen": "Pitrufquén",
    "curacavi": "Curacaví", "licanten": "Licantén", "puren": "Purén", "hualpen": "Hualpén",
    "mulchen": "Mulchén", "tirua": "Tirúa", "canete": "Cañete", "concon": "Concón",
    "olmue": "Olmué", "chanaral": "Chañaral", "vicuna": "Vicuña", "maullin": "Maullín",
    "chaiten": "Chaitén", "futaleufu": "Futaleufú",
}

# Palabra suelta (letras, incluidas las con tilde y la ñ).
_PALABRA = r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+"


def _mismo_formato(original, corregida):
    """Aplica las mayúsculas del original a la corrección: REGION → REGIÓN."""
    if original.isupper():
        return corregida.upper()
    if original[0].isupper() or corregida[0].isupper():
        return corregida[0].upper() + corregida[1:]
    return corregida


def _tilde_de(m):
    palabra = m.group()
    clave = palabra.lower()
    if clave in _CON_TILDE:
        return _mismo_formato(palabra, _CON_TILDE[clave])
    # Toda palabra terminada en -cion / -sion lleva tilde: construcción,
    # pavimentación, comisión. (El plural "-ciones" no la lleva y no calza.)
    t = re.fullmatch(r"([A-Za-zñÑ]{2,}[cCsS][iI])([oO])([nN])", palabra)
    if t:
        return t.group(1) + ("Ó" if t.group(2) == "O" else "ó") + t.group(3)
    return palabra


def tildes(serie):
    """
    Pone las tildes que no tienen duda: "Pavimentacion region del Biobio" →
    "Pavimentación región del Biobío". No toca correos ni direcciones web.
    """
    s = serie.astype(str)
    web = s.str.contains(r"@|://|www\.", case=False, regex=True)
    return s.where(web, s.str.replace(_PALABRA, _tilde_de, regex=True))


# ─────────────────────────────────────────────────────────────
# UNIDADES
# ─────────────────────────────────────────────────────────────

# Formas sueltas de una unidad, SIEMPRE detrás de un número ("1200 mts2"): así
# "ml" o "kg" sueltos en un texto no se tocan. Orden: las más largas primero.
_UNIDADES = [
    (r"m(?:ts?|etros?)?\.?\s*(?:2|²|cuadrados?)", "m2"),
    (r"m(?:ts?|etros?)?\.?\s*(?:3|³|c[uú]bicos?)", "m3"),
    (r"(?:m(?:ts?|etros?)?\.?\s*lineales?|ml)", "ml"),
    (r"(?:kgs?|kilos?|kilogramos?)", "kg"),
    (r"(?:kms?|kil[oó]metros?)", "km"),
    (r"(?:mts?|metros?)", "m"),
]


def unidades(serie):
    """Unidades a su forma corta: "1200 mts2" → "1200 m2", "15 metros cubicos" → "15 m3"."""
    s = serie.astype(str)
    for patron, corta in _UNIDADES:
        s = s.str.replace(rf"(\d)\s*{patron}(?![A-Za-zÁÉÍÓÚáéíóúñÑ0-9])", rf"\1 {corta}",
                          case=False, regex=True)
    return s


# ─────────────────────────────────────────────────────────────
# LIMPIEZA DE UN DATAFRAME COMPLETO
# ─────────────────────────────────────────────────────────────

# Tipo de cada columna según su nombre (la etiqueta del origen).
_NOMBRES = [
    ("fecha", ("fecha", "vencimiento", "emision", "apertura", "cierre", "inicio", "termino")),
    ("rut", ("rut", "rol unico")),
    ("correo", ("correo", "email", "e mail", "mail")),
    ("telefono", ("telefono", "fono", "celular", "movil", "whatsapp")),
    ("plazo", ("plazo", "duracion", "dias", "meses", "vigencia")),
    ("persona", ("representante", "contacto", "encargado", "responsable", "nombre del",
                 "nombre completo", "profesional", "inspector", "jefe", "firma")),
]
# Aunque digan "nombre", estas columnas son de empresas u obras, no de personas.
_NO_PERSONA = ("empresa", "razon social", "fantasia", "proyecto", "obra", "licitacion",
               "institucion", "servicio", "mandante", "organismo", "producto", "partida")
_ERRORES_EXCEL = {"#VALUE!", "#DIV/0!", "#N/A", "#REF!", "#NAME?", "#NUM!", "#NULL!", "#SPILL!", "#CALC!"}


def tipo_columna(nombre):
    n = _clave(nombre)
    for tipo, palabras in _NOMBRES:
        if any(re.search(rf"\b{p}\b", n) for p in palabras):
            if tipo == "persona" and any(p in n for p in _NO_PERSONA):
                return "texto"
            return tipo
    return "texto"


def limpiar_dataframe(df):
    """
    Limpia con pandas todas las columnas de texto del DataFrame y devuelve
    (df_limpio, resumen) con cuántas celdas cambió cada regla. Solo toca las
    celdas que son texto (o fechas de Excel): números, vacíos y demás quedan igual.

    Además de por su nombre, las fechas y los RUT se reconocen por su contenido
    (una celda "15/08/2024" es una fecha aunque la columna se llame "Apertura
    de ofertas"), siempre que la celda entera sea la fecha o el RUT.
    """
    df = df.copy()
    resumen = {"fechas": 0, "ruts": 0, "correos": 0, "telefonos": 0, "plazos": 0, "nombres": 0,
               "unidades": 0, "tildes": 0, "errores_excel": 0, "espacios": 0}

    for col in df.columns:
        serie = df[col]
        tipo = tipo_columna(col)
        if tipo == "telefono":
            # Todas las celdas, también las que Excel guardó como número
            # (56998019366): si no, la columna quedaba con formatos mezclados.
            normal = serie.map(telefono)
            hay = normal.notna()
            resumen["telefonos"] += int((normal[hay] != serie[hay].astype(str)).sum())
            df[col] = serie.astype(object).where(~hay, normal)
            serie = df[col]
        es_texto = serie.map(lambda v: isinstance(v, str))
        es_fecha_excel = serie.map(lambda v: isinstance(v, (datetime, date)))
        if not (es_texto.any() or es_fecha_excel.any()):
            continue
        # Como object: en una columna de tipo fecha, pandas volvería a convertir
        # el texto "01-09-2024" a fecha leyendo el mes primero (9 de enero).
        nueva = serie.astype(object)

        # Fechas de Excel (datetime) → "15-08-2024", en cualquier columna.
        if es_fecha_excel.any():
            nueva[es_fecha_excel] = fechas(serie[es_fecha_excel])
            resumen["fechas"] += int(es_fecha_excel.sum())

        texto = serie[es_texto]
        if texto.empty:
            df[col] = nueva
            continue

        # Espacios dobles y de los extremos; errores de fórmula → vacío.
        limpio = texto.str.replace(r"\s+", " ", regex=True).str.strip()
        error = limpio.str.upper().isin(_ERRORES_EXCEL)
        resumen["errores_excel"] += int(error.sum())
        limpio = limpio.mask(error, pd.NA)
        resumen["espacios"] += int((limpio.fillna("") != texto).sum() - error.sum())

        # Fecha: por nombre de columna o porque la celda entera es una fecha.
        como_fecha = fechas(limpio.dropna())
        if tipo != "fecha":
            # Sin nombre de fecha, solo fechas inequívocas (con año de 4 cifras
            # o el mes escrito): "12-10-25" podría ser un código.
            inequivoca = limpio.dropna().str.contains(rf"\d{{4}}|{_MES}", case=False, regex=True)
            como_fecha = como_fecha.where(inequivoca)
        hay = como_fecha.notna()
        resumen["fechas"] += int((como_fecha[hay] != limpio[hay.index[hay]]).sum())
        limpio.update(como_fecha[hay])

        # RUT: por nombre, o celda con forma de RUT con guion ("12345678-5").
        candidatos = limpio.dropna()
        if tipo != "rut":
            candidatos = candidatos[candidatos.str.fullmatch(r"\d{1,2}\.?\d{3}\.?\d{3}\s*-\s*[\dkK]")]
        ruts = candidatos.map(rut).dropna()
        resumen["ruts"] += int((ruts != limpio[ruts.index]).sum())
        limpio.update(ruts)

        if tipo == "correo":
            correos = limpio.dropna()
            correos = correos[correos.str.contains("@")].str.replace(" ", "").str.lower()
            resumen["correos"] += int((correos != limpio[correos.index]).sum())
            limpio.update(correos)
        elif tipo == "plazo":
            numeros = plazos(limpio.dropna()).dropna()
            resumen["plazos"] += int((numeros != limpio[numeros.index]).sum())
            limpio.update(numeros)
        elif tipo == "persona":
            # "juan perez (RUT 15234987-k)" → sin el RUT, que va en su propio campo.
            sin_rut = limpio.dropna().str.replace(r"\(?\s*\brut\b[^)]*\)?", "", case=False, regex=True)
            nombres = sin_rut.str.strip(" ,-").map(nombre_persona)
            resumen["nombres"] += int((nombres != limpio[nombres.index]).sum())
            limpio.update(nombres)

        # Tildes y unidades en todo texto que no sea dato con formato propio.
        if tipo in ("texto", "persona", "plazo"):
            pendientes = limpio.dropna()
            pendientes = pendientes[~pendientes.index.isin(ruts.index) & ~pendientes.index.isin(como_fecha[hay].index)]
            con_unidad = unidades(pendientes)
            resumen["unidades"] += int((con_unidad != pendientes).sum())
            con_tilde = tildes(con_unidad)
            resumen["tildes"] += int((con_tilde != con_unidad).sum())
            limpio.update(con_tilde)

        nueva[es_texto] = limpio
        df[col] = nueva

    return df, resumen


def resuelto_por_reglas(valor):
    """
    True si el valor ya quedó en su forma final con las reglas y no vale la pena
    mandarlo a la IA: fechas, RUT, correos, números, montos y cantidades con unidad.
    """
    if valor is None or isinstance(valor, (int, float, date, datetime)):
        return True
    s = str(valor).strip()
    return bool(
        not s
        or re.fullmatch(r"\d{2}-\d{2}-\d{4}|\d{2}-\d{4}", s)            # fecha ya normalizada
        or rut(s)
        or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", s)                 # correo
        or re.fullmatch(r"[\d\s.,$%+\-()/]+(?:UF|CLP|USD)?", s, re.IGNORECASE)  # números
        # Montos: "$ 150.000.000.- (ciento cincuenta millones)", "$59,500,000 pesos".
        # Los limpia la regla de montos y nunca salen a la IA (privacidad).
        or re.fullmatch(r"\$\s*\d[\d.,]*\s*\.?-?\s*(?:pesos|clp|uf)?\s*(?:\(.*\))?", s, re.IGNORECASE)
        or re.fullmatch(r"\d[\d.,]*\s*(?:m2|m3|ml|kg|km|m|%)", s)       # cantidad con unidad
    )
