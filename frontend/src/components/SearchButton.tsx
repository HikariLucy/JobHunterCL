import { useCallback, useEffect, useId, useState } from "react";
import { api, ApiError } from "../api/client";
import type { ScanRun } from "../api/types";
import { relativeTime } from "../utils/format";

type Tone = "success" | "warning" | "error";

const isFuture = (iso: string | null, now: number) => !!iso && Date.parse(iso) > now;

/**
 * Lanza una búsqueda manual y explica el resultado.
 * Consulta la espera mínima antes de habilitarse, para no provocar un 429 que el
 * panel ya puede prever; el 429 de la API queda como respaldo (otra pestaña, programador).
 */
export function SearchButton({ onDone, compact = false }: { onDone?: (run: ScanRun) => void; compact?: boolean }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: Tone; text: string }>();
  const [nextAllowed, setNextAllowed] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const hintId = useId();

  const refreshStatus = useCallback(async (): Promise<string | null> => {
    try {
      const next = (await api.searchStatus()).next_allowed_at;
      setNextAllowed(next);
      setNow(Date.now());
      return next;
    } catch {
      return null; // sin estado el botón queda habilitado y la API decide
    }
  }, []);

  useEffect(() => { void refreshStatus(); }, [refreshStatus]);

  const waiting = isFuture(nextAllowed, now);
  useEffect(() => {
    if (!waiting) return;
    const timer = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(timer);
  }, [waiting]);

  const run = async () => {
    setBusy(true);
    setMessage(undefined);
    try {
      const result = await api.runSearch();
      const next = await refreshStatus();
      const failures = result.errors.length ? ` Fallos: ${result.errors.join(" · ")}` : "";
      if (result.status === "error") {
        const retry = isFuture(next, Date.now())
          ? `Podrás reintentar ${relativeTime(next)}.`
          : "Revisa tu conexión a internet; puedes reintentar ahora.";
        setMessage({ tone: "error", text: `No se pudo consultar ninguna fuente.${failures} ${retry}` });
      } else if (result.status === "empty") {
        setMessage({ tone: "success", text: "No hay fuentes habilitadas o no se encontraron ofertas." });
      } else {
        setMessage({ tone: failures ? "warning" : "success",
                     text: `${result.fetched} ofertas leídas, ${result.added} nuevas.${failures}` });
      }
      onDone?.(result);
    } catch (e) {
      const err = e as ApiError;
      let text = err.message;
      if (err.status === 429) {
        const next = (err.detail as { next_allowed_at?: string })?.next_allowed_at ?? null;
        setNextAllowed(next);
        setNow(Date.now());
        text = `Las fuentes se consultaron hace poco. Podrás buscar de nuevo ${relativeTime(next)}.`;
      }
      setMessage({ tone: err.status === 429 ? "warning" : "error", text });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={compact ? "search-btn compact" : "search-btn"}>
      <button className="btn btn-primary" onClick={run} disabled={busy || waiting} aria-busy={busy}
              aria-describedby={waiting && !message ? hintId : undefined}>
        {busy ? <><span className="spinner spinner-light" aria-hidden="true" /> Consultando fuentes…</> : "Buscar nuevas ofertas"}
      </button>
      {message && <p className={`search-msg text-${message.tone}`} role="status">{message.text}</p>}
      {waiting && !message && (
        <p id={hintId} className="search-msg muted">
          Disponible {relativeTime(nextAllowed, new Date(now))}: espera mínima entre consultas para respetar las fuentes.
        </p>
      )}
    </div>
  );
}
