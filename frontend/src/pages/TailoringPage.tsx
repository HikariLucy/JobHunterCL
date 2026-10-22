import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import type { CvSuggestion, JobAnalysis, TailoringPlan, TailoringPreview } from '../api/types';
import { AsyncView, Card, Empty, ErrorBox, Loading, Notice, PageHeader } from '../components/ui';
import { useAsync } from '../hooks/useAsync';

const categories: Record<string,string> = {technology:'Tecnología',experience:'Experiencia',level:'Nivel',language:'Idioma',condition:'Condición laboral',other:'Otro requisito'};
const kinds = {required:'Obligatorio',nice_to_have:'Deseable',unknown:'Por confirmar'};
const actions = {reorder:'Reorganizar',emphasize:'Destacar',remove:'Omitir (opcional)',gap:'Brecha: no se añadirá',rephrase:'Edición manual'};
const statuses = {pending:'Pendiente',accepted:'Aceptada',rejected:'Rechazada'};
const language = (lang: string) => lang==='es'?'Español':'English';

function Requirements({analysis}: {analysis: JobAnalysis}) {
  return <Card title="Requisitos identificados">
    {analysis.partial && <Notice tone="warning">Análisis parcial: revisa manualmente el texto disponible y la oferta original.</Notice>}
    <p className="muted">Detección local orientativa. Una mención no acredita el cumplimiento del requisito. Idioma recomendado: {language(analysis.lang)} (modificable).</p>
    {analysis.requirements.length===0 && <p>No hay requisitos identificados con suficiente evidencia textual.</p>}
    <ul className="tailoring-requirements">{analysis.requirements.map((r,i)=><li key={i}><span className="badge">{kinds[r.kind]}</span> <strong>{r.skill||categories[r.category]||r.category}</strong><blockquote>{r.text}</blockquote></li>)}</ul>
    <details><summary>Revisar descripción guardada</summary><pre className="cv-source">{analysis.description||'Sin descripción disponible.'}</pre></details>
  </Card>;
}

