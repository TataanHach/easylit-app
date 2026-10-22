/**
 * Editor de mapeo + vista previa por hojas.
 *
 * Orden: Vista previa (arriba) → BOTONES (medio) → Mapeo (abajo).
 * En la vista previa, los campos de moneda tienen un control de IVA que
 * reemplaza el de la plantilla para esta transformación.
 */
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { plantillaService } from "@/features/plantillas/plantillaService";
import { nombreDescarga, transformacionService } from "@/features/historial/historialService";
import { useAvisos } from "@/components/ui/Avisos";
import { describirError } from "@/lib/errores";
import { useConfiguracion } from "@/lib/configuracion";
import ResultadoModal, { type Resultado } from "@/components/ui/ResultadoModal";
import "./mapeo.css";

/** Lista para la ventana de resultado: hasta `max` ítems y "… y N más". */
function resumir(items: string[], max = 8): string[] {
  return items.length <= max ? items : [...items.slice(0, max), `… y ${items.length - max} más.`];
}

interface EstadoCampo { campo: string; hoja: string; ok: boolean; valor: string }

/** De qué columna del origen sale una columna de tabla, y por qué. */
interface ParejaColumna {
  destino: string; origen: string | null;
  fuente: "usuario" | "nombre" | "ia" | "ninguna"; motivo: string;
}
const FUENTE_COLUMNA: Record<string, string> = {
  usuario: "Elegida por ti",
  nombre: "Emparejada por nombre",
  ia: "Sugerida por la IA: revísala",
  vacia: "Quedará vacía: elige una columna del origen si corresponde",
};

/**
 * Campos que se llenarán, agrupados por hoja ("Hoja «X»: 3 de 4 campos"), con
 * el valor que llevará cada uno. Los que quedan vacíos van en su propio grupo.
 */
/**
 * Lo que la limpieza automática (pandas, sin IA) corrigió al leer el archivo.
 * Es informativo: no vuelve "amarilla" la ventana.
 */
function grupoLimpiezaAuto(resumen?: Record<string, number>) {
  if (!resumen) return [];
  const textos: Record<string, (n: number) => string> = {
    fechas: (n) => `${n} fecha(s) al formato 15-08-2024`,
    ruts: (n) => `${n} RUT con puntos y guion (dígito verificador comprobado)`,
    correos: (n) => `${n} correo(s) sin espacios y en minúsculas`,
    plazos: (n) => `${n} plazo(s) o cantidad(es) a número («sesenta (60) días» → 60)`,
    nombres: (n) => `${n} nombre(s) de persona con mayúsculas iniciales`,
    unidades: (n) => `${n} unidad(es) normalizada(s) («mts2» → m2)`,
    tildes: (n) => `${n} texto(s) con tildes corregidas`,
    errores_excel: (n) => `${n} error(es) de fórmula de Excel (#VALUE!…) dejados vacíos`,
  };
  const items = Object.entries(textos)
    .filter(([clave]) => (resumen[clave] ?? 0) > 0)
    .map(([clave, texto]) => texto(resumen[clave]));
  return items.length ? [{ titulo: "Limpieza automática, sin IA", items }] : [];
}

function gruposPorHoja(estados: EstadoCampo[]) {
  const hojas = [...new Set(estados.map((e) => e.hoja))];
  return hojas.map((hoja) => {
    const deLaHoja = estados.filter((e) => e.hoja === hoja);
    const llenos = deLaHoja.filter((e) => e.ok);
    return {
      titulo: `Hoja «${hoja}»: ${llenos.length} de ${deLaHoja.length} campos se llenarán`,
      items: resumir(llenos.map((e) => `✓ «${e.campo}»: ${e.valor || "(vacío)"}`)),
    };
  }).filter((g) => g.items.length > 0);
}

/** Opciones del control de IVA; el porcentaje lo define el backend (IVA_TASA). */
function opcionesIVA(porcentaje: number) {
  return [
    { v: "NINGUNO", t: "Sin IVA" },
    { v: "AGREGAR", t: `+ IVA (${porcentaje.toLocaleString("es-CL")}%)` },
    { v: "QUITAR", t: "Neto (−IVA)" },
  ];
}

export default function MapeoPage() {
  const IVA_OPCIONES = opcionesIVA(useConfiguracion().iva_porcentaje);
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const avisos = useAvisos();
  const [generando, setGenerando] = useState(false);
  const [generado, setGenerado] = useState(false);
  const [mapeosLocal, setMapeosLocal] = useState<any[]>([]);
  const [guardandoId, setGuardandoId] = useState<string | null>(null);
  const [limpiando, setLimpiando] = useState(false);
  const [hojaActiva, setHojaActiva] = useState(0);
  const [hojaMapeo, setHojaMapeo] = useState(0);   // hoja visible en «Mapeo propuesto»
  // Ventana emergente con el resultado del procesamiento o de la generación.
  const [resultado, setResultado] = useState<Resultado | null>(null);

  const { data: t, isLoading, isFetchedAfterMount, refetch } = useQuery({
    queryKey: ["transformacion", id],
    queryFn: () => transformacionService.detalle(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const estado = query.state.data?.estado;
      const enProceso = estado === "BORRADOR" || estado === "LIMPIEZA" || estado === "MAPEO_PROPUESTO";
      return enProceso ? 2000 : false;
    },
  });

  const { data: plantilla } = useQuery({
    queryKey: ["plantilla", t?.plantilla],
    queryFn: () => plantillaService.detalle(t!.plantilla),
    enabled: !!t?.plantilla,
  });

  const { data: preview, refetch: refetchPreview } = useQuery({
    queryKey: ["vistaPrevia", id],
    queryFn: () => transformacionService.vistaPrevia(id!),
    enabled: !!id && !!t && t.estado === "EN_REVISION",
  });

  useEffect(() => {
    if (t?.mapeos) setMapeosLocal(t.mapeos);
  }, [t?.mapeos]);

  // Mientras el worker procesa se muestra la animación de pasos. Aunque el
  // backend termine, la animación completa los pasos que faltan antes de pasar
  // a la revisión (si no, los pasos rápidos ni se alcanzan a ver).
  // Solo cuenta el estado consultado al abrir la pantalla: el de la caché puede
  // ser viejo (ej. quedó en LIMPIEZA y ya está EN_REVISION) y lanzaría la
  // animación de nuevo.
  const estadoEnProceso = t?.estado === "BORRADOR" || t?.estado === "LIMPIEZA" || t?.estado === "MAPEO_PROPUESTO";
  const enProceso = isFetchedAfterMount && estadoEnProceso;
  const [animandoProceso, setAnimandoProceso] = useState(false);
  useEffect(() => {
    if (enProceso) setAnimandoProceso(true);
  }, [enProceso]);

  // Si el procesamiento que se estaba mirando termina en error, avisarlo.
  const vioProceso = useRef(false);
  useEffect(() => {
    if (enProceso) vioProceso.current = true;
    if (vioProceso.current && t?.estado === "ERROR") {
      vioProceso.current = false;
      setResultado({
        estado: "error",
        titulo: "La transformación falló",
        mensaje: t.detalle_error || "Ocurrió un problema al procesar el archivo. Puede que no sea un Excel válido o que esté dañado.",
        grupos: [{
          titulo: "¿Qué puedes hacer?",
          items: ["Corrige el archivo según lo indicado y crea una nueva transformación.",
                  "Esta quedará en el historial con estado «Error»."],
        }],
      });
    }
  }, [enProceso, t?.estado, t?.detalle_error]);

  /**
   * Al terminar la animación: pasar a revisión y mostrar en una ventana cómo
   * salió: ✓ todo listo, ⚠ qué hay que revisar (y dónde), ✗ por qué falló.
   */
  async function terminarProceso() {
    setAnimandoProceso(false);
    vioProceso.current = false;
    if (!t || t.estado !== "EN_REVISION") return;

    const lista = t.mapeos ?? [];
    const total = lista.length;
    const asignados = lista.filter((m) => m.destino_campo).length;
    const confianza = t.confianza ?? 0;
    const avisoIA = t.resultado_limpieza?.aviso_ia as string | undefined;
    const tablas = (t.resultado_limpieza?.hojas_itemizado as string[] | undefined) ?? [];

    // Columnas de las tablas de la plantilla que no encontraron pareja en el origen.
    const emparejadas = (t.resultado_limpieza?.tablas_emparejadas ?? {}) as Record<
      string, {
        columnas: number; emparejadas: number; sin_pareja: string[];
        por_ia?: { destino: string; origen: string; motivo: string }[];
      }
    >;
    const colsTotal = Object.values(emparejadas).reduce((s, i) => s + i.columnas, 0);
    const colsOk = Object.values(emparejadas).reduce((s, i) => s + i.emparejadas, 0);

    if (total === 0 && tablas.length === 0) {
      setResultado({
        estado: "error",
        titulo: "El archivo no tiene datos que usar",
        mensaje: "No se encontraron columnas, etiquetas ni tablas en el archivo de origen, así que no hay nada que pasar a la plantilla.",
        grupos: [{ titulo: "¿Qué puedes hacer?", items: [
          "Revisa que el Excel tenga encabezados y valores (no solo imágenes o celdas vacías).",
          "Corrígelo y crea una nueva transformación.",
        ] }],
      });
      return;
    }

    // Lo que quedará vacío en el documento y el estado de cada campo: lo
    // calcula la vista previa.
    const previa = await refetchPreview();
    const pendientes: string[] = previa.data?.avisos ?? [];
    const estados: EstadoCampo[] = previa.data?.campos_estado ?? [];
    const llenos = estados.filter((e) => e.ok).length;
    const hojasConCampos = new Set(estados.map((e) => e.hoja)).size;

    const grupos: { titulo: string; items: string[] }[] = [];
    if (pendientes.length) {
      grupos.push({ titulo: "Campos que quedarán vacíos en el documento", items: resumir(pendientes) });
    }
    Object.entries(emparejadas).forEach(([hoja, info]) => {
      if (info.sin_pareja.length) {
        grupos.push({
          titulo: `Tabla «${hoja}»: columnas sin pareja en el origen`,
          items: resumir(info.sin_pareja.map((c) => `«${c}» quedará vacía: el origen no tiene una columna parecida.`)),
        });
      }
      // Parejas que sugirió la IA (no calzaban por nombre): conviene revisarlas.
      if (info.por_ia?.length) {
        grupos.push({
          titulo: `Tabla «${hoja}»: columnas emparejadas por la IA (revísalas en el encabezado de la tabla, en la vista previa)`,
          items: resumir(info.por_ia.map((p) => `«${p.destino}» ← «${p.origen}»${p.motivo ? `: ${p.motivo}` : ""}`)),
        });
      }
    });
    const bajas = lista.filter((m) => m.destino_campo && m.confianza < 60);
    if (bajas.length) {
      grupos.push({
        titulo: "Asignaciones con confianza baja (revísalas en el mapeo)",
        items: resumir(bajas.map((m) => `«${m.origen_columna}» (${m.confianza}%)${m.motivo ? `: ${m.motivo}` : ""}`)),
      });
    }
    if (avisoIA) grupos.push({ titulo: "Inteligencia artificial", items: [avisoIA] });

    const cifras = [
      ...(estados.length ? [{ etiqueta: "campos llenos", valor: `${llenos} de ${estados.length}` }] : []),
      ...(hojasConCampos ? [{ etiqueta: hojasConCampos === 1 ? "hoja con campos" : "hojas con campos", valor: hojasConCampos }] : []),
      ...(total ? [{ etiqueta: "datos asignados", valor: `${asignados} de ${total}` }] : []),
      ...(colsTotal ? [{ etiqueta: "columnas de tabla", valor: `${colsOk} de ${colsTotal}` }] : []),
      { etiqueta: "confianza", valor: `${confianza}%` },
    ];

    const porHoja = gruposPorHoja(estados);
    const auto = grupoLimpiezaAuto(t.resultado_limpieza?.normalizacion as Record<string, number> | undefined);

    if (total > 0 && asignados === 0 && tablas.length === 0) {
      setResultado({
        estado: "error",
        titulo: "No se pudo asignar ningún dato",
        mensaje: "No se encontró a qué campo de la plantilla corresponde cada dato del archivo, así que el documento saldría vacío. Asígnalos a mano en «Mapeo propuesto» antes de generar.",
        cifras,
        grupos,
      });
    } else if (grupos.length > 0) {
      setResultado({
        estado: "advertencia",
        titulo: "Transformación lista, con cosas por revisar",
        mensaje: "Los datos se procesaron, pero lo siguiente no quedará bien si generas ahora. Corrígelo en la vista previa y en «Mapeo propuesto», o genera igual.",
        cifras,
        grupos: [...grupos, ...auto, ...porHoja],
      });
    } else {
      setResultado({
        estado: "exito",
        titulo: "Transformación procesada con éxito",
        mensaje: `${total ? `Los ${total} datos tienen su campo destino` : "Las tablas se emparejaron completas"}${tablas.length ? ` y ${tablas.length === 1 ? "la tabla «" + tablas[0] + "» está lista" : `las ${tablas.length} tablas están listas`}` : ""}. Revisa la vista previa y genera el documento.`,
        cifras,
        grupos: [...auto, ...porHoja],
      });
    }
  }

  /** Elige qué dato del origen va en un campo de la plantilla ("" = sin dato). */
  async function cambiarDato(campoId: string, campoNombre: string, columna: string) {
    if (!id) return;
    const anteriores = mapeosLocal;
    // Cambio optimista: el dato elegido pasa a este campo y el anterior queda libre.
    setMapeosLocal((prev) => prev.map((m) => {
      if (columna && m.origen_columna === columna) return { ...m, destino_campo: campoId };
      if (m.destino_campo === campoId) return { ...m, destino_campo: null };
      return m;
    }));
    setGuardandoId(campoId);
    try {
      const r = await transformacionService.asignarDato(id, campoId, columna || null);
      setMapeosLocal(r.mapeos);
      if (r.quitado_de) {
        avisos.info(
          "Dato movido de campo",
          `«${columna}» ya no rellena «${r.quitado_de}»: ahora va en «${campoNombre}». Si «${r.quitado_de}» necesita un dato, elígelo en su fila.`
        );
      }
      await refetchPreview();
    } catch (e) {
      // Volver a lo que había para no mostrar un cambio que no se aplicó.
      setMapeosLocal(anteriores);
      avisos.error(describirError(e, `cambiar el dato de «${campoNombre}»`));
    } finally {
      setGuardandoId(null);
    }
  }

  async function cambiarIVA(campoNombre: string, ajuste: string) {
    if (!id) return;
    try {
      await transformacionService.ajustarIVA(id, campoNombre, ajuste);
      await refetchPreview();
    } catch (e) {
      avisos.error(describirError(e, `ajustar el IVA de «${campoNombre}»`));
    }
  }

  const [guardandoColumna, setGuardandoColumna] = useState<string | null>(null);

  async function cambiarColumna(hojaNombre: string, destino: string, origen: string) {
    if (!id) return;
    setGuardandoColumna(destino);
    try {
      await transformacionService.asignarColumna(id, hojaNombre, destino, origen || null);
      await Promise.all([refetchPreview(), refetch()]);
    } catch (e) {
      avisos.error(describirError(e, `cambiar la columna «${destino}»`));
    } finally {
      setGuardandoColumna(null);
    }
  }

  const [calculandoTotales, setCalculandoTotales] = useState(false);

  async function alternarTotales(activar: boolean, faltantes: number) {
    if (!id) return;
    setCalculandoTotales(true);
    try {
      await transformacionService.calcularTotales(id, activar);
      await refetchPreview();
      if (activar) {
        avisos.exito(
          "Totales calculados",
          `Se completaron ${faltantes} total(es) como precio × cantidad. Están marcados en la vista previa y se incluirán en el documento.`
        );
      } else {
        avisos.info("Cálculo de totales quitado", "Los totales faltantes volverán a quedar vacíos en el documento.");
      }
    } catch (e) {
      avisos.error(describirError(e, activar ? "calcular los totales" : "quitar el cálculo de totales"));
    } finally {
      setCalculandoTotales(false);
    }
  }

  /**
   * Limpia con IA los textos y fechas, y muestra el resultado en una ventana:
   * ✓ qué cambió (antes → después), ⚠ no había nada que limpiar, ✗ por qué falló.
   */
  async function limpiarConIA() {
    if (!id) return;
    setLimpiando(true);
    try {
      const r = await transformacionService.limpiarIA(id);
      const listaCambios = (cs: { campo: string; antes: string; despues: string }[] = []) =>
        resumir(cs.map((c) => `«${c.campo}»: «${c.antes || "(vacío)"}» → «${c.despues || "(vacío)"}»`), 10);

      if (r.modelo && (r.modelo.startsWith("gemini") || r.modelo.startsWith("models/"))) {
        const grupos = [
          ...(r.cambios?.length ? [{ titulo: "Campos corregidos", items: listaCambios(r.cambios) }] : []),
          ...(r.cambios_tabla?.length ? [{ titulo: "Textos de tablas corregidos", items: listaCambios(r.cambios_tabla) }] : []),
        ];
        setResultado({
          estado: "exito",
          titulo: grupos.length ? "Limpieza con IA lista" : "Los datos ya estaban limpios",
          mensaje: (r.repetida
            ? "Estos mismos datos ya se habían limpiado, así que se muestra ese resultado sin volver a consultar a la IA. "
            : "")
            + (grupos.length
              ? "La IA corrigió los textos y fechas de abajo. En la vista previa están marcados con ✦: revísalos antes de generar."
              : "La IA revisó los textos y fechas y no encontró nada que corregir."),
          cifras: [
            { etiqueta: "campos corregidos", valor: `${r.campos ?? 0} de ${r.campos_revisados ?? 0}` },
            { etiqueta: "textos de tablas", valor: `${r.textos_tabla ?? 0} de ${r.textos_tabla_revisados ?? 0}` },
          ],
          grupos,
        });
      } else if (r.modelo === "sin-limpieza-ia") {
        setResultado({
          estado: "advertencia",
          titulo: "No había nada que limpiar",
          mensaje: "Ni los campos con dato asignado ni las tablas tienen textos o fechas que limpiar. Los montos y cantidades nunca se envían a la IA, por privacidad.",
        });
      } else if (r.modelo === "sin-clave-ia") {
        setResultado({
          estado: "error",
          titulo: "La IA no está configurada",
          mensaje: "Falta la clave de Gemini en el servidor (GEMINI_API_KEY), así que no se limpió nada. Pídele al administrador que la configure. Puedes generar el documento igual."
            + (r.conserva_anterior ? " Se mantiene la limpieza que ya habías hecho." : ""),
        });
      } else {
        setResultado({
          estado: "error",
          titulo: "La IA no pudo limpiar los datos",
          mensaje: "Puede que se haya agotado la cuota de Gemini (si apretaste el botón varias veces seguidas, espera un minuto) o que no haya conexión. "
            + (r.conserva_anterior
              ? "Se mantiene la limpieza que ya habías hecho, sin cambios."
              : "Los datos quedaron como estaban: puedes generar igual o intentarlo más tarde."),
        });
      }
      await refetchPreview();
    } catch (e) {
      const { detalle } = describirError(e, "limpiar los datos con IA");
      setResultado({ estado: "error", titulo: "No se pudieron limpiar los datos con IA", mensaje: detalle });
    } finally {
      setLimpiando(false);
    }
  }

  async function generar() {
    if (!id) return;
    setGenerando(true);
    try {
      const r = await transformacionService.generar(id);
      await refetch();
      setGenerado(true);
      const pendientes = r.avisos ?? [];
      // Se generó, pero si quedó algo sin llenar no basta con un "éxito".
      setResultado(pendientes.length > 0 ? {
        estado: "advertencia",
        titulo: "Documento generado, pero incompleto",
        mensaje: `${pendientes.length === 1 ? "1 dato quedó" : `${pendientes.length} datos quedaron`} sin llenar. Puedes descargarlo igual, o corregir y generar otra transformación.`,
        grupos: [{ titulo: "Lo que quedó vacío y por qué", items: resumir(pendientes, 12) }],
      } : {
        estado: "exito",
        titulo: "Documento generado con éxito",
        mensaje: "Todos los campos y tablas se llenaron. El documento está listo para descargar.",
      });
    } catch (e) {
      const { detalle } = describirError(e, "generar el documento");
      setResultado({ estado: "error", titulo: "No se pudo generar el documento", mensaje: detalle });
      await refetch();
    } finally {
      setGenerando(false);
    }
  }

  async function descargar() {
    if (!id || !t) return;
    try {
      const archivo = nombreDescarga(t);
      await transformacionService.descargar(id, archivo);
      avisos.exito("Descarga iniciada", `«${archivo}» se está guardando en tu carpeta de descargas.`);
    } catch (e) {
      avisos.error(describirError(e, "descargar el documento"));
    }
  }

  if (isLoading || (estadoEnProceso && !isFetchedAfterMount)) {
    return <div style={{ padding: 40, textAlign: "center", color: "var(--text-3)" }}>
      <i aria-hidden="true" className="ti ti-loader-2" style={{ fontSize: 22 }} /><p style={{ marginTop: 8 }}>Cargando…</p>
    </div>;
  }
  if (!t) {
    return (
      <div style={{ maxWidth: 640 }}>
        <div className="banda banda-error">
          <i aria-hidden="true" className="ti ti-alert-circle" />
          <div>
            <strong>No se encontró la transformación</strong>
            Puede que se haya eliminado o que no tengas acceso a ella. Vuelve al historial y elige otra.
          </div>
        </div>
        <button className="btn btn-lg" onClick={() => navigate("/historial")}>Ir al historial</button>
      </div>
    );
  }

  if (t.estado !== "ERROR" && (enProceso || animandoProceso)) {
    return (
      <ProcesandoIA estado={t.estado} nombre={t.nombre || t.nombre_origen}
        onTerminar={terminarProceso} />
    );
  }

  if (t.estado === "ERROR") {
    return (
      <div style={{ maxWidth: 640 }}>
      {resultado && <ResultadoModal resultado={resultado} onAceptar={() => setResultado(null)} />}
        <div className="mapeo-header"><h1>Hubo un problema</h1></div>
        <div style={{
          background: "var(--danger-50)", border: "1px solid var(--danger-100)",
          borderRadius: "var(--r-lg)", padding: 24, color: "var(--danger-700)",
        }}>
          <i aria-hidden="true" className="ti ti-alert-triangle" style={{ fontSize: 28 }} />
          <p style={{ marginTop: 8 }}><strong>No se pudo procesar «{t.nombre || t.nombre_origen}».</strong></p>
          <p style={{ marginTop: 12, fontWeight: 600 }}>¿Qué pasó?</p>
          <p style={{ marginTop: 2 }}>
            {t.detalle_error || "El archivo no se pudo leer. Puede que no sea un Excel válido o que esté dañado."}
          </p>
          <p style={{ marginTop: 12, fontWeight: 600 }}>¿Qué puedes hacer?</p>
          <p style={{ marginTop: 2 }}>
            Corrige el archivo según lo indicado y crea una nueva transformación. Esta quedará en el historial con estado «Error».
          </p>
          <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
            <button className="btn btn-primary btn-lg" onClick={() => navigate("/transformar")}>
              Intentar con otro archivo
            </button>
            <button className="btn btn-lg" onClick={() => navigate("/historial")}>Ir al historial</button>
          </div>
        </div>
      </div>
    );
  }

  if (generado || t.estado === "GENERADO") {
    return (
      <div style={{ maxWidth: 640 }}>
      {resultado && <ResultadoModal resultado={resultado} onAceptar={() => setResultado(null)} />}
        <div className="mapeo-header"><h1>Transformación realizada con éxito</h1></div>
        <div className="exito-caja">
          <i aria-hidden="true" className="ti ti-circle-check" />
          <h2>¡Tu documento está listo!</h2>
          <p>Se rellenó la plantilla con los datos de la licitación, respetando el formato original.</p>
          <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
            <button className="btn btn-primary btn-lg" onClick={descargar}>
              <i aria-hidden="true" className="ti ti-download" /> Descargar documento
            </button>
            <button className="btn btn-lg" onClick={() => navigate("/historial")}>
              Ir al historial
            </button>
          </div>
        </div>
      </div>
    );
  }

  const mapeos = mapeosLocal;
  const campos = plantilla?.campos ?? [];
  const hojas = preview?.hojas ?? [];
  const hoja = hojas[hojaActiva];

  // Advertencias antes de generar.
  const avisoIA = t.resultado_limpieza?.aviso_ia as string | undefined;
  const tablasOrigen = (t.resultado_limpieza?.hojas_itemizado as string[] | undefined) ?? [];
  const soloTablas = mapeos.length === 0 && tablasOrigen.length > 0;
  // Sin campos con dato y sin tablas que copiar, el documento saldría vacío.
  const ningunoAsignado = tablasOrigen.length === 0 && mapeos.length > 0 && !mapeos.some((m) => m.destino_campo);
  const camposSinDato = campos.filter((c) => !mapeos.some((m) => m.destino_campo === c.id)).length;
  // Valor de cada dato del origen (viene con la vista previa) para mostrarlo al elegir.
  const valorDe: Record<string, string> = Object.fromEntries(
    (preview?.datos_origen ?? []).map((d: { columna: string; valor: string }) => [d.columna, d.valor])
  );
  const nombreCampo: Record<string, string> = Object.fromEntries(campos.map((c) => [c.id, c.nombre]));

  // Campos agrupados por hoja, en el orden de las hojas del Excel de la plantilla.
  const ordenHojas = hojas.map((h: { nombre: string }) => h.nombre);
  const hojasMapeo: { nombre: string; campos: typeof campos }[] = [];
  campos.forEach((c) => {
    const nombre = c.hoja_destino || "General";
    let grupo = hojasMapeo.find((h) => h.nombre === nombre);
    if (!grupo) { grupo = { nombre, campos: [] }; hojasMapeo.push(grupo); }
    grupo.campos.push(c);
  });
  const posicion = (n: string) => (ordenHojas.indexOf(n) === -1 ? 999 : ordenHojas.indexOf(n));
  hojasMapeo.sort((a, b) => posicion(a.nombre) - posicion(b.nombre));
  const indiceMapeo = Math.min(hojaMapeo, Math.max(0, hojasMapeo.length - 1));
  const grupoMapeo = hojasMapeo[indiceMapeo];
  const conDato = (lista: typeof campos) => lista.filter((c) => mapeos.some((m) => m.destino_campo === c.id)).length;

  // Datos del origen ordenados alfabéticamente, para el desplegable.
  const datosOrdenados = [...mapeos].sort((a, b) => a.origen_columna.localeCompare(b.origen_columna, "es"));
  const obligatoriosFaltantes = campos.filter(
    (c) => c.obligatorio && !mapeos.some((m) => m.destino_campo === c.id)
  );

  return (
    <div style={{ maxWidth: 980 }}>
      <div className="mapeo-header">
        <h1>Revisar y generar</h1>
        <p>{t.nombre || t.nombre_origen} → {t.plantilla_nombre}. Revisa la vista previa, ajusta y genera.</p>
      </div>

      {resultado && <ResultadoModal resultado={resultado} onAceptar={() => setResultado(null)} />}
      {/* ───── LO QUE QUEDARÁ SIN LLENAR (antes de la vista previa) ───── */}
      {(preview?.avisos?.length ?? 0) > 0 && (
        <div className="pendientes-caja" role="status">
          <p className="pendientes-titulo">
            <i aria-hidden="true" className="ti ti-alert-triangle" />
            {generado ? "Revisa antes de descargar" : "Revisa antes de generar"}: {preview.avisos.length === 1
              ? "1 dato quedará sin llenar" : `${preview.avisos.length} datos quedarán sin llenar`} en el documento
          </p>
          <ul>
            {preview.avisos.map((a: string, i: number) => <li key={i}>{a}</li>)}
          </ul>
          <p className="pendientes-pie">
            Puedes generar igual, pero esas casillas quedarán vacías. Los campos se corrigen en
            Plantillas → Campos; los datos, en el mapeo de abajo.
          </p>
        </div>
      )}

      {/* ───── VISTA PREVIA POR HOJAS (arriba) ───── */}
      {hojas.length > 0 && (
        <div className="mapeo-panel" style={{ marginBottom: 14 }}>
          <div className="preview-nav">
            <button className="preview-flecha" disabled={hojaActiva === 0} aria-label="Hoja anterior"
              onClick={() => setHojaActiva((h) => Math.max(0, h - 1))}>
              <i aria-hidden="true" className="ti ti-chevron-left" />
            </button>
            <div className="preview-titulo">
              <span className="preview-hoja-nombre">{hoja?.nombre}</span>
              <span className="preview-hoja-contador">
                Hoja {hojaActiva + 1} de {hojas.length}
                {hoja?.tipo === "itemizado" && <span className="preview-badge-item">tabla</span>}
              </span>
            </div>
            <button className="preview-flecha" disabled={hojaActiva >= hojas.length - 1} aria-label="Hoja siguiente"
              onClick={() => setHojaActiva((h) => Math.min(hojas.length - 1, h + 1))}>
              <i aria-hidden="true" className="ti ti-chevron-right" />
            </button>
          </div>

          {/* Campos de la hoja (también en hojas con tabla: casillas sobre la tabla) */}
          {hoja?.campos?.length > 0 && (
            <table className="preview-tabla">
              <thead><tr><th>Campo</th><th>Valor final</th><th>IVA</th><th><span className="solo-lector">Limpieza con IA</span></th></tr></thead>
              <tbody>
                {hoja.campos.map((f: any, i: number) => (
                  <tr key={i}>
                    <td>{f.campo}</td>
                    <td style={{ fontWeight: f.valor_final ? 500 : 400,
                                 color: f.valor_final ? "var(--text)" : "var(--text-3)" }}>
                      {f.valor_final || "(vacío)"}
                    </td>
                    <td>
                      {f.es_moneda && (
                        <select className="iva-select" value={f.ajuste_iva || "NINGUNO"} aria-label={`IVA de «${f.campo}»`}
                          onChange={(e) => cambiarIVA(f.campo, e.target.value)}>
                          {IVA_OPCIONES.map((o) => <option key={o.v} value={o.v}>{o.t}</option>)}
                        </select>
                      )}
                    </td>
                    <td>{f.limpiado_ia && <span title="Limpiado con IA" role="img" aria-label="Limpiado con IA" style={{ color: "var(--ai-600,#5B4E8C)" }}><i aria-hidden="true" className="ti ti-sparkles" /></span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {hoja?.tipo === "itemizado" && hoja.tabla.totales_faltantes > 0 && (
            <div className={`totales-banda ${hoja.tabla.totales_calculados ? "activo" : ""}`}>
              <i aria-hidden="true" className={hoja.tabla.totales_calculados ? "ti ti-calculator" : "ti ti-alert-triangle"} />
              <span>
                {hoja.tabla.totales_calculados
                  ? <>Se calcularon <strong>{hoja.tabla.totales_faltantes}</strong> total(es) como precio × cantidad (marcados en azul).</>
                  : <>Hay <strong>{hoja.tabla.totales_faltantes}</strong> fila(s) sin total, pero con precio y cantidad. Puedes calcularlo.</>}
              </span>
              <button className="btn" disabled={calculandoTotales}
                onClick={() => alternarTotales(!hoja.tabla.totales_calculados, hoja.tabla.totales_faltantes)}>
                {calculandoTotales ? "Calculando…" : hoja.tabla.totales_calculados
                  ? <><i aria-hidden="true" className="ti ti-arrow-back-up" /> Quitar cálculo</>
                  : <><i aria-hidden="true" className="ti ti-calculator" /> Calcular totales (precio × cantidad)</>}
              </button>
            </div>
          )}

          {hoja?.tipo === "itemizado" && hoja.tabla.filas.length > 15 && (
            <div className="preview-filas-total">
              {hoja.tabla.filas.length.toLocaleString("es-CL")} filas · baja dentro de la tabla para verlas todas
            </div>
          )}
          {hoja?.tipo === "itemizado" && (
            <TablaItemizado key={hoja.nombre} hoja={hoja} guardandoColumna={guardandoColumna}
              onCambiarColumna={cambiarColumna} />
          )}
        </div>
      )}

      {/* ───── ADVERTENCIAS ───── */}
      {avisoIA && (
        <div className="banda banda-aviso">
          <i aria-hidden="true" className="ti ti-alert-triangle" />
          <div><strong>Mapeo hecho sin IA</strong>{avisoIA}</div>
        </div>
      )}
      {ningunoAsignado ? (
        <div className="banda banda-error">
          <i aria-hidden="true" className="ti ti-alert-circle" />
          <div>
            <strong>No se puede generar todavía</strong>
            Ningún campo tiene un dato asignado, así que el documento saldría vacío. Abajo, en «Mapeo propuesto»,
            elige qué dato del Excel va en cada campo.
          </div>
        </div>
      ) : obligatoriosFaltantes.length > 0 && (
        <div className="banda banda-aviso">
          <i aria-hidden="true" className="ti ti-alert-triangle" />
          <div>
            <strong>Faltan campos obligatorios</strong>
            Ningún dato está asignado a: {obligatoriosFaltantes.map((c) => c.nombre).join(", ")}. Quedarán vacíos en el
            documento. Asígnalos abajo si el dato existe en el origen.
          </div>
        </div>
      )}

      {/* ───── BOTONES (entre vista previa y mapeo) ───── */}
      <div className="mapeo-acciones" style={{ marginBottom: 14 }}>
        <span className="mapeo-acciones-info">
          <i aria-hidden="true" className="ti ti-info-circle" style={{ verticalAlign: "-2px" }} /> {campos.length} campos
          {camposSinDato > 0 && !ningunoAsignado && <> · {camposSinDato} sin dato (quedarán vacíos)</>}.
        </span>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn btn-lg" onClick={() => navigate("/historial")}>Volver</button>
          <button className="btn btn-lg" onClick={limpiarConIA} disabled={limpiando}
            style={{ borderColor: "var(--ai-600, #5B4E8C)", color: "var(--ai-600, #5B4E8C)" }}>
            {limpiando ? "Limpiando…" : <><i aria-hidden="true" className="ti ti-sparkles" /> Limpiar con IA</>}
          </button>
          <button className="btn btn-primary btn-lg" onClick={generar}
            disabled={generando || (mapeos.length === 0 && !soloTablas) || ningunoAsignado}
            title={ningunoAsignado ? "Asigna un dato a al menos un campo para poder generar" : undefined}>
            {generando ? "Generando…" : <><i aria-hidden="true" className="ti ti-file-export" /> Generar documento</>}
          </button>
        </div>
      </div>

      {/* ───── MAPEO (abajo) ───── */}
      <div className="mapeo-panel">
        <div className="mapeo-panel-head">
          <div className="titulo">
            <span className="mapeo-ia-icon"><i aria-hidden="true" className="ti ti-brain" /></span>
            <div>
              <h2>Mapeo propuesto</h2>
              <p>Elige qué dato del Excel va en cada campo de la plantilla. Se guarda al instante.</p>
            </div>
          </div>
          <span className="privacy-tag"><i aria-hidden="true" className="ti ti-lock" /> Montos ocultos a la IA</span>
        </div>

        {mapeos.length === 0 ? (
          <div style={{ padding: 32, textAlign: "center", color: "var(--text-3)" }}>
            {soloTablas ? (
              <>
                <i aria-hidden="true" className="ti ti-table" style={{ fontSize: 26, display: "block", marginBottom: 6 }} />
                Esta licitación solo trae tablas ({tablasOrigen.join(", ")}), así que no hay datos sueltos que mapear.
                Las filas se copiarán a las hojas de tabla de la plantilla: revisa la vista previa y genera.
              </>
            ) : (
              "No se encontraron datos para mapear en el archivo de origen. Revisa que el Excel tenga encabezados y valores, y crea una nueva transformación."
            )}
          </div>
        ) : (
          <>
            {hojasMapeo.length > 1 && (
              <div className="preview-nav mapeo-nav">
                <button className="preview-flecha" disabled={indiceMapeo === 0} title="Hoja anterior" aria-label="Hoja anterior"
                  onClick={() => setHojaMapeo(indiceMapeo - 1)}>
                  <i aria-hidden="true" className="ti ti-chevron-left" />
                </button>
                <div className="preview-titulo">
                  <span className="preview-hoja-nombre">{grupoMapeo?.nombre}</span>
                  <span className="preview-hoja-contador">
                    Hoja {indiceMapeo + 1} de {hojasMapeo.length}
                    <span className={`mapeo-progreso ${grupoMapeo && conDato(grupoMapeo.campos) === grupoMapeo.campos.length ? "completo" : ""}`}>
                      {grupoMapeo ? conDato(grupoMapeo.campos) : 0} de {grupoMapeo?.campos.length ?? 0} con dato
                    </span>
                  </span>
                </div>
                <button className="preview-flecha" disabled={indiceMapeo >= hojasMapeo.length - 1} title="Hoja siguiente" aria-label="Hoja siguiente"
                  onClick={() => setHojaMapeo(indiceMapeo + 1)}>
                  <i aria-hidden="true" className="ti ti-chevron-right" />
                </button>
              </div>
            )}
            <div className="mapeo-fila mapeo-fila-head">
              <span>Campo de la plantilla</span><span /><span>Dato del Excel</span><span>Confianza</span>
            </div>
            {(grupoMapeo?.campos ?? []).map((c) => {
              const m = mapeos.find((x) => x.destino_campo === c.id);
              const clase = !m ? "" : m.confianza >= 85 ? "alta" : m.confianza >= 60 ? "media" : "baja";
              return (
                <div className="mapeo-fila" key={c.id}>
                  <span className="mapeo-origen mapeo-campo">
                    {c.nombre}
                    {c.obligatorio && <span className="mapeo-oblig" title="Campo obligatorio">*</span>}
                  </span>
                  <span className="mapeo-flecha"><i aria-hidden="true" className="ti ti-arrow-left" /></span>
                  <div className="mapeo-dato">
                    <select
                      className={`mapeo-select ${!m ? "sin-asignar" : ""}`}
                      value={m?.origen_columna ?? ""}
                      disabled={guardandoId === c.id}
                      aria-label={`Dato del Excel para «${c.nombre}»`}
                      onChange={(e) => cambiarDato(c.id, c.nombre, e.target.value)}
                    >
                      <option value="">— Sin dato —</option>
                      {m && (
                        <optgroup label="Dato actual">
                          <option value={m.origen_columna}>{opcionDato(m.origen_columna, valorDe)}</option>
                        </optgroup>
                      )}
                      <optgroup label="Disponibles">
                        {datosOrdenados.filter((d) => !d.destino_campo).map((d) => (
                          <option key={d.id} value={d.origen_columna}>{opcionDato(d.origen_columna, valorDe)}</option>
                        ))}
                      </optgroup>
                      <optgroup label="Ya usados en otro campo (se moverán aquí)">
                        {datosOrdenados.filter((d) => d.destino_campo && d.destino_campo !== c.id).map((d) => (
                          <option key={d.id} value={d.origen_columna}>
                            {opcionDato(d.origen_columna, valorDe)} → {nombreCampo[d.destino_campo] ?? "otro campo"}
                          </option>
                        ))}
                      </optgroup>
                    </select>
                    {m && (
                      <span className="mapeo-valor" title={valorDe[m.origen_columna] || ""}>
                        Valor: <strong>{valorDe[m.origen_columna] ? recortarTexto(valorDe[m.origen_columna], 60) : "(vacío)"}</strong>
                      </span>
                    )}
                  </div>
                  <span className={`mapeo-conf ${clase}`}>
                    {guardandoId === c.id ? (
                      <span role="status" aria-label={`Guardando «${c.nombre}»…`}>
                        <i aria-hidden="true" className="ti ti-loader-2" style={{ color: "var(--brand-500)" }} />
                      </span>
                    ) : !m ? (
                      <span className="mapeo-conf-num" style={{ color: "var(--text-3)" }}>—</span>
                    ) : m.ajustado_por_humano ? (
                      <span className="mapeo-manual" title="Elegido por ti">Manual</span>
                    ) : (
                      <>
                        <span className="mapeo-conf-bar"><span className="mapeo-conf-fill" style={{ width: `${m.confianza}%` }} /></span>
                        <span className="mapeo-conf-num">{m.confianza}%</span>
                      </>
                    )}
                  </span>
                </div>
              );
            })}
          </>
        )}
      </div>
    </div>
  );
}

// Tiempo mínimo que se ve cada paso, para que la animación se lea aunque el
// worker sea más rápido que el sondeo de 2 s.
const MS_POR_PASO = 900;

function ProcesandoIA({ estado, nombre, onTerminar }: {
  estado: string; nombre: string; onTerminar: () => void;
}) {
  // Hasta qué paso llegó realmente el worker (índice del paso en curso):
  //   BORRADOR        → leyendo/limpiando el Excel (pasos 0 y 1)
  //   LIMPIEZA        → limpieza lista, la IA está trabajando (paso 2)
  //   MAPEO_PROPUESTO → la IA respondió, se guarda el mapeo (paso 3)
  //   EN_REVISION…    → todo listo (4 = todos hechos)
  const objetivo =
    estado === "BORRADOR" ? 1 :
      estado === "LIMPIEZA" ? 2 :
        estado === "MAPEO_PROPUESTO" ? 3 : 4;

  // El paso mostrado avanza de a uno hacia el objetivo, con un mínimo por paso.
  const [pasoActual, setPasoActual] = useState(0);
  // En ref para que los re-render del padre (sondeo) no reinicien el temporizador.
  const onTerminarRef = useRef(onTerminar);
  onTerminarRef.current = onTerminar;
  useEffect(() => {
    if (pasoActual < objetivo) {
      const timer = setTimeout(() => setPasoActual((p) => p + 1), MS_POR_PASO);
      return () => clearTimeout(timer);
    }
    if (pasoActual >= 4) {
      const timer = setTimeout(() => onTerminarRef.current(), 600);   // un respiro con todo en verde
      return () => clearTimeout(timer);
    }
  }, [pasoActual, objetivo]);

  const pasos = [
    { icono: "ti ti-file-search", titulo: "Leyendo el documento", desc: "Extrayendo las columnas y datos del Excel" },
    { icono: "ti ti-wash", titulo: "Limpiando los datos", desc: "Duplicados, unidades y formatos numéricos" },
    { icono: "ti ti-brain", titulo: "La IA está trabajando", desc: "Gemini analiza y propone el mapeo de campos", ia: true },
    { icono: "ti ti-checks", titulo: "Preparando la revisión", desc: "Dejando todo listo para que revises" },
  ];
  return (
    <div style={{ maxWidth: 620 }}>
      <div className="mapeo-header"><h1>Procesando tu licitación</h1><p>{nombre}</p></div>
      <div className="ia-proceso">
        <div className="ia-proceso-orbe"><i aria-hidden="true" className="ti ti-sparkles" /></div>
        <div className="ia-pasos">
          {pasos.map((p, i) => {
            const hecho = i < pasoActual; const activo = i === pasoActual;
            return (
              <div key={i} className={`ia-paso ${hecho ? "hecho" : ""} ${activo ? "activo" : ""}`}>
                <span className="ia-paso-icono">{hecho ? <i aria-hidden="true" className="ti ti-check" /> : <i aria-hidden="true" className={p.icono} />}</span>
                <div className="ia-paso-texto">
                  <p className="ia-paso-titulo">{p.titulo}{p.ia && activo && <span className="ia-badge">IA</span>}</p>
                  <p className="ia-paso-desc">{p.desc}</p>
                </div>
                {activo && <span className="ia-paso-spinner"><i aria-hidden="true" className="ti ti-loader-2" /></span>}
              </div>
            );
          })}
        </div>
        {/* El lector de pantalla anuncia cada paso al avanzar. */}
        <p className="solo-lector" role="status">
          {pasoActual < pasos.length
            ? `Paso ${pasoActual + 1} de ${pasos.length}: ${pasos[pasoActual].titulo}`
            : "Procesamiento terminado"}
        </p>
        <p className="ia-nota"><i aria-hidden="true" className="ti ti-info-circle" /> Puedes ir a otras secciones; la transformación seguirá en tu historial.</p>
      </div>
    </div>
  );
}
// Tablas con más filas que esto dibujan solo las que se ven (más un margen),
// para que miles de filas no traben la pantalla.
const FILAS_SIN_VIRTUALIZAR = 100;
const FILAS_MARGEN = 10;
const FILAS_VISIBLES = 15;      // alto de .preview-scroll

/**
 * Tabla de una hoja itemizada, con el selector de columna del origen en el
 * encabezado. Sin `onCambiarColumna` es de solo lectura (vista previa del historial).
 */
export function TablaItemizado({ hoja, guardandoColumna = null, onCambiarColumna }: {
  hoja: any; guardandoColumna?: string | null;
  onCambiarColumna?: (hoja: string, destino: string, origen: string) => void;
}) {
  const filas: string[][] = hoja.tabla.filas;
  // Celdas marcadas como "fila,columna", para no recorrer las listas en cada celda.
  const calculadas = useMemo(
    () => new Set((hoja.tabla.celdas_calculadas ?? []).map(([f, c]: number[]) => `${f},${c}`)),
    [hoja.tabla.celdas_calculadas]);
  const porIA = useMemo(
    () => new Set((hoja.tabla.celdas_ia ?? []).map(([f, c]: number[]) => `${f},${c}`)),
    [hoja.tabla.celdas_ia]);

  const virtual = filas.length > FILAS_SIN_VIRTUALIZAR;
  const [scrollTop, setScrollTop] = useState(0);
  // Alto real de una fila: se mide la primera dibujada (depende de la fuente).
  const [altoFila, setAltoFila] = useState(28);
  const cuerpo = useRef<HTMLTableSectionElement>(null);
  useLayoutEffect(() => {
    const fila = cuerpo.current?.querySelector<HTMLElement>("tr[data-fila]");
    if (virtual && fila && fila.offsetHeight) setAltoFila(fila.offsetHeight);
  }, [virtual]);

  const desde = virtual ? Math.max(0, Math.floor(scrollTop / altoFila) - FILAS_MARGEN) : 0;
  const hasta = virtual
    ? Math.min(filas.length, Math.ceil(scrollTop / altoFila) + FILAS_VISIBLES + FILAS_MARGEN)
    : filas.length;

  return (
    // Alto de ~15 filas con su propia barra: con miles de filas la página no se alarga.
    <div className="preview-scroll"
      onScroll={virtual ? (e) => setScrollTop(e.currentTarget.scrollTop) : undefined}>
      <table className="preview-tabla preview-itemizado" aria-rowcount={filas.length + 1}>
        <thead>
          <tr aria-rowindex={1}>{hoja.tabla.columnas.map((c: string, i: number) => {
            // De qué columna del origen sale esta: se puede cambiar aquí mismo.
            const p = hoja.tabla.parejas?.[i] as ParejaColumna | undefined;
            return (
              <th key={i}>
                {c}
                {p && onCambiarColumna && (
                  <div className={`columna-origen columna-origen-${p.origen ? p.fuente : "vacia"}`}
                    title={FUENTE_COLUMNA[p.origen ? p.fuente : "vacia"] + (p.motivo ? `: ${p.motivo}` : "")}>
                    <span aria-hidden="true">←</span>
                    <select value={p.origen ?? ""} disabled={guardandoColumna === c}
                      aria-label={`Columna del origen para «${c}»`}
                      onChange={(e) => onCambiarColumna(hoja.nombre, c, e.target.value)}>
                      <option value="">(vacía)</option>
                      {(hoja.tabla.columnas_origen as string[]).map((o) => (
                        <option key={o} value={o}>{o}</option>
                      ))}
                    </select>
                    {p.fuente === "ia" && p.origen && <i aria-hidden="true" className="ti ti-sparkles" />}
                  </div>
                )}
              </th>
            );
          })}</tr>
        </thead>
        <tbody ref={cuerpo}>
          {desde > 0 && <tr aria-hidden="true" style={{ height: desde * altoFila }} />}
          {filas.slice(desde, hasta).map((fila, k) => {
            const i = desde + k;
            return (
              <tr key={i} data-fila aria-rowindex={i + 2}>
                {fila.map((celda, j) => {
                  const calculada = calculadas.has(`${i},${j}`);
                  const ia = porIA.has(`${i},${j}`);
                  return (
                    <td key={j} className={calculada ? "celda-calculada" : ia ? "celda-ia" : ""}
                      title={calculada ? "Calculado: precio × cantidad" : ia ? "Limpiado con IA" : undefined}>
                      {celda || "—"}
                      {ia && <i role="img" aria-label="Limpiado con IA" className="ti ti-sparkles celda-ia-icono" />}
                    </td>
                  );
                })}
              </tr>
            );
          })}
          {hasta < filas.length && <tr aria-hidden="true" style={{ height: (filas.length - hasta) * altoFila }} />}
        </tbody>
      </table>
    </div>
  );
}

function recortarTexto(texto: string, max: number) {
  return texto.length > max ? `${texto.slice(0, max).trimEnd()}…` : texto;
}

/** Texto de una opción del desplegable: «Columna — valor». */
function opcionDato(columna: string, valorDe: Record<string, string>) {
  const valor = valorDe[columna];
  return `${recortarTexto(columna, 30)}  —  ${valor ? recortarTexto(valor, 30) : "(vacío)"}`;
}
