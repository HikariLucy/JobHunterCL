import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { AppConfig, ImportResult } from "../api/types";
import { ListEditor } from "../components/ListEditor";
import { AsyncView, Card, ErrorBox, Notice, PageHeader } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { formatDate, minutesLabel } from "../utils/format";

const INTERVALS = [0, 30, 60, 120, 240, 360, 720, 1440];
const TOKEN = /^[a-zA-Z0-9_-]{2,70}$/;
const tokenCheck = (v: string) => (TOKEN.test(v) ? null : `«${v}» no es un identificador válido (letras, números, - o _).`);
const RUN_LABEL: Record<string, string> = {
  ok: "Correcta", partial: "Parcial", error: "Fallida", empty: "Sin resultados", running: "En curso", interrupted: "Interrumpida",
};

function SourcesForm({ initial, onSaved }: { initial: AppConfig; onSaved: (c: AppConfig) => void }) {
  const [c, setC] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  const [saved, setSaved] = useState(false);
  useEffect(() => setC(initial), [initial]);
  const setSource = <K extends keyof AppConfig["sources"]>(k: K, v: AppConfig["sources"][K]) => {
    setC({ ...c, sources: { ...c.sources, [k]: v } });
    setSaved(false);
  };

  const save = async () => {
    setSaving(true);
    setError(undefined);
    try {
      const next = await api.saveConfig({ sources: c.sources, scan_interval_minutes: c.scan_interval_minutes });
      onSaved(next);
      setSaved(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const effective = c.scan_interval_minutes > 0 ? Math.max(c.scan_interval_minutes, c.min_interval_minutes) : 0;

  return (
    <div className="stack">
      <Card title="Fuentes públicas">
        <label className="check">
          <input type="checkbox" checked={c.sources.getonbrd} onChange={(e) => setSource("getonbrd", e.target.checked)} />
          <span><strong>Get on Board</strong> — empleo tecnológico Chile/LatAm (feed público)</span>
        </label>
        <label className="check">
          <input type="checkbox" checked={c.sources.remotive} onChange={(e) => setSource("remotive", e.target.checked)} />
          <span><strong>Remotive</strong> — remotos internacionales; máximo 4 consultas al día (espera de 6,5 h)</span>
        </label>
        <ListEditor label="Greenhouse: identificadores públicos de empresas" values={c.sources.greenhouse_boards}
                    onChange={(v) => setSource("greenhouse_boards", v)} validate={tokenCheck}
                    hint="El «board token» de la URL pública, no credenciales." />
        <ListEditor label="Lever: identificadores públicos de empresas" values={c.sources.lever_sites}
                    onChange={(v) => setSource("lever_sites", v)} validate={tokenCheck} />
      </Card>

      <Card title="Búsqueda programada">
        <div className="field">
          <label htmlFor="interval">Frecuencia</label>
          <select id="interval" value={c.scan_interval_minutes}
                  onChange={(e) => { setC({ ...c, scan_interval_minutes: Number(e.target.value) }); setSaved(false); }}>
            {INTERVALS.map((m) => <option key={m} value={m}>{minutesLabel(m)}</option>)}
          </select>
        </div>
        <p className="muted small">
          Solo funciona mientras JobHunter está abierto; no se instala ningún servicio del sistema.
          {effective > 0 && effective !== c.scan_interval_minutes &&
            ` Por los límites de las fuentes activas, la frecuencia real será ${minutesLabel(effective).toLowerCase()}.`}
        </p>
      </Card>

      {error && <ErrorBox error={error} />}
      <div className="sticky-actions">
        <button className="btn btn-primary" onClick={save} disabled={saving}>{saving ? "Guardando…" : "Guardar configuración"}</button>
        {saved && <span className="text-success">Configuración guardada.</span>}
      </div>
    </div>
  );
}

function BackupCard() {
  const file = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ImportResult>();
  const [error, setError] = useState<string>();

  const doImport = async () => {
    const f = file.current?.files?.[0];
    if (!f) return;
    setBusy(true);
    setError(undefined);
    setResult(undefined);
    try {
      setResult(await api.importBackup(await f.text()));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Respaldo y traslado entre equipos">
      <p className="muted">El JSON incluye ofertas, estados, notas, historial y tu perfil. Es privado: transfiérelo por un canal personal seguro.</p>
      <div className="row wrap">
        <a className="btn" href={api.exportUrl} download>Descargar respaldo (.json)</a>
      </div>
      <div className="field">
        <label htmlFor="backup-file">Importar respaldo</label>
        <div className="row wrap">
          <input id="backup-file" ref={file} type="file" accept="application/json,.json" />
          <button className="btn" onClick={doImport} disabled={busy}>{busy ? "Importando…" : "Importar"}</button>
        </div>
        <small className="muted">Antes de importar se guarda una copia de la base en data/backups/.</small>
      </div>
      {result && (
        <Notice tone="success">
          {result.imported} registros importados{result.profile_restored ? " y perfil restaurado" : ""}.
          {result.safety_copy && ` Copia previa: ${result.safety_copy}.`}
        </Notice>
      )}
      {error && <ErrorBox error={error} />}
    </Card>
  );
}

export function Settings() {
  const config = useAsync(api.config);
  const status = useAsync(api.searchStatus);
  return (
    <>
      <PageHeader title="Configuración" subtitle="Fuentes, frecuencia de búsqueda y respaldos." />
      <div className="grid-2">
        <AsyncView state={config} label="Cargando configuración…">
          {(c) => <SourcesForm initial={c} onSaved={(next) => { config.setData(next); void status.reload(); }} />}
        </AsyncView>
        <div className="stack">
          <BackupCard />
          <Card title="Registro de búsquedas">
            <AsyncView state={status}>
              {(s) => s.recent_runs.length === 0 ? <p className="muted">Todavía no se han ejecutado búsquedas.</p> : (
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Inicio</th><th>Tipo</th><th>Resultado</th><th>Leídas</th><th>Nuevas</th></tr></thead>
                    <tbody>
                      {s.recent_runs.map((r) => (
                        <tr key={r.id} title={r.errors.join("\n")}>
                          <td>{formatDate(r.started_at)}</td>
                          <td>{r.trigger === "scheduled" ? "Programada" : "Manual"}</td>
                          <td className={`run-${r.status}`}>{RUN_LABEL[r.status] ?? r.status}{r.errors.length ? ` (${r.errors.length} fallos)` : ""}</td>
                          <td>{r.fetched}</td>
                          <td>{r.added}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </AsyncView>
          </Card>
        </div>
      </div>
    </>
  );
}
