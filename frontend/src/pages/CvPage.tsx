import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { api } from '../api/client';
import type { CvMetadata, CvPreview } from '../api/types';
import { AsyncView, Card, Empty, ErrorBox, Loading, Notice, PageHeader } from '../components/ui';
import { useAsync } from '../hooks/useAsync';

const language = (lang: string) => lang === 'es' ? 'Español' : 'English';

function Preview({cv}: {cv: CvMetadata}) {
  const state = useAsync(() => api.cvPreview(cv.id), [cv.id, cv.sha256]);
  return <AsyncView state={state}>{(p: CvPreview) => <Card title={`Contenido · ${cv.name}`}>
    <Notice tone={p.partial ? 'warning' : 'info'}>{p.partial ? 'Extracción parcial · revisa el contenido no interpretado.' : 'Secciones reconocidas · revisa la extracción.'}</Notice>
    {p.warnings.map((w, i) => <p className="muted small" key={i}>{w}</p>)}
    <h3>Información reconocida</h3>
    {p.sections.length === 0 && <p className="muted">No se pudo extraer texto reconocido.</p>}
    {p.sections.map(s => <section key={s.key} className="cv-section">
      <h3>{s.title} <span className="badge">{s.kind === 'other' ? 'Otra sección' : s.kind}</span></h3>
      <p className="small muted">Fuente: caracteres {s.tex_span[0]}–{s.tex_span[1]} · {s.key}</p>
      <pre className="cv-text">{s.text}</pre>
    </section>)}
    <h3>Contenido no interpretado</h3>
    {p.uninterpreted.length === 0 ? <p className="muted">No se detectaron macros desconocidas.</p> : p.uninterpreted.map((u,i) => <div key={i} className="cv-section">
      <p className="small muted">{u.reason} Caracteres {u.tex_span[0]}–{u.tex_span[1]}.</p>
      <pre className="cv-text">{u.raw_tex}</pre>
    </div>)}
    <details><summary>Ver fuente LaTeX conservado (solo texto)</summary><pre className="cv-text">{p.source_text}</pre></details>
  </Card>}</AsyncView>;
}

