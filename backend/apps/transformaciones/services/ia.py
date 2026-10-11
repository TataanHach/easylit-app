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

    return f"""Eres un asistente que mapea columnas de una planilla de licitación a un formato destino.

COLUMNAS DE ORIGEN (con muestras de datos):
{columnas_origen}

CAMPOS DEL FORMATO DESTINO:
{campos_texto}

Para cada columna de origen, indica a qué campo destino corresponde (o null si ninguno).
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
    return f"""Eres un asistente que limpia datos de licitaciones chilenas.
Para cada valor sucio, devuelve la versión LIMPIA según su tipo.

Reglas de QUÉ SÍ hacer:
- Fechas: formato YYYY-MM-DD si es clara; si es aproximada ("Agosto 2024 aprox."), lo más cercano (2024-08) sin inventar día.
- Números y plazos: extrae solo el número si viene con texto ("sesenta ( 60 ) Días" -> "60", "120 dias" -> "120").
- Unidades: normaliza lo evidente ("1200 mts2" -> "1200 m2").
- Espacios: corrige palabras partidas ("Servi cios" -> "Servicios") y espacios dobles.
- RUT: formato XX.XXX.XXX-X sin espacios internos.
- Emails: sin espacios.

Reglas de QUÉ NO hacer (MUY IMPORTANTE):
- NO expandas abreviaturas en NOMBRES de entidades, empresas o instituciones.
- "I. Municipalidad de Maipu" se queda "I. Municipalidad de Maipú" (solo corrige la tilde), NUNCA "Ilustre Municipalidad".
- NO agregues ni quites palabras en nombres propios.
- Si un valor NO es un dato real ("El mismo representante"), devuélvelo IGUAL.
- Si dudas, devuelve el valor ORIGINAL.
- NUNCA inventes información.

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