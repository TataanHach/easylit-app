/**
 * Muestra el código de invitación de una persona y un mensaje listo para
 * enviarle (WhatsApp, correo…). EasyLit no envía correos: lo hace el gerente.
 */
import { useEffect } from "react";
import { useAvisos } from "@/components/ui/Avisos";
import { fechaVencimiento, mensajeInvitacion, type CodigoInvitacion } from "./equipoService";

interface Props {
  nombre: string;
  organizacion: string | null;
  inv: CodigoInvitacion;
  onCerrar: () => void;
}

export default function CodigoModal({ nombre, organizacion, inv, onCerrar }: Props) {
  const avisos = useAvisos();
  const mensaje = mensajeInvitacion(nombre, organizacion, inv);

  async function copiar(texto: string, que: string) {
    try {
      await navigator.clipboard.writeText(texto);
      avisos.exito(`${que} copiado`, `Pégalo en WhatsApp o en un correo para ${nombre}.`);
    } catch {
      avisos.error("No se pudo copiar", "Selecciona el texto del recuadro y cópialo con Ctrl+C.");
    }
  }

  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => { if (e.key === "Escape") onCerrar(); };
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [onCerrar]);

  return (
    <div className="modal-overlay">
      <div className="modal eq-modal-ancho" role="dialog" aria-modal="true" aria-labelledby="codigo-titulo">
        <div className="modal-head">
          <h2 id="codigo-titulo">Código de invitación</h2>
          <button className="modal-close" onClick={onCerrar} aria-label="Cerrar"><i aria-hidden="true" className="ti ti-x" /></button>
        </div>
        <div className="modal-body">
          <p className="eq-codigo-intro">
            Envíale este mensaje a <strong>{nombre}</strong>. Con el enlace crea su contraseña y queda
            listo para entrar. El código sirve una sola vez y vence el <strong>{fechaVencimiento(inv.expira)}</strong>.
          </p>
          <div className="eq-mensaje">{mensaje}</div>
          <div className="eq-codigo-solo">
            <span>Solo el código</span>
            <code>{inv.codigo}</code>
          </div>
        </div>
        <div className="modal-foot">
          <button type="button" className="btn" onClick={() => copiar(inv.codigo, "Código")}>
            <i aria-hidden="true" className="ti ti-key" /> Copiar código
          </button>
          <button type="button" className="btn btn-primary" onClick={() => copiar(mensaje, "Mensaje")}>
            <i aria-hidden="true" className="ti ti-copy" /> Copiar mensaje
          </button>
        </div>
      </div>
    </div>
  );
}
