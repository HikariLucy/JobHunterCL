import { useState } from "react";
import { api } from "../api/client";
import { STATUSES, type HistoryEntry, type Job, type Status } from "../api/types";
import { formatDate, relativeTime } from "../utils/format";
import { ErrorBox, ScoreBadge, StatusBadge } from "./ui";

/** Tarjeta expandible de oferta: explicación del puntaje, estado, notas e historial. */
export function JobCard({ job, onChange, defaultOpen = false }: {
  job: Job;
  onChange: (job: Job) => void;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [notes, setNotes] = useState(job.notes);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  const [saved, setSaved] = useState(false);
  const [history, setHistory] = useState<HistoryEntry[]>();

  const patch = async (body: { status?: Status; notes?: string }) => {
    setSaving(true);
    setError(undefined);
    setSaved(false);
    try {
      const updated = await api.updateJob(job.id, body);
      onChange(updated);
      setNotes(updated.notes);
      setSaved(body.notes !== undefined);
      if (history) setHistory(await api.history(job.id));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && !history) {
      try {
        setHistory(await api.history(job.id));
      } catch {
        setHistory([]);
      }
    }
  };

  return (
    <article className={`job ${open ? "job-open" : ""}`}>
      <button className="job-summary" onClick={toggle} aria-expanded={open}>
        <ScoreBadge score={job.score} />
        <div className="job-main">
          <strong className="job-title">{job.title}</strong>
          <span className="muted">
            {job.company} · {job.location || "Ubicación no indicada"} · {job.source}
          </span>
        </div>
        <StatusBadge status={job.status} />
      </button>

      {open && (
        <div className="job-body">
          <div className="job-explain">
            {job.reasons.map((r) => <span key={r} className="tag tag-good">✓ {r}</span>)}
            {job.warnings.map((w) => <span key={w} className="tag tag-warn">! {w}</span>)}
          </div>
          <p className="job-desc">
            {(job.description || "Sin descripción en la fuente; revisa la oferta original.").slice(0, 3500)}
          </p>
          <div className="job-meta muted">
            Vista por primera vez {relativeTime(job.first_seen)} · Publicada: {job.posted_at ? formatDate(job.posted_at) : "sin fecha"}
          </div>

          <div className="job-actions">
            <a className="btn btn-primary" href={job.url} target="_blank" rel="noopener noreferrer">
              Abrir oferta original ↗
            </a>
            <label className="inline-field">
              Estado
              <select value={job.status} disabled={saving} onChange={(e) => patch({ status: e.target.value as Status })}>
                {STATUSES.map((s) => <option key={s}>{s}</option>)}
              </select>
            </label>
          </div>

          <div className="field">
            <label htmlFor={`notes-${job.id}`}>Notas privadas</label>
            <textarea id={`notes-${job.id}`} rows={3} maxLength={5000} value={notes}
                      onChange={(e) => { setNotes(e.target.value); setSaved(false); }} />
            <div className="row">
              <button className="btn btn-small" disabled={saving || notes === job.notes} onClick={() => patch({ notes })}>
                {saving ? "Guardando…" : "Guardar nota"}
              </button>
              {saved && <span className="muted">Nota guardada</span>}
            </div>
          </div>
          {error && <ErrorBox error={error} />}

          {history && history.length > 0 && (
            <div className="history">
              <h3>Historial</h3>
              <ol>
                {history.map((h) => (
                  <li key={h.id}>
                    <span className="muted">{formatDate(h.changed_at)}</span> {h.old_status ?? "—"} → <strong>{h.new_status}</strong>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}
    </article>
  );
}
