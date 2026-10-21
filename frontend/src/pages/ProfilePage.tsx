import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { ExperienceItem, LanguageItem, Profile } from "../api/types";
import { ListEditor } from "../components/ListEditor";
import { AsyncView, Card, ErrorBox, Notice, PageHeader } from "../components/ui";
import { useAsync } from "../hooks/useAsync";

const EMPTY_EXP: ExperienceItem = { role: "", organization: "", period: "", summary: "" };
const EMPTY_LANG: LanguageItem = { name: "", level: "" };

function ProfileForm({ initial }: { initial: Profile }) {
  const [p, setP] = useState<Profile>(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  const [saved, setSaved] = useState(false);
  useEffect(() => setP(initial), [initial]);

  const set = <K extends keyof Profile>(key: K, value: Profile[K]) => { setP({ ...p, [key]: value }); setSaved(false); };
  const setPref = <K extends keyof Profile["preferences"]>(key: K, value: Profile["preferences"][K]) =>
    set("preferences", { ...p.preferences, [key]: value });
  const setExp = (i: number, patch: Partial<ExperienceItem>) =>
    set("experience", p.experience.map((e, idx) => (idx === i ? { ...e, ...patch } : e)));
  const setLang = (i: number, patch: Partial<LanguageItem>) =>
    set("languages", p.languages.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(undefined);
    try {
      const clean: Profile = {
        ...p,
        experience: p.experience.filter((x) => x.role.trim()),
        languages: p.languages.filter((x) => x.name.trim()),
      };
      setP(await api.saveProfile(clean));
      setSaved(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="stack">
      <Notice>Registra solo experiencia y habilidades reales: el matching y la futura adaptación de CV nunca inventan datos.</Notice>

      <Card title="Qué trabajos buscar">
        <ListEditor label="Cargos objetivo" values={p.titles} onChange={(v) => set("titles", v)}
                    hint="Frases exactas suman más puntaje (p. ej. «soporte ti»)." />
        <ListEditor label="Habilidades reales" values={p.skills} onChange={(v) => set("skills", v)} />
        <ListEditor label="Ubicaciones y modalidades" values={p.locations} onChange={(v) => set("locations", v)} />
        <div className="field">
          <label htmlFor="minscore">Puntaje mínimo para «nueva coincidencia»: <strong>{p.min_score}</strong></label>
          <input id="minscore" type="range" min={0} max={100} step={5} value={p.min_score}
                 onChange={(e) => set("min_score", Number(e.target.value))} />
        </div>
      </Card>

      <Card title="Experiencia" actions={
        <button type="button" className="btn btn-small" onClick={() => set("experience", [...p.experience, { ...EMPTY_EXP }])}>+ Añadir</button>}>
        {p.experience.length === 0 && <p className="muted">Sin experiencia registrada.</p>}
        {p.experience.map((x, i) => (
          <div className="repeat" key={i}>
            <div className="grid-3">
              <input aria-label="Cargo" placeholder="Cargo" value={x.role} onChange={(e) => setExp(i, { role: e.target.value })} />
              <input aria-label="Organización" placeholder="Organización" value={x.organization} onChange={(e) => setExp(i, { organization: e.target.value })} />
              <input aria-label="Periodo" placeholder="Periodo (p. ej. 2024–2025)" value={x.period} onChange={(e) => setExp(i, { period: e.target.value })} />
            </div>
            <textarea aria-label="Resumen" rows={2} placeholder="Logros y tareas verificables" value={x.summary}
                      onChange={(e) => setExp(i, { summary: e.target.value })} />
            <button type="button" className="btn btn-small btn-ghost"
                    onClick={() => set("experience", p.experience.filter((_, idx) => idx !== i))}>Quitar</button>
          </div>
        ))}
      </Card>

      <div className="grid-2">
        <Card title="Idiomas" actions={
          <button type="button" className="btn btn-small" onClick={() => set("languages", [...p.languages, { ...EMPTY_LANG }])}>+ Añadir</button>}>
          {p.languages.length === 0 && <p className="muted">Sin idiomas registrados.</p>}
          {p.languages.map((l, i) => (
            <div className="row" key={i}>
              <input aria-label="Idioma" placeholder="Idioma" value={l.name} onChange={(e) => setLang(i, { name: e.target.value })} />
              <input aria-label="Nivel" placeholder="Nivel (A2, B2, nativo…)" value={l.level} onChange={(e) => setLang(i, { level: e.target.value })} />
              <button type="button" className="btn btn-small btn-ghost" aria-label={`Quitar idioma ${l.name}`}
                      onClick={() => set("languages", p.languages.filter((_, idx) => idx !== i))}>×</button>
            </div>
          ))}
        </Card>

        <Card title="Preferencias laborales">
          <ListEditor label="Modalidad" values={p.preferences.modalities} onChange={(v) => setPref("modalities", v)}
                      placeholder="Remoto, híbrido, presencial…" />
          <ListEditor label="Nivel buscado" values={p.preferences.seniority} onChange={(v) => setPref("seniority", v)}
                      placeholder="Práctica, junior…" />
          <div className="row">
            <div className="field grow">
              <label htmlFor="salary">Renta mínima esperada</label>
              <input id="salary" type="number" min={0} step={10000} value={p.preferences.salary_min ?? ""}
                     onChange={(e) => setPref("salary_min", e.target.value === "" ? null : Number(e.target.value))} />
            </div>
            <div className="field">
              <label htmlFor="currency">Moneda</label>
              <select id="currency" value={p.preferences.salary_currency} onChange={(e) => setPref("salary_currency", e.target.value)}>
                <option>CLP</option><option>USD</option><option>EUR</option>
              </select>
            </div>
          </div>
          <label className="check">
            <input type="checkbox" checked={p.preferences.relocation} onChange={(e) => setPref("relocation", e.target.checked)} />
            Dispuesto/a a reubicarme
          </label>
        </Card>
      </div>

      {error && <ErrorBox error={error} />}
      <div className="sticky-actions">
        <button className="btn btn-primary" type="submit" disabled={saving}>{saving ? "Guardando…" : "Guardar perfil"}</button>
        {saved && <span className="text-success">Perfil guardado en este equipo.</span>}
      </div>
    </form>
  );
}

export function ProfilePage() {
  const state = useAsync(api.profile);
  return (
    <>
      <PageHeader title="Mi perfil" subtitle="Se guarda solo en data/profile.json de este equipo." />
      <AsyncView state={state} label="Cargando perfil…">{(p) => <ProfileForm initial={p} />}</AsyncView>
    </>
  );
}
