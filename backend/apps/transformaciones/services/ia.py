"""
Servicio de mapeo asistido por IA (Gemini).

Principio central del producto: la IA NUNCA toca los datos fila por fila. Solo ve
los encabezados de origen + el esquema destino, y propone qué columna va a qué
campo. El código determinista aplica esa propuesta a las 200 filas después de que
un humano la aprueba.

Anonimización: si la organización lo pide (por defecto sí), los montos ni siquiera
se envían. La IA solo necesita los NOMBRES de las columnas y unas pocas muestras
de texto para inferir la estructura; los precios se quedan en la empresa.

Modo simulado: si no hay clave de Gemini configurada, el servicio devuelve una
propuesta heurística local, para poder desarrollar y probar sin gastar API ni
exponer datos.
"""
import json
import logging
import re

import requests
from django.conf import settings

from .normalizacion import resuelto_por_reglas

# Temperatura 0: con los mismos datos, la IA responde siempre lo mismo. Con la
# temperatura por defecto, cada clic en "Limpiar con IA" daba un resultado distinto.
CONFIG_IA = {"temperature": 0}

logger = logging.getLogger(__name__)

_URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/{modelo}:generateContent"


def _llamar_gemini(prompt, timeout=None):
    """
    Envía el prompt a Gemini y devuelve el texto de la respuesta.

    Se llama a la API REST directo (HTTPS) en vez de usar la librería
    google-generativeai: esa librería depende de gRPC, cuyo .dll lo bloquea el
    Control de aplicaciones de Windows, y entonces la IA fallaba en silencio.
    Lanza una excepción con el motivo si Google responde con error.
    """
    modelo = getattr(settings, "IA_MODEL", "gemini-flash-latest")
    if not modelo.startswith("models/"):
        modelo = f"models/{modelo}"
    resp = requests.post(
        _URL_GEMINI.format(modelo=modelo),
        headers={"x-goog-api-key": settings.GEMINI_API_KEY},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": CONFIG_IA,
        },
        timeout=timeout or settings.IA_TIMEOUT_SEGUNDOS,
    )
    if resp.status_code != 200:
        try:
            motivo = resp.json().get("error", {}).get("message", "")
        except ValueError:
            motivo = resp.text[:200]
        raise RuntimeError(f"Gemini respondió {resp.status_code}: {motivo}")
    datos = resp.json()
    try:
        partes = datos["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        # Sin candidatos: suele ser un bloqueo por filtros de seguridad.
        raise RuntimeError(f"Gemini no devolvió respuesta: {datos.get('promptFeedback', datos)}")
    return "".join(p.get("text", "") for p in partes)


def _muestra_segura(df, columnas_numericas, anonimizar, filas=5):
    """
    Construye la muestra que se envía a la IA. Si anonimizar=True, reemplaza los
    valores de las columnas numéricas (montos) por un marcador, para que los
    precios reales nunca salgan de la empresa.
    """
    muestra = {}
    for col in df.columns:
        valores = df[col].dropna().head(filas).tolist()
        if anonimizar and col in columnas_numericas:
            muestra[col] = ["<número oculto>"] * len(valores)
        else:
            muestra[col] = [str(v)[:60] for v in valores]  # recortar por si acaso
    return muestra


def _construir_prompt(muestra, campos_destino):
    """Arma el prompt para que Gemini devuelva SOLO un JSON de mapeo."""
    campos_texto = "\n".join(
        f'  - "{c["nombre"]}" (tipo: {c["tipo"]}'
        + (f', moneda: {c["moneda_destino"]}' if c.get("moneda_destino") else "")
        + (", OBLIGATORIO" if c.get("obligatorio") else "")
        + (f') — {c["descripcion"]}' if c.get("descripcion") else ")")
        for c in campos_destino
    )
    columnas_origen = json.dumps(muestra, ensure_ascii=False, indent=2)

    return f"""Eres un asistente que mapea los datos de una planilla Excel de ORIGEN a los campos de un formato DESTINO.

COLUMNAS DE ORIGEN (con muestras de datos; "<número oculto>" = monto que no se muestra por privacidad):
{columnas_origen}

CAMPOS DEL FORMATO DESTINO:
{campos_texto}

Para cada columna de origen, indica a qué campo destino corresponde (o null si ninguno).
- Fíjate en el significado, no solo en el nombre: pueden llamarse distinto y ser el mismo dato
  (sinónimos, abreviaturas, otro idioma). Usa el tipo y la descripción de cada campo y las muestras.
- Cada campo destino recibe como máximo una columna de origen.
- Si una columna no corresponde a ningún campo, o dudas, responde null: es mejor dejar un campo vacío
  que llenarlo con otro dato.
- La confianza (0-100) debe reflejar tu seguridad real; si el nombre es ambiguo, que sea baja.
Responde ÚNICAMENTE con un JSON válido, sin texto adicional ni markdown, con esta forma exacta:
[
  {{"origen": "nombre columna origen", "destino": "nombre campo destino o null", "confianza": 0-100, "motivo": "breve"}}
]
"""


def _propuesta_heuristica(muestra, campos_destino):
    """
    Propuesta local sin IA: empareja por similitud de nombres y palabras clave.
    Sirve como modo simulado (sin clave) y como respaldo si la IA falla.
    """
    def normaliza(s):
        return re.sub(r"[^a-z0-9]", "", s.lower())

    def palabras(s):
        return set(re.findall(r"[a-z0-9]+", s.lower()))

    # Sinónimos frecuentes en licitaciones chilenas, para emparejar mejor.
    sinonimos = {
        "licitacion": {"proceso", "id", "codigo", "numero"},
        "objeto": {"descripcion", "obra", "nombre", "proyecto"},
        "monto": {"presupuesto", "valor", "total", "clp", "estimado"},
        "fecha": {"plazo", "cierre", "adjudicacion"},
        "cantidad": {"cant"},
        "precio": {"unitario", "pu", "valor"},
    }

    def expandir(pals):
        exp = set(pals)
        for p in pals:
            for clave, syns in sinonimos.items():
                if p == clave or p in syns:
                    exp.add(clave)
                    exp |= syns
        return exp

    resultado = []
    for origen in muestra.keys():
        o_norm = normaliza(origen)
        o_pals = expandir(palabras(origen))
        mejor, score = None, 0

        for c in campos_destino:
            d_norm = normaliza(c["nombre"])
            d_pals = expandir(palabras(c["nombre"]) | palabras(c.get("descripcion", "")))

            if o_norm == d_norm:
                mejor, score = c["nombre"], 95
                break
            if o_norm in d_norm or d_norm in o_norm:
                if 80 > score:
                    mejor, score = c["nombre"], 80
            # Coincidencia por palabras/sinónimos compartidos.
            comunes = o_pals & d_pals
            if comunes:
                s = min(75, 45 + 15 * len(comunes))
                if s > score:
                    mejor, score = c["nombre"], s

        resultado.append({
            "origen": origen,
            "destino": mejor,
            "confianza": score,
            "motivo": "Coincidencia por nombre" if score >= 80 else
                      ("Coincidencia por palabra clave" if mejor else "Sin coincidencia clara"),
        })
    return resultado


def _completar_por_nombre(propuesta, muestra, campos_destino):
    """
    Red de seguridad tras la IA: un campo que quedó sin dato se asigna si una
    columna libre del origen tiene un nombre que claramente le corresponde
    (puntaje 80+: "RUT" ⊂ "RUT Legal"). Así un campo obvio no queda vacío solo
    porque la IA lo pasó por alto. Las coincidencias por una palabra suelta no
    se usan: podrían asignar mal.
    """
    asignados = {p.get("destino") for p in propuesta if p.get("destino")}
    usados = {p.get("origen") for p in propuesta if p.get("destino")}
    for h in _propuesta_heuristica(muestra, campos_destino):
        if (not h["destino"] or h["confianza"] < 80
                or h["destino"] in asignados or h["origen"] in usados):
            continue
        nuevo = {**h, "motivo": "Asignado por coincidencia de nombre: la IA lo había dejado sin dato."}
        existente = next((p for p in propuesta if p.get("origen") == h["origen"]), None)
        if existente is not None:
            existente.update(nuevo)
        else:
            propuesta.append(nuevo)
        asignados.add(h["destino"])
        usados.add(h["origen"])
    return propuesta


def proponer_mapeo(df, columnas_numericas, campos_destino, anonimizar=True):
    """
    Devuelve la lista de mapeos propuestos. Usa Gemini si hay clave; si no, la
    heurística local. Cada elemento: {origen, destino, confianza, motivo}.
    """
    muestra = _muestra_segura(df, columnas_numericas, anonimizar)

    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        # Modo simulado: sin clave, propuesta local. No se envía nada a internet.
        return _propuesta_heuristica(muestra, campos_destino), "heuristica-local"

    try:
        prompt = _construir_prompt(muestra, campos_destino)
        texto = _llamar_gemini(prompt).strip()
        # Quitar posibles vallas de markdown que a veces añade el modelo.
        texto = re.sub(r"^```(json)?|```$", "", texto, flags=re.MULTILINE).strip()
        propuesta = json.loads(texto)
        return _completar_por_nombre(propuesta, muestra, campos_destino), getattr(settings, "IA_MODEL", "gemini")
    except Exception:
        # Si la IA falla por cualquier razón, no rompemos el flujo: caemos a la
        # heurística local y seguimos. El usuario igual revisa y aprueba. El
        # motivo queda en el log del worker para poder diagnosticarlo.
        logger.exception("Falló el mapeo con Gemini; se usa la heurística local")
        return _propuesta_heuristica(muestra, campos_destino), "heuristica-respaldo"

# ═════════════════════════════════════════════════════════════
# Columnas de TABLAS que no calzaron por nombre («Numero» vs «Telefono»).
# Las columnas se emparejan primero por nombre, gratis y exacto; a la IA solo
# se le preguntan las que quedaron sin pareja.
# ═════════════════════════════════════════════════════════════

# Bajo esta confianza la sugerencia no se usa: mejor una columna vacía que
# una llena con datos que no corresponden.
CONFIANZA_MINIMA_COLUMNA = 50


def _construir_prompt_columnas(pedido):
    hojas = json.dumps(pedido, ensure_ascii=False, indent=2)
    return f"""Eres un asistente que empareja columnas de tablas entre dos planillas Excel.

Para cada hoja tienes:
- "titulo": el texto que hay sobre la tabla DESTINO (puede venir vacío).
- "columnas_destino": todas las columnas de la tabla DESTINO, para que entiendas de qué trata.
- "sin_pareja": columnas DESTINO que no encontraron una columna con el mismo nombre.
- "origen": las columnas de la planilla de ORIGEN, con algunos ejemplos de sus datos.

{hojas}

Para cada columna de "sin_pareja", indica qué columna de "origen" trae ese mismo dato, o null si ninguna.
- Fíjate en el significado, no solo en el nombre: dos columnas pueden llamarse distinto y traer el
  mismo dato (sinónimos, abreviaturas, otro idioma).
- Si el nombre es corto o ambiguo, interprétalo según el título, las demás columnas de la tabla
  destino y los ejemplos del origen: decide qué dato tiene sentido en esa tabla.
- Si la columna destino solo numera las filas (un correlativo) y el origen no trae uno, responde null.
- Si ninguna columna del origen trae ese dato, responde null: es mejor dejar la columna vacía que
  llenarla con otro dato.
- El valor de "origen" debe ser EXACTAMENTE uno de los nombres de columna del origen de esa hoja.

Responde ÚNICAMENTE con un JSON válido, sin texto adicional ni markdown, así:
[
  {{"hoja": "nombre hoja", "destino": "columna destino", "origen": "columna origen o null", "confianza": 0-100, "motivo": "breve"}}
]
"""


def sugerir_columnas_tablas(pedido):
    """
    pedido: {hoja: {"sin_pareja": [...], "origen": {columna: [ejemplos]}}}, armado
    por generacion.pedido_ia_columnas (montos ya ocultos).
    Devuelve ({hoja: {destino: {origen, confianza, motivo}}}, modelo_usado).
    Sin clave o si la IA falla, devuelve {} y las columnas quedan como estaban.
    """
    if not pedido:
        return {}, "sin-columnas"
    if not getattr(settings, "GEMINI_API_KEY", ""):
        return {}, "sin-clave-ia"
    try:
        texto = _llamar_gemini(_construir_prompt_columnas(pedido)) or ""
        texto = re.sub(r"```(json)?", "", texto).strip()
        inicio, fin = texto.find("["), texto.rfind("]")
        if inicio != -1 and fin > inicio:
            texto = texto[inicio:fin + 1]
        respuesta = json.loads(texto)
    except Exception:
        logger.exception("Falló el emparejamiento de columnas con Gemini")
        return {}, "columnas-ia-fallo"

    sugerencias = {}
    for r in respuesta if isinstance(respuesta, list) else []:
        if not isinstance(r, dict):
            continue
        hoja, destino, origen = r.get("hoja"), r.get("destino"), r.get("origen")
        info = pedido.get(hoja)
        try:
            confianza = int(r.get("confianza") or 0)
        except (TypeError, ValueError):
            confianza = 0
        # Solo lo que se preguntó y columnas que existen: la IA puede inventar nombres.
        if (not info or destino not in info["sin_pareja"] or origen not in info["origen"]
                or confianza < CONFIANZA_MINIMA_COLUMNA):
            continue
        sugerencias.setdefault(hoja, {})[destino] = {
            "origen": origen, "confianza": confianza, "motivo": str(r.get("motivo") or "")[:200],
        }
    return sugerencias, getattr(settings, "IA_MODEL", "gemini")


# ═════════════════════════════════════════════════════════════
# CAPA 2 DEL ESCALÓN 4: limpieza inteligente de datos con IA.
#
# Limpia SOLO texto y fechas (nunca montos: esos se protegen y los limpia la
# Capa 1 local, sin enviarlos a Google). Se usa cuando el usuario lo pide
# explícitamente (botón "Limpiar con IA"), para no gastar cuota sin necesidad.
# ═════════════════════════════════════════════════════════════

# Formatos que son MONETARIOS: NUNCA se mandan a la IA (privacidad).
_FORMATOS_SENSIBLES = {"PESOS", "PESOS_DEC", "UF"}


def _construir_prompt_limpieza(items):
    """items: lista de {n, campo, tipo, valor}. Arma el prompt para Gemini."""
    lista = "\n".join(
        f'  {it["n"]}. Campo "{it["campo"]}" (tipo {it["tipo"]}): "{it["valor"]}"'
        for it in items
    )
    return f"""Eres un asistente que limpia datos de planillas Excel chilenas.
Para cada valor, devuelve la versión LIMPIA según el TIPO de su campo. El nombre del campo es solo contexto.

Según el tipo:
- FECHA: formato YYYY-MM-DD si la fecha es clara; si solo trae mes y año, YYYY-MM sin inventar el día.
- NUMERO: solo el número, aunque venga escrito en palabras o con texto alrededor.
- TEXTO (y cualquier otro tipo): conserva el contenido; solo corrige la forma.

Para todos los tipos:
- Espacios: quita los dobles y une palabras partidas por un espacio de más.
- Tildes y mayúsculas: corrige solo errores evidentes.
- RUT: formato XX.XXX.XXX-X sin espacios. Correos: sin espacios.

Lo que NUNCA se hace:
- Quitar, agregar o cambiar palabras de un TEXTO, ni sacar números de él.
- Expandir o cambiar abreviaturas de nombres propios (personas, empresas, instituciones).
- Inventar información.
- Si un valor no es un dato (una nota, una referencia a otro campo), o si dudas, devuélvelo IGUAL.

VALORES A LIMPIAR:
{lista}

Responde ÚNICAMENTE con un JSON válido, sin texto adicional ni markdown, así:
[
  {{"n": 1, "limpio": "valor limpio"}}
]
"""


def limpiar_con_ia(valores_campos):
    """
    valores_campos: lista de dicts con:
        - campo: el CampoPlantilla (para saber tipo y formato)
        - valor: el valor sucio a limpiar
    Devuelve (lista_valores_limpios, modelo_usado). La lista mantiene el mismo
    orden y largo que la entrada; los montos se dejan intactos.

    Si no hay clave o la IA falla, devuelve los valores SIN cambios (no rompe).
    """
    api_key = getattr(settings, "GEMINI_API_KEY", "")

    # Preparar solo los que NO son montos (privacidad) y son texto/fecha no vacíos.
    a_limpiar = []
    for i, item in enumerate(valores_campos):
        campo = item["campo"]
        valor = item["valor"]
        formato = getattr(campo, "formato_numero", "") or "NINGUNO"
        # Saltar montos (sensibles) y vacíos.
        if formato in _FORMATOS_SENSIBLES:
            continue
        if valor is None or str(valor).strip() == "":
            continue
        # Fechas, RUT, correos y números ya los dejó listos la limpieza con
        # pandas (normalizacion.py): mandarlos a la IA solo gasta cuota.
        if resuelto_por_reglas(valor):
            continue
        a_limpiar.append({
            "n": i,  # índice original, para devolver en orden
            "campo": getattr(campo, "nombre", ""),
            "tipo": getattr(campo, "tipo", "TEXTO"),
            "valor": str(valor),
        })

    # Copia de los valores originales (los que no se limpian quedan igual).
    resultado = [item["valor"] for item in valores_campos]

    if not a_limpiar:
        return resultado, "sin-limpieza-ia"
    if not api_key:
        return resultado, "sin-clave-ia"

    try:
        prompt = _construir_prompt_limpieza(a_limpiar)
        texto = _llamar_gemini(prompt) or ""
        texto = re.sub(r"```(json)?", "", texto).strip()
        inicio = texto.find("[")
        fin = texto.rfind("]")
        if inicio != -1 and fin != -1 and fin > inicio:
            texto = texto[inicio:fin + 1]
        limpios = json.loads(texto)
        if not isinstance(limpios, list):
            return resultado, "limpieza-ia-sin-formato"

        # Aplicar cada valor limpio en su índice original.
        for entrada in limpios:
            n = entrada.get("n")
            limpio = entrada.get("limpio")
            if n is not None and 0 <= n < len(resultado) and limpio is not None:
                resultado[n] = limpio

        return resultado, getattr(settings, "IA_MODEL", "gemini")
    except Exception:
        # Si la IA falla, devolver los valores sin cambios (el motivo va al log).
        logger.exception("Falló la limpieza con Gemini")
        return resultado, "limpieza-ia-fallo"