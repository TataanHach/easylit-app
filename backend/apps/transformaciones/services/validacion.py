"""
Servicio de validación aritmética (determinista, sin IA).

Esta es la red de seguridad del sistema. Después de limpiar y mapear, verifica
que los números cuadren ANTES de permitir generar el documento. Si algo no
cuadra, la transformación no se puede descargar. En una licitación, un total mal
calculado es dinero perdido, así que estas comprobaciones no son opcionales.

Devuelve una lista de comprobaciones, cada una con su resultado (ok/falla) y un
detalle legible. La regla de negocio: si CUALQUIER comprobación crítica falla,
`todo_ok` es False y la generación queda bloqueada.
"""
from decimal import Decimal


# Tolerancia para comparar montos (redondeos de centavos).
TOLERANCIA = Decimal("1.0")


def _cerca(a, b, tol=TOLERANCIA):
    if a is None or b is None:
        return False
    return abs(Decimal(str(a)) - Decimal(str(b))) <= tol


def validar(partidas, total_documento=None):
    """
    `partidas` es una lista de objetos Partida (del modelo). `total_documento` es
    el total que declara el archivo origen, para reconciliar.

    Devuelve dict con 'comprobaciones' (lista) y 'todo_ok' (bool).
    """
    comprobaciones = []
    solo_items = [p for p in partidas if not p.es_capitulo]

    # --- 1. Cantidad × Precio = Total, fila por fila ---
    filas_mal = []
    for p in solo_items:
        calc = p.total_calculado
        if p.total is not None and calc is not None and not _cerca(calc, p.total):
            filas_mal.append(p.codigo or p.descripcion[:30])
    comprobaciones.append({
        "clave": "linea",
        "titulo": "Cantidad × Precio = Total",
        "ok": len(filas_mal) == 0,
        "detalle": (
            f"{len(solo_items)} de {len(solo_items)} filas cuadran"
            if not filas_mal
            else f"{len(filas_mal)} filas no cuadran: {', '.join(filas_mal[:5])}"
        ),
        "critica": True,
    })

    # --- 2. Suma de partidas = subtotal de cada capítulo ---
    capitulos = [p for p in partidas if p.es_capitulo]
    caps_mal = []
    for cap in capitulos:
        hijos = [p for p in solo_items if p.capitulo == cap.codigo]
        suma_hijos = sum((p.total or Decimal(0)) for p in hijos)
        if cap.total is not None and not _cerca(suma_hijos, cap.total):
            caps_mal.append(cap.codigo)
    comprobaciones.append({
        "clave": "capitulo",
        "titulo": "Subtotales por capítulo",
        "ok": len(caps_mal) == 0,
        "detalle": (
            f"{len(capitulos)} de {len(capitulos)} capítulos cuadran"
            if not caps_mal
            else f"Capítulos que no cuadran: {', '.join(caps_mal)}"
        ),
        "critica": True,
    })

    # --- 3. Total general vs total del documento origen ---
    total_calculado = sum((p.total or Decimal(0)) for p in solo_items)
    if total_documento is not None:
        ok_total = _cerca(total_calculado, total_documento)
        comprobaciones.append({
            "clave": "total",
            "titulo": "Total vs documento origen",
            "ok": ok_total,
            "detalle": (
                "El total coincide con el documento original"
                if ok_total
                else f"Calculado {total_calculado} vs origen {total_documento}"
            ),
            "critica": True,
        })

    # --- 4. Ninguna partida sin unidad canónica ---
    sin_unidad = [
        p.codigo or p.descripcion[:30]
        for p in solo_items
        if p.unidad_canonica_id is None
    ]
    comprobaciones.append({
        "clave": "unidades",
        "titulo": "Unidades canónicas",
        "ok": len(sin_unidad) == 0,
        "detalle": (
            "Todas las partidas usan unidades del catálogo"
            if not sin_unidad
            else f"{len(sin_unidad)} partidas sin unidad asignada"
        ),
        "critica": True,
    })

    # --- 5. Sin partidas duplicadas (mismo código) ---
    codigos = [p.codigo for p in solo_items if p.codigo]
    duplicados = {c for c in codigos if codigos.count(c) > 1}
    comprobaciones.append({
        "clave": "duplicados",
        "titulo": "Sin partidas duplicadas",
        "ok": len(duplicados) == 0,
        "detalle": (
            "No hay códigos repetidos"
            if not duplicados
            else f"Códigos repetidos: {', '.join(list(duplicados)[:5])}"
        ),
        "critica": False,
    })

    # todo_ok solo considera las comprobaciones críticas.
    todo_ok = all(c["ok"] for c in comprobaciones if c["critica"])

    return {"comprobaciones": comprobaciones, "todo_ok": todo_ok}
