import { useState } from "react";
import { api } from "../api/client";
import type { Job, Status, Tracking as TrackingData } from "../api/types";
import { JobCard } from "../components/JobCard";
import { AsyncView, Card, Empty, PageHeader } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { formatDate } from "../utils/format";

export function Tracking() {
  const state = useAsync(api.tracking);
  const [filter, setFilter] = useState<Status | "Todas">("Todas");

  const replace = (data: TrackingData, job: Job) => {
    const before = data.items.find((j) => j.id === job.id)?.status;
    const counts = { ...data.counts };
    if (before && before !== job.status) {
      counts[before] -= 1;
      counts[job.status] += 1;
    }
    state.setData({ ...data, counts, items: data.items.map((j) => (j.id === job.id ? job : j)) });
  };

  return (
    <>
      <PageHeader title="Seguimiento" subtitle="Estado, notas e historial de cada postulación. Las ofertas en «Nueva» están en Explorar." />
      <AsyncView state={state} label="Cargando seguimiento…">
        {(d) => {
          const tracked = d.statuses.filter((s) => s !== "Nueva");
          const items = filter === "Todas" ? d.items : d.items.filter((j) => j.status === filter);
          return (
            <>
              <div className="pipeline" role="tablist" aria-label="Filtrar por estado">
                <button role="tab" aria-selected={filter === "Todas"} className={`pipe ${filter === "Todas" ? "active" : ""}`}
                        onClick={() => setFilter("Todas")}>
                  <span>En seguimiento</span><strong>{tracked.reduce((n, s) => n + d.counts[s], 0)}</strong>
                </button>
                {tracked.map((s) => (
                  <button key={s} role="tab" aria-selected={filter === s}
                          className={`pipe pipe-${s.toLowerCase()} ${filter === s ? "active" : ""}`}
                          onClick={() => setFilter(s)}>
                    <span>{s}</span><strong>{d.counts[s]}</strong>
                  </button>
                ))}
              </div>
              <div className="grid-2">
                <div>
                  {items.length === 0 ? (
                    <Empty title="Nada por aquí todavía">
                      Cambia el estado de una oferta en «Explorar ofertas» para empezar a seguirla.
                    </Empty>
                  ) : (
                    <div className="job-list">
                      {items.map((j) => <JobCard key={j.id} job={j} onChange={(job) => replace(d, job)} />)}
                    </div>
                  )}
                </div>
                <Card title="Historial reciente">
                  {d.recent_changes.length === 0 ? <p className="muted">Sin cambios registrados.</p> : (
                    <ul className="timeline">
                      {d.recent_changes.map((h) => (
                        <li key={h.id}>
                          <span>{h.title ?? h.job_id}{h.company ? ` · ${h.company}` : ""}</span>
                          <span className="muted small">{h.old_status} → {h.new_status} · {formatDate(h.changed_at)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="muted small">Los cambios hechos desde la interfaz Streamlit anterior no quedan en el historial.</p>
                </Card>
              </div>
            </>
          );
        }}
      </AsyncView>
    </>
  );
}
