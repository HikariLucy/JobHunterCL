import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { ExperienceItem, LanguageItem, Profile } from "../api/types";
import { ListEditor } from "../components/ListEditor";
import { AsyncView, Card, ErrorBox, Notice, PageHeader } from "../components/ui";
import { useAsync } from "../hooks/useAsync";

const STEPS = ["Objetivos profesionales", "Experiencia y formación", "Habilidades", "Idiomas", "Preferencias", "Fuentes y límites", "Resumen y confirmación"];
const text = (values: string[]) => values.join(", ") || "Por confirmar";

function ProfileForm({ initial, wizard = false, onCancel, onSaved }: {
  initial: Profile; wizard?: boolean; onCancel: () => void; onSaved: (p: Profile) => void;
}) {
  const [p, setP] = useState<Profile>(initial);
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  const [saved, setSaved] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { if (wizard) heading.current?.focus(); }, [step, wizard]);
  const set = <K extends keyof Profile>(key: K, value: Profile[K]) => { setP({ ...p, [key]: value }); setSaved(false); };
  const pref = <K extends keyof Profile["preferences"]>(key: K, value: Profile["preferences"][K]) =>
    set("preferences", { ...p.preferences, [key]: value });
  const exp = (i: number, patch: Partial<ExperienceItem>) => set("experience", p.experience.map((x, n) => n === i ? { ...x, ...patch } : x));
  const lang = (i: number, patch: Partial<LanguageItem>) => set("languages", p.languages.map((x, n) => n === i ? { ...x, ...patch } : x));
  const show = (n: number) => !wizard || step === n;
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (wizard && step < 6) { setStep(step + 1); return; }
    setSaving(true); setError(undefined);
    try {
      const result = await api.saveProfile(p);
      setP(result); setSaved(true); onSaved(result);
    } catch (err) { setError((err as Error).message); }
    finally { setSaving(false); }
  };
  return <form onSubmit={submit} className="stack">
    <Notice>Registra solo experiencia y habilidades reales. Todo es opcional; lo que falta queda por confirmar y puedes completarlo después.</Notice>
    {wizard && <div>
      <p aria-live="polite">Paso {step + 1} de 7</p>
      <h2 tabIndex={-1} ref={heading}>{STEPS[step]}</h2>
    </div>}
    {show(0) && <Card title="Qué trabajos buscar">
      <ListEditor label="Cargos objetivo" values={p.titles} onChange={v => set("titles", v)} hint="Frases exactas suman más puntaje (p. ej. «soporte ti»)." />
      <ListEditor label="Áreas de interés" values={p.areas ?? []} onChange={v => set("areas", v)} />
      <div className="field"><label htmlFor="minscore">Puntaje mínimo para «nueva coincidencia»: <strong>{p.min_score}</strong></label>
        <input id="minscore" type="range" min={0} max={100} step={5} value={p.min_score} onChange={e => set("min_score", Number(e.target.value))} /></div>
    </Card>}
    {show(1) && <>
      <Card title="Experiencia" actions={<button type="button" className="btn btn-small" onClick={() => set("experience", [...p.experience, {role: "", organization: "", period: "", summary: "", kind: ""}])}>+ Añadir experiencia</button>}>
        {!p.experience.length && <p className="muted">Sin experiencia registrada.</p>}
        {p.experience.map((x, i) => <div className="repeat" key={i}>
          <div className="grid-3">
            <input aria-label="Cargo" placeholder="Cargo" value={x.role} onChange={e => exp(i, {role: e.target.value})} />
            <input aria-label="Organización" placeholder="Organización o proyecto" value={x.organization} onChange={e => exp(i, {organization: e.target.value})} />
            <input aria-label="Periodo" placeholder="Periodo (por confirmar si falta)" value={x.period} onChange={e => exp(i, {period: e.target.value})} />
          </div>
          <select aria-label="Tipo de experiencia" value={x.kind ?? ""} onChange={e => exp(i, {kind: e.target.value as ExperienceItem["kind"]})}>
            <option value="">Por confirmar</option><option value="empleo">Empleo formal</option><option value="practica">Práctica</option><option value="proyecto">Proyecto personal / educativo</option><option value="voluntariado">Voluntariado</option>
          </select>
          <textarea aria-label="Resumen" placeholder="Responsabilidades y logros verificables" value={x.summary} onChange={e => exp(i, {summary: e.target.value})} />
          <button type="button" className="btn btn-small btn-ghost" onClick={() => set("experience", p.experience.filter((_, n) => n !== i))}>Quitar experiencia</button>
        </div>)}
      </Card>
      <Card title="Formación" actions={<button type="button" className="btn btn-small" onClick={() => set("education", [...p.education ?? [], {title: "", institution: "", period: "", status: ""}])}>+ Añadir formación</button>}>
        {(p.education ?? []).map((x, i) => <div className="repeat" key={i}>
          {([['title', 'Estudio'], ['institution', 'Institución'], ['period', 'Periodo de estudio']] as const).map(([key, label]) => <input key={key} aria-label={label} placeholder={label} value={x[key]} onChange={e => set("education", p.education!.map((v, n) => n === i ? {...v, [key]: e.target.value} : v))} />)}
          <select aria-label="Estado de formación" value={x.status} onChange={e => set("education", p.education!.map((v, n) => n === i ? {...v, status: e.target.value as typeof x.status} : v))}>
            <option value="">Por confirmar</option><option value="en_curso">En curso (sin título completado)</option><option value="completado">Completado</option><option value="incompleto">Incompleto</option>
          </select>
          <button type="button" className="btn btn-small btn-ghost" onClick={() => set("education", p.education!.filter((_, n) => n !== i))}>Quitar formación</button>
        </div>)}
      </Card>
    </>}
    {show(2) && <Card title="Habilidades">
      <ListEditor label="Habilidades reales" values={p.skills} onChange={v => set("skills", v)} hint="Declaradas por ti; una coincidencia no acredita dominio." />
      <ListEditor label="Habilidades en aprendizaje" values={p.learning_skills ?? []} onChange={v => set("learning_skills", v)} hint="No se puntúan como habilidades dominadas." />
      <p className="muted">Evidencia opcional por habilidad: experiencia o proyecto que puedes explicar.</p>
      {p.skills.map(skill => <label className="field" key={skill}>Evidencia: {skill}
        <input value={p.skill_evidence?.find(x => x.skill === skill)?.evidence ?? ""} maxLength={500} onChange={e => set("skill_evidence", [...(p.skill_evidence ?? []).filter(x => x.skill !== skill), ...(e.target.value ? [{skill, evidence: e.target.value}] : [])])} />
      </label>)}
    </Card>}
    {show(3) && <Card title="Idiomas" actions={<button type="button" className="btn btn-small" onClick={() => set("languages", [...p.languages, {name: "", level: "", evidence: ""}])}>+ Añadir idioma</button>}>
      {!p.languages.length && <p className="muted">Sin idiomas registrados.</p>}
      {p.languages.map((x, i) => <div className="repeat" key={i}>
        <div className="grid-3">
          <input aria-label="Idioma" placeholder="Idioma" value={x.name} onChange={e => lang(i, {name: e.target.value})} />
          <input aria-label="Nivel" placeholder="Nivel declarado (A2, B2…)" value={x.level} onChange={e => lang(i, {level: e.target.value})} />
          <input aria-label="Evidencia del idioma" placeholder="Evidencia opcional, sin inferir certificación" value={x.evidence ?? ""} onChange={e => lang(i, {evidence: e.target.value})} />
        </div>
        <button type="button" className="btn btn-small btn-ghost" onClick={() => set("languages", p.languages.filter((_, n) => n !== i))}>Quitar idioma</button>
      </div>)}
    </Card>}
    {show(4) && <Card title="Preferencias laborales">
      <ListEditor label="Ubicaciones permitidas" values={p.locations} onChange={v => set("locations", v)} hint="Países o ciudades; remoto es modalidad, no un país." />
      <ListEditor label="Modalidad" values={p.preferences.modalities} onChange={v => pref("modalities", v)} placeholder="Remoto, híbrido, presencial…" />
      <ListEditor label="Nivel buscado" values={p.preferences.seniority} onChange={v => pref("seniority", v)} placeholder="Práctica, junior, intermedio…" />
      <div className="grid-3">
        <label className="field">Renta mínima esperada<input type="number" min={0} step={1} value={p.preferences.salary_min ?? ""} onChange={e => pref("salary_min", e.target.value === "" ? null : Number(e.target.value))} /></label>
        <label className="field">Moneda<select value={p.preferences.salary_currency} onChange={e => pref("salary_currency", e.target.value)}><option>CLP</option><option>USD</option><option>EUR</option></select></label>
        <label className="field">Periodicidad<select value={p.preferences.salary_period ?? "mensual"} onChange={e => pref("salary_period", e.target.value as "mensual" | "anual")}><option value="mensual">Mensual</option><option value="anual">Anual</option></select></label>
      </div>
      <label className="check"><input type="checkbox" checked={p.preferences.relocation} onChange={e => pref("relocation", e.target.checked)} />Dispuesto/a a reubicarme</label>
      <label className="field">Restricciones de residencia y otras notas<textarea value={p.preferences.notes} onChange={e => pref("notes", e.target.value)} /></label>
      <p className="muted">Las notas requieren revisión manual; reubicación no confirma autorización para trabajar en otro país.</p>
    </Card>}
    {show(5) && <Card title="Fuentes y límites">
      <Notice>No se consultan portales al configurar ni al iniciar. Búsqueda manual, o programada desde Configuración mientras la app está abierta.</Notice>
      {([['getonbrd', 'Get on Board — feed (mínimo 30 min)'], ['getonbrd_api', 'Get on Board — API pública (mínimo 60 min)'], ['remotive', 'Remotive (mínimo 6 h 30 min)']] as const).map(([key, label]) => <label className="check" key={key}><input type="checkbox" checked={p.sources[key]} onChange={e => set("sources", {...p.sources, [key]: e.target.checked})} />{label}</label>)}
      <ListEditor label="Greenhouse: identificadores públicos de empresas" values={p.sources.greenhouse_boards} onChange={v => set("sources", {...p.sources, greenhouse_boards: v})} />
      <ListEditor label="Lever: identificadores públicos de empresas" values={p.sources.lever_sites} onChange={v => set("sources", {...p.sources, lever_sites: v})} />
    </Card>}
    {wizard && step === 6 && <Card title="Revisa antes de guardar">
      <dl>
        <dt>Cargos objetivo</dt><dd>{text(p.titles)}</dd><dt>Áreas</dt><dd>{text(p.areas ?? [])}</dd>
        <dt>Experiencia</dt><dd>{p.experience.map(x => `${x.role || 'Cargo por confirmar'} · ${x.kind || 'Tipo por confirmar'} · ${x.organization || 'Organización por confirmar'} · ${x.period || 'Periodo por confirmar'} · ${x.summary || 'Responsabilidades por confirmar'}`).join('; ') || 'Por confirmar'}</dd>
        <dt>Formación</dt><dd>{p.education?.map(x => `${x.title || 'Estudio por confirmar'} · ${x.institution || 'Institución por confirmar'} · ${x.period || 'Periodo por confirmar'} · ${x.status || 'Estado por confirmar'}`).join('; ') || 'Por confirmar'}</dd>
        <dt>Habilidades declaradas</dt><dd>{text(p.skills)}</dd><dt>Evidencias aportadas</dt><dd>{p.skill_evidence?.map(x => `${x.skill}: ${x.evidence}`).join('; ') || 'Por confirmar'}</dd>
        <dt>En aprendizaje</dt><dd>{text(p.learning_skills ?? [])}</dd><dt>Idiomas</dt><dd>{p.languages.map(x => `${x.name || 'Idioma por confirmar'}: ${x.level || 'Nivel por confirmar'} · ${x.evidence || 'Sin evidencia aportada'}`).join('; ') || 'Por confirmar'}</dd>
        <dt>Ubicaciones</dt><dd>{text(p.locations)}</dd><dt>Modalidad y nivel</dt><dd>{text(p.preferences.modalities)} · {text(p.preferences.seniority)}</dd>
        <dt>Renta mínima</dt><dd>{p.preferences.salary_min == null ? 'Opcional, sin definir' : `${p.preferences.salary_min} ${p.preferences.salary_currency} / ${p.preferences.salary_period ?? 'mensual'}`}</dd>
        <dt>Relocalización y restricciones</dt><dd>{p.preferences.relocation ? 'Dispuesto/a' : 'No indicada'} · {p.preferences.notes || 'Sin notas'}</dd>
        <dt>Fuentes</dt><dd>{[p.sources.getonbrd && 'Get on Board feed', p.sources.getonbrd_api && 'Get on Board API', p.sources.remotive && 'Remotive', ...p.sources.greenhouse_boards.map(x => `Greenhouse: ${x}`), ...p.sources.lever_sites.map(x => `Lever: ${x}`)].filter(Boolean).join(', ') || 'Ninguna activa'}</dd>
      </dl>
      <div className="row wrap">{STEPS.slice(0, 6).map((label, i) => <button key={label} type="button" className="btn btn-small" onClick={() => setStep(i)}>Editar {label.toLowerCase()}</button>)}</div>
    </Card>}
    {error && <ErrorBox error={error} />}
    <div className="sticky-actions" aria-live="polite">
      {wizard && <><button type="button" className="btn" disabled={saving} onClick={onCancel}>Cancelar</button>
        {step > 0 && <button type="button" className="btn" disabled={saving} onClick={() => setStep(step - 1)}>Anterior</button>}</>}
      <button className="btn btn-primary" type="submit" disabled={saving}>{saving ? 'Guardando…' : wizard && step < 6 ? 'Siguiente' : 'Guardar perfil'}</button>
      {saved && <span className="text-success">Perfil guardado en este equipo.</span>}
    </div>
  </form>;
}

