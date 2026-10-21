import { Link } from "react-router-dom";
import { api } from "../api/client";
import { STATUSES, type Dashboard as DashboardData, type Job } from "../api/types";
import { JobCard } from "../components/JobCard";
import { SearchButton } from "../components/SearchButton";
import { AsyncView, Card, Empty, PageHeader, StatCard, StatusBadge } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { formatDate, minutesLabel, relativeTime } from "../utils/format";

export function Dashboard() {
  const state = useAsync(api.dashboard);

  const replaceJob = (data: DashboardData, job: Job) =>
    state.setData({ ...data, top_matches: data.top_matches.map((j) => (j.id === job.id ? job : j)) });

  return (
    <>
      <PageHeader title="Dashboard" subtitle="Resumen de oportunidades y postulaciones guardadas en este equipo."
                  actions={<SearchButton compact onDone={() => void state.reload()} />} />
      <AsyncView state={state} label="Cargando resumen…">
        {(d) => (
          <>
            <div className="stats">
              <StatCard label="Ofertas guardadas" value={d.total} hint={`${d.seen_last_7_days} nuevas en 7 días`} />
              <StatCard label="Nuevas coincidencias" value={d.new_matches_count} tone="accent"
                        hint={`Estado «Nueva» y puntaje ≥ ${d.min_score}`} />
              <StatCard label="En preparación" value={d.counts.Revisar + d.counts.Preparada} tone="warning"
                        hint="Revisar + Preparada" />
              <StatCard label="Postuladas" value={d.counts.Postulada} tone="success" />
            </div>

            <div className="grid-2">
              <Card title="Mejores coincidencias nuevas"
                    actions={<Link to="/ofertas" className="link">Ver todas →</Link>}>
                {d.top_matches.length === 0 ? (
                  <Empty title="Sin coincidencias nuevas">
                    {d.total === 0 ? "Aún no hay ofertas. Pulsa «Buscar nuevas ofertas» (requiere internet)."
                                   : "Ajusta tu perfil o baja el puntaje mínimo."}
                  </Empty>
                ) : (
                  <div className="job-list">
                    {d.top_matches.map((j) => <JobCard key={j.id} job={j} onChange={(job) => replaceJob(d, job)} />)}
                  </div>
                )}
              </Card>

              <div className="stack">
                <Card title="Búsquedas">
                  <dl className="kv">
                    <dt>Última consulta</dt><dd>{d.search.last_scan ? relativeTime(d.search.last_scan) : "Nunca"}</dd>
                    <dt>Programación</dt><dd>{minutesLabel(d.search.scan_interval_minutes)}</dd>
                    {d.search.next_scheduled_at && <><dt>Próxima automática</dt><dd>{relativeTime(d.search.next_scheduled_at)}</dd></>}
                    {d.search.next_allowed_at && <><dt>Manual disponible</dt><dd>{relativeTime(d.search.next_allowed_at)}</dd></>}
                  </dl>
                  <p className="muted small">Las búsquedas programadas solo se ejecutan mientras JobHunter está abierto.</p>
                </Card>
                <Card title="Embudo">
                  <ul className="funnel">
                    {STATUSES.map((s) => (
                      <li key={s}><StatusBadge status={s} /><strong>{d.counts[s]}</strong></li>
                    ))}
                  </ul>
                </Card>
                <Card title="Cambios recientes">
                  {d.recent_changes.length === 0 ? <p className="muted">Sin cambios registrados todavía.</p> : (
                    <ul className="timeline">
                      {d.recent_changes.map((h) => (
                        <li key={h.id}>
                          <span>{h.title ?? h.job_id}</span>
                          <span className="muted small">{h.old_status} → {h.new_status} · {formatDate(h.changed_at)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>
              </div>
            </div>
          </>
        )}
      </AsyncView>
    </>
  );
}
