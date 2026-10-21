const dateFmt = new Intl.DateTimeFormat("es-CL", { dateStyle: "medium", timeStyle: "short" });

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : dateFmt.format(d);
}

/** "hace 5 min", "en 2 h"… relativo a `now`. */
export function relativeTime(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const diffMin = Math.round((d.getTime() - now.getTime()) / 60000);
  const abs = Math.abs(diffMin);
  let text: string;
  if (abs < 1) return "ahora";
  if (abs < 60) text = `${abs} min`;
  else if (abs < 60 * 48) text = `${Math.round(abs / 60)} h`;
  else text = `${Math.round(abs / 1440)} días`;
  return diffMin < 0 ? `hace ${text}` : `en ${text}`;
}

export function scoreLevel(score: number): "high" | "mid" | "low" {
  if (score >= 60) return "high";
  if (score >= 30) return "mid";
  return "low";
}

export function minutesLabel(minutes: number): string {
  if (minutes <= 0) return "Desactivada";
  if (minutes < 60) return `Cada ${minutes} min`;
  if (minutes % 1440 === 0) return minutes === 1440 ? "Una vez al día" : `Cada ${minutes / 1440} días`;
  return `Cada ${+(minutes / 60).toFixed(1)} h`;
}