export function ProfilePage() {
  const state = useAsync(async () => {
    const status = await api.profileStatus();
    if (!status.readable) throw new Error(`El perfil local está dañado: ${status.error}. ${status.backup_available ? 'Existe una copia .bak.' : ''} Consulta docs/PERFIL.md; no se modificó el archivo.`);
    return {profile: status.exists ? await api.profile() : status.new_profile, fresh: !status.exists};
  });
  const [mode, setMode] = useState<boolean>();
  const [version, setVersion] = useState(0);
  const [persisted, setPersisted] = useState<Profile>();
  return <>
    <PageHeader title="Mi perfil" subtitle="Se guarda solo en el directorio de datos de este equipo." />
    <AsyncView state={state} label="Cargando perfil…">{({profile, fresh}) => <>
      {!(mode ?? fresh) && <button type="button" className="btn" onClick={() => {setMode(true); setVersion(v => v + 1);}}>Abrir asistente</button>}
      <ProfileForm key={version} initial={persisted ?? profile} wizard={mode ?? fresh}
        onCancel={() => {setMode(false); setVersion(v => v + 1); sessionStorage.setItem('jobhunter-onboarding-dismissed', '1');}}
        onSaved={saved => { setPersisted(saved); setMode(false); sessionStorage.setItem('jobhunter-onboarding-dismissed', '1'); }} />
    </>}</AsyncView>
  </>;
}