function Workspace({jobId}: {jobId: string}) {
  const data=useAsync(async()=>({cvs:await api.cvs(),analysis:await api.analyzeJob(jobId)}),[jobId]);
  const [params,setParams]=useSearchParams();
  const planId=params.get('plan');
  const [plan,setPlan]=useState<TailoringPlan>();
  const [cvId,setCvId]=useState('');
  const [lang,setLang]=useState<'es'|'en'>('es');
  const [manualLang,setManualLang]=useState(false);
  const [preview,setPreview]=useState<TailoringPreview>();
  const [error,setError]=useState<string>();
  const [busy,setBusy]=useState(false);
  const [loadingPlan,setLoadingPlan]=useState(Boolean(planId));
  useEffect(()=>{if(data.data&&!manualLang)setLang(data.data.analysis.lang);},[data.data,manualLang]);
  useEffect(()=>{
    if(!planId){setLoadingPlan(false);return;}
    if(plan?.id===planId)return;
    let ignore=false; setLoadingPlan(true);setError(undefined);
    api.plan(planId).then(p=>{if(p.job_id!==jobId)throw new Error('El plan pertenece a otra oferta.');if(!ignore)setPlan(p);})
      .catch(e=>{if(!ignore)setError((e as Error).message);}).finally(()=>{if(!ignore)setLoadingPlan(false);});
    return()=>{ignore=true;};
  },[planId,jobId]);
  useEffect(()=>{
    let ignore=false;setPreview(undefined);
    if(plan)api.planPreview(plan).then(p=>{if(!ignore)setPreview(p);}).catch(e=>{if(!ignore)setError((e as Error).message);});
    return()=>{ignore=true;};
  },[plan]);
  const run=async(action:()=>Promise<TailoringPlan>)=>{
    setBusy(true);setError(undefined);setPreview(undefined);
    try{const p=await action();setPlan(p);setParams({plan:p.id},{replace:true});}
    catch(e){setError((e as Error).message);}
    finally{setBusy(false);}
  };
  const decide=(s: CvSuggestion,status: CvSuggestion['status'])=>{if(plan)void run(()=>api.decideSuggestion(plan,s.id,status));};
  return <>
    <PageHeader title="Adaptar CV" subtitle={plan?`${plan.analysis.title} · ${plan.analysis.company}`:data.data?`${data.data.analysis.title} · ${data.data.analysis.company}`:'Análisis local y copia revisable'}/>
    <div className="stack">
      <div className="row wrap"><Link className="btn" to="/ofertas">Volver a ofertas</Link><Link className="btn" to="/cv">Ir a Mis CV</Link></div>
      {error&&<ErrorBox error={error} onRetry={()=>{if(plan)void run(()=>api.plan(plan.id));else void data.reload();}}/>}
      {loadingPlan&&<Loading label="Cargando plan privado…"/>}
      <AsyncView state={plan?{...data, data:{cvs:data.data?.cvs||[],analysis:plan.analysis},error:undefined}:data}>{({cvs,analysis})=><>
        {!plan&&<>
          <Requirements analysis={analysis}/>
          {cvs.length===0?<Empty title="Importa un CV para crear un plan">Puedes revisar los requisitos sin CV ni perfil completo.</Empty>:<Card title="Elegir documento">
            <div className="form-grid">
              <div className="field"><label htmlFor="tailor-cv">Currículum</label><select id="tailor-cv" value={cvId} disabled={busy} onChange={e=>setCvId(e.target.value)}><option value="">Selecciona un CV</option>{cvs.map(cv=><option key={cv.id} value={cv.id}>{cv.name} · {language(cv.lang)}{cv.is_primary?' · Principal':''}</option>)}</select></div>
              <div className="field"><label htmlFor="tailor-lang">Idioma de trabajo</label><select id="tailor-lang" value={lang} disabled={busy} onChange={e=>{setManualLang(true);setLang(e.target.value as 'es'|'en');}}><option value="es">Español</option><option value="en">English</option></select></div>
            </div>
            <p className="muted">Recomendación modificable. La adaptación conserva el idioma del texto original; no traduce el documento.</p>
            <button className="btn btn-primary" disabled={!cvId||busy||loadingPlan||Boolean(planId)} onClick={()=>{const cv=cvs.find(cv=>cv.id===cvId);if(cv)void run(()=>api.createPlan(jobId,cv,lang));}}>Analizar y crear plan</button>
          </Card>}
        </>}
        {plan&&<>
          <Card title="Revisión fijada">
            <p><strong>{plan.cv_name}</strong> · {language(plan.lang)} · Revisión del plan {plan.revision}</p>
            <p className="cv-hash small">SHA-256 original: <code>{plan.cv_sha256}</code></p>
            {plan.cv_changed&&<Notice tone="warning">El maestro tiene una versión más reciente o ya no está disponible. Este plan conserva la instantánea original y no aplica cambios al maestro actual.</Notice>}
            {plan.job_changed&&<Notice tone="warning">La oferta cambió. Crea un nuevo plan antes de generar una copia.</Notice>}
            {plan.cv_partial&&<Notice tone="warning">Extracción parcial del CV: revisa el fuente. La estructura puede bloquear la generación automática.</Notice>}
            <button className="btn btn-small" disabled={busy} onClick={()=>{setPlan(undefined);setPreview(undefined);setParams({});setError(undefined);}}>Crear otro plan</button>
          </Card>
          <Requirements analysis={plan.analysis}/>
          <Card title="Coincidencias respaldadas">
            <p className="muted">Certeza: mención literal documentada. Revisa contexto, nivel y condiciones; no acredita dominio, años, título finalizado ni empleo formal.</p>
            {plan.matches.length===0?<p>Sin coincidencias documentadas suficientes.</p>:plan.matches.map((m,i)=><article className="cv-entry" key={i}><strong>{plan.analysis.requirements[m.requirement_index].skill}</strong><p>Oferta: {plan.analysis.requirements[m.requirement_index].text}</p><p className="muted">Sección: {m.evidence.section_key}</p><blockquote>{m.evidence.quote}</blockquote><p className="small">{m.rationale}</p></article>)}
          </Card>
          <Card title="Brechas por revisar">
            <p>Estas brechas no se incorporarán al documento.</p>
            {plan.suggestions.filter(s=>s.action==='gap').map(s=><p key={s.id} className="tag tag-warn">{s.rationale}</p>)}
            {!plan.suggestions.some(s=>s.action==='gap')&&<p>No se detectaron brechas dentro del catálogo analizado.</p>}
          </Card>
          <Card title="Propuestas individuales">
            <p className="muted">Solo se aplican las aceptadas. El contenido pendiente o rechazado se conserva. Las alternativas superpuestas requieren elegir una.</p>
            {plan.suggestions.filter(s=>s.action!=='gap').map(s=><article className={`cv-entry tailoring-${s.action}`} key={s.id}>
              <div className="row wrap"><h3>{actions[s.action]}</h3><span className="badge">{statuses[s.status]}</span></div><p>{s.rationale}</p>
              <details><summary>Evidencia y fragmentos originales · {s.section_key}</summary>{s.evidence.map((ev,i)=><blockquote key={i}>{ev.quote}</blockquote>)}<pre className="cv-source">{s.before}</pre>{s.after!==null&&<><p>Propuesta:</p><pre className="cv-source">{s.after||'(Omitido)'}</pre></>}</details>
              <div className="row wrap"><button className="btn btn-small" aria-label={`Aceptar propuesta ${s.id}`} disabled={busy||plan.job_changed||s.status==='accepted'} onClick={()=>decide(s,'accepted')}>Aceptar</button><button className="btn btn-small" aria-label={`Rechazar propuesta ${s.id}`} disabled={busy||plan.job_changed||s.status==='rejected'} onClick={()=>decide(s,'rejected')}>Rechazar</button><button className="btn btn-small" disabled={busy||plan.job_changed||s.status==='pending'} onClick={()=>decide(s,'pending')}>Dejar pendiente</button></div>
            </article>)}
            {!plan.suggestions.some(s=>s.action!=='gap')&&<p>No hay transformaciones automáticas seguras disponibles para este documento.</p>}
          </Card>
          <Card title="Diferencias propuestas">
            {!preview?<Loading label="Actualizando diferencias…"/>:<>
              {preview.blockers.map((b,i)=><Notice tone="warning" key={i}>{b}</Notice>)}
              <p className="muted">Conservado: líneas sin prefijo. Cambio: − original / + propuesta. Tipo de cambio en cada tarjeta: reorganizar, destacar u omitir. Las brechas quedan fuera del CV.</p>
              <pre className="cv-source tailoring-diff" aria-label="Diferencias propuestas">{preview.diff?preview.diff.split('\n').map((line,i)=><span key={i} className={line.startsWith('+')?'diff-added':line.startsWith('-')?'diff-removed':''}>{line}{'\n'}</span>):'Sin cambios aprobados: se conservará todo el documento.'}</pre>
              <details><summary>Comparar fuente completo conservado y resultado</summary><div className="tailoring-compare"><div><h3>Original</h3><pre className="cv-source">{preview.original}</pre></div><div><h3>Resultado propuesto</h3><pre className="cv-source">{preview.result}</pre></div></div></details>
            </>}
            <div className="row wrap"><button className="btn btn-primary" disabled={busy||!preview||preview.revision!==plan.revision||preview.blockers.length>0||plan.job_changed||Boolean(error)} onClick={()=>{if(preview)void run(()=>api.generateCv(plan,preview));}}>Generar CV adaptado</button>
            {plan.state==='generated'&&!busy&&<a className="btn" href={`/api/tailoring/plans/${plan.id}/download`} download>Descargar .tex adaptado</a>}</div>
            <p className="muted small">Se genera una nueva copia privada .tex. No modifica el maestro ni compila PDF.</p>
          </Card>
        </>}
      </>}</AsyncView>
      {busy&&<Loading label="Guardando revisión privada…"/>}
    </div>
  </>;
}

export function TailoringPage(){const {jobId=''}=useParams();return <Workspace key={jobId} jobId={jobId}/>;}
