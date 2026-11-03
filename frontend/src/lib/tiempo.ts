/** Duración en palabras cortas: 45 → «45 s», 125 → «2 min 05 s», 3720 → «1 h 02 min». */
export function formatearDuracion(segundos: number | null | undefined): string {
  if (segundos == null) return "—";
  const s = Math.max(0, Math.round(segundos));
  if (s < 60) return `${s} s`;
  const min = Math.floor(s / 60);
  if (min < 60) return `${min} min ${String(s % 60).padStart(2, "0")} s`;
  return `${Math.floor(min / 60)} h ${String(min % 60).padStart(2, "0")} min`;
}
