import { useState } from "react";
import { api, ApiError } from "../api/client";
import type { ScanRun } from "../api/types";
import { relativeTime } from "../utils/format";

/** Lanza una búsqueda manual y explica el resultado (incluida la espera mínima entre consultas). */
export function SearchButton({ onDone, compact = false }: { onDone?: (run: ScanRun) => void; compact?: boolean }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "warning" | "error"; text: string }>();

  const run = async () => {
    setBusy(true);
    setMessage(undefined);
    try {
      const result = await api.runSearch();
      const text = result.status === "empty"
        ? "No hay fuentes habilitadas o no se encontraron ofertas."
        : `${result.fetched} ofertas leídas, ${result.added} nuevas.`;
      setMessage({ tone: result.errors.length ? "warning" : "success",
                   text: result.errors.length ? `${text} Fallos: ${result.errors.join(" · ")}` : text });
      onDone?.(result);
    } catch (e) {
      const err = e as ApiError;
      let text = err.message;
      if (err.status === 429) {
        const next = (err.detail as { next_allowed_at?: string })?.next_allowed_at;
        text = `Las fuentes se consultaron hace poco. Podrás buscar de nuevo ${relativeTime(next)}.`;
      }
      setMessage({ tone: err.status === 429 ? "warning" : "error", text });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={compact ? "search-btn compact" : "search-btn"}>
      <button className="btn btn-primary" onClick={run} disabled={busy} aria-busy={busy}>
        {busy ? <><span className="spinner spinner-light" aria-hidden="true" /> Consultando fuentes…</> : "Buscar nuevas ofertas"}
      </button>
      {message && <p className={`search-msg text-${message.tone}`} role="status">{message.text}</p>}
    </div>
  );
}