export function CvPage() {
  const list = useAsync(api.cvs);
  const [name, setName] = useState('');
  const [lang, setLang] = useState<'es'|'en'>('es');
  const [file, setFile] = useState<File>();
  const [replacement, setReplacement] = useState<File>();
  const [selected, setSelected] = useState<CvMetadata>();
  const [action, setAction] = useState<{kind:'replace'|'delete'; cv:CvMetadata}>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState<Error>();
  const form = useRef<HTMLFormElement>(null);
  async function run(work: () => Promise<void>, success: string) {
    setBusy(true); setError(undefined); setMessage('');
    try {
      await work();
      setMessage(success);
      await list.reload();
    } catch (e) {setError(e instanceof Error ? e : new Error(String(e)));}
    finally {setBusy(false);}
  }
  function importCv(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    void run(async () => {
      await api.importCv(file, name.trim(), lang);
      setFile(undefined); setName(''); form.current?.reset(); setLang('es');
    }, 'CV importado en este equipo.');
  }
  return <>
    <PageHeader title="Mis CV" subtitle="Tus currículums LaTeX, conservados de forma privada en este equipo."/>
    <div className="stack">
      <Notice>Importa una copia .tex en UTF-8. El archivo original permanece intacto. Puedes usar JobHunter sin registrar un CV.</Notice>
      {message && <Notice tone="success">{message}</Notice>}
      {error && <ErrorBox error={error}/>}
      <Card title="Importar currículum">
        <form ref={form} onSubmit={importCv}>
          <fieldset className="cv-form" disabled={busy}>
            <div className="field"><label htmlFor="cv-name">Nombre descriptivo</label><input id="cv-name" value={name} required maxLength={120} onChange={e=>setName(e.target.value)}/></div>
            <div className="field"><label htmlFor="cv-lang">Idioma del CV</label><select id="cv-lang" value={lang} onChange={e=>setLang(e.target.value as 'es'|'en')}><option value="es">Español</option><option value="en">English</option></select></div>
            <div className="field"><label htmlFor="cv-file">Archivo LaTeX (.tex)</label><input id="cv-file" type="file" accept=".tex" required onChange={e=>setFile(e.target.files?.[0])}/></div>
            <button className="btn btn-primary" disabled={!file || !name.trim()} type="submit">Importar CV</button>
          </fieldset>
        </form>
        <p className="muted small">Vista textual local. No compila PDF ni ejecuta macros. Los CV no se incluyen en el respaldo JSON.</p>
      </Card>
      <AsyncView state={list}>{rows => rows.length === 0 ? <Empty title="Todavía no tienes CV registrados">Elige un archivo .tex para empezar.</Empty> : <Card title="Currículums guardados">
        <div className="stack">{rows.map(cv => <article className="cv-entry" key={cv.id}>
          <div className="row wrap"><h3>{cv.name}</h3><span className={`badge ${cv.is_primary?'status-preparada':''}`}>{cv.is_primary?'Principal · ':''}{language(cv.lang)}</span></div>
          <p className="muted small">Importado: {new Date(cv.imported_at).toLocaleString()} · {cv.size_bytes.toLocaleString()} bytes<br/>Última versión: {new Date(cv.updated_at).toLocaleString()}</p>
          <p className="cv-hash small">SHA-256: <code>{cv.sha256}</code></p>
          <div className="row wrap">
            <button className="btn btn-small" disabled={busy} onClick={()=>{setSelected(cv);setError(undefined);}}>Ver contenido</button>
            <button className="btn btn-small" disabled={busy||cv.is_primary} onClick={()=>void run(async()=>{await api.primaryCv(cv.id);}, 'CV principal actualizado.')}>Usar como principal</button>
            <button className="btn btn-small" disabled={busy} onClick={()=>{setAction({kind:'replace',cv});setReplacement(undefined);setMessage('');}}>Sustituir</button>
            <button className="btn btn-small text-error" disabled={busy} onClick={()=>{setAction({kind:'delete',cv});setMessage('');}}>Eliminar</button>
          </div>
          {action?.cv.id===cv.id && <div className="cv-confirm" role="group" aria-label={action.kind==='replace'?'Confirmar sustitución':'Confirmar eliminación'}>
            <p>{action.kind==='replace'?'Se sustituirá la copia gestionada por el nuevo archivo.':'Se eliminará la copia gestionada y su registro.'} El original del usuario permanece intacto. CV: <strong>{action.cv.name}</strong>.</p>
            {action.kind==='replace' && <div className="field"><label htmlFor="cv-replacement">Nuevo archivo .tex</label><input id="cv-replacement" type="file" accept=".tex" disabled={busy} onChange={e=>setReplacement(e.target.files?.[0])}/></div>}
            <div className="row wrap">
              <button className="btn btn-primary" disabled={busy||(action.kind==='replace'&&!replacement)} onClick={()=>{
                const pending=action;
                void run(async()=>{
                  if(pending.kind==='replace'&&replacement) await api.replaceCv(pending.cv,replacement);
                  else if(pending.kind==='delete') await api.deleteCv(pending.cv);
                  setAction(undefined);setSelected(undefined);setReplacement(undefined);
                },pending.kind==='replace'?'Copia gestionada sustituida.':'Copia gestionada eliminada.');
              }}>Confirmar {action.kind==='replace'?'sustitución':'eliminación'}</button>
              <button className="btn" disabled={busy} onClick={()=>{setAction(undefined);setReplacement(undefined);}}>Cancelar {action.kind==='replace'?'sustitución':'eliminación'}</button>
            </div>
          </div>}
        </article>)}</div>
      </Card>}</AsyncView>
      {busy && <Loading label="Guardando cambios de CV…"/>}
      {selected && <Preview key={selected.id+selected.sha256} cv={selected}/>}
    </div>
  </>;
}
