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
import re

from django.conf import settings


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
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        modelo = genai.GenerativeModel(getattr(settings, "IA_MODEL", "gemini-flash-latest"))
        prompt = _construir_prompt(muestra, campos_destino)
        respuesta = modelo.generate_content(prompt)

        texto = respuesta.text.strip()
        # Quitar posibles vallas de markdown que a veces añade el modelo.
        texto = re.sub(r"^```(json)?|```$", "", texto, flags=re.MULTILINE).strip()
        propuesta = json.loads(texto)
        return propuesta, getattr(settings, "IA_MODEL", "gemini")
    except Exception:
        # Si la IA falla por cualquier razón, no rompemos el flujo: caemos a la
        # heurística local y seguimos. El usuario igual revisa y aprueba.
        return _propuesta_heuristica(muestra, campos_destino), "heuristica-respaldo"