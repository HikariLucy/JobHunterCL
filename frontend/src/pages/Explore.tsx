import { useEffect, useState } from "react";
import { api } from "../api/client";
import { STATUSES, type Job, type JobPage, type Status } from "../api/types";
import { JobCard } from "../components/JobCard";
import { SearchButton } from "../components/SearchButton";
import { AsyncView, Empty, PageHeader } from "../components/ui";
import { useAsync } from "../hooks/useAsync";

const PAGE = 50;

function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return v;
}

export function Explore() {
  const [statuses, setStatuses] = useState<Status[]>(["Nueva", "Revisar"]);
  const [minScore, setMinScore] = useState(30);
  const [text, setText] = useState("");
  const [source, setSource] = useState("");
  const [sort, setSort] = useState<"score" | "recent">("score");
  const [limit, setLimit] = useState(PAGE);
  const q = useDebounced(text);
  const score = useDebounced(minScore, 200);

  const sources = useAsync(api.jobSources);
  const page = useAsync(
    () => api.jobs({ status: statuses, min_score: score, q, source, sort, limit }),
    [statuses.join(","), score, q, source, sort, limit],
  );

  const toggleStatus = (s: Status) =>
    setStatuses((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]));

  const replace = (data: JobPage, job: Job) =>
    page.setData({ ...data, items: data.items.map((j) => (j.id === job.id ? job : j)) });

  return (
    <>
      <PageHeader title="Explorar ofertas" subtitle="La puntuación es orientativa y siempre explica sus motivos."
                  actions={<SearchButton compact onDone={() => { void page.reload(); void sources.reload(); }} />} />

      <div className="filters card">
        <div className="field grow">
          <label htmlFor="q">Buscar</label>
          <input id="q" type="search" placeholder="Cargo, empresa o ubicación" value={text}
                 onChange={(e) => setText(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="min">Puntaje mínimo: <strong>{minScore}</strong></label>
          <input id="min" type="range" min={0} max={100} step={5} value={minScore}
                 onChange={(e) => setMinScore(Number(e.target.value))} />
        </div>
        <div className="field">
          <label htmlFor="source">Fuente</label>
          <select id="source" value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="">Todas</option>
            {(sources.data ?? []).map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="sort">Orden</label>
          <select id="sort" value={sort} onChange={(e) => setSort(e.target.value as "score" | "recent")}>
            <option value="score">Mejor puntaje</option>
            <option value="recent">Más recientes</option>
          </select>
        </div>
        <fieldset className="field status-filter">
          <legend>Estados</legend>
          {STATUSES.map((s) => (
            <label key={s} className="check">
              <input type="checkbox" checked={statuses.includes(s)} onChange={() => toggleStatus(s)} /> {s}
            </label>
          ))}
        </fieldset>
      </div>

      <AsyncView state={page} label="Cargando ofertas…">
        {(data) => (
          <>
            <p className="muted small" aria-live="polite">
              {data.total} ofertas visibles de {data.stored} guardadas{page.loading ? " · actualizando…" : ""}
            </p>
            {data.items.length === 0 ? (
              <Empty title="No hay ofertas con estos filtros">
                {data.stored === 0 ? "Pulsa «Buscar nuevas ofertas». Necesitas conexión a internet."
                                   : "Prueba bajando el puntaje mínimo o incluyendo más estados."}
              </Empty>
            ) : (
              <div className="job-list">
                {data.items.map((j) => <JobCard key={j.id} job={j} onChange={(job) => replace(data, job)} />)}
              </div>
            )}
            {data.total > data.items.length && (
              <button className="btn load-more" onClick={() => setLimit((l) => l + PAGE)}>
                Mostrar más ({data.total - data.items.length} restantes)
              </button>
            )}
          </>
        )}
      </AsyncView>
    </>
  );
}
