import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { TailoringPage } from './TailoringPage';
import { mockFetch } from '../test/helpers';
const analysis={job_id:'job',title:'Backend sintético',company:'Empresa ficticia',lang:'es',description:'Python obligatorio',description_sha256:'a'.repeat(64),partial:true,warnings:['Análisis parcial'],requirements:[{text:'Python obligatorio',kind:'required',skill:'Python',category:'technology'}]};
const cv={id:'b'.repeat(32),name:'CV sintético',lang:'es',sha256:'c'.repeat(64),size_bytes:100,imported_at:'2026-10-21',updated_at:'2026-10-21',is_primary:false};
const evidence={section_key:'projects[1]',quote:'Proyecto con Python.',tex_span:[10,30]};
const plan={id:'d'.repeat(32),job_id:'job',cv_id:cv.id,cv_name:cv.name,lang:'en',cv_sha256:cv.sha256,revision:1,state:'review',analysis,matches:[{requirement_index:0,evidence,confidence:'literal_mention',rationale:'Mención literal'}],suggestions:[{id:'s1',action:'emphasize',section_key:'projects[1]',before:'Python',after:'\\textbf{Python}',tex_span:[23,29],requirement_indices:[0],rationale:'Destacar término existente',evidence:[evidence],status:'pending'}],blockers:[],cv_partial:true,cv_changed:false,job_changed:false,coverage:1};
const preview={revision:1,original:'Proyecto con Python.',result:'Proyecto con Python.',diff:'',sha256:'e'.repeat(64),blockers:[],applied:[]};
afterEach(()=>vi.unstubAllGlobals());
function open(){render(<MemoryRouter initialEntries={['/ofertas/job/adaptar']}><Routes><Route path="/ofertas/:jobId/adaptar" element={<TailoringPage/>}/></Routes></MemoryRouter>);}
it('sin CV ofrece importar y conserva análisis parcial',async()=>{
 mockFetch({'GET /api/cv':()=>[], 'GET /api/tailoring/jobs/job/analysis':()=>analysis});open();
 expect(await screen.findByRole('link',{name:'Ir a Mis CV'})).toHaveAttribute('href','/cv');
 expect(screen.getByText(/Análisis parcial/)).toBeInTheDocument();
 expect(screen.queryByRole('button',{name:'Generar CV adaptado'})).not.toBeInTheDocument();
});
it('idioma manual, evidencia, decisiones, diff y descarga',async()=>{
 let current=structuredClone(plan);
 const fetch=mockFetch({'GET /api/cv':()=>[cv], 'GET /api/tailoring/jobs/job/analysis':()=>analysis,'POST /api/tailoring/plans':()=>current,
 [`GET /api/tailoring/plans/${plan.id}/preview`]:()=>({...preview,revision:current.revision,diff:current.revision>1?'@@\n- Python\n+ \\textbf{Python}':''}),
 [`PATCH /api/tailoring/plans/${plan.id}/suggestions/s1`]:(_u,init)=>{const body=JSON.parse(String(init.body));current={...current,revision:current.revision+1,suggestions:current.suggestions.map(s=>({...s,status:body.status}))};return current;},
 [`POST /api/tailoring/plans/${plan.id}/generate`]:()=>({...current,revision:current.revision+1,state:'generated',artifact_sha256:preview.sha256})});
 open();const user=userEvent.setup();await screen.findByLabelText('Currículum');await user.selectOptions(screen.getByLabelText('Currículum'),cv.id);await user.selectOptions(screen.getByLabelText('Idioma de trabajo'),'en');await user.click(screen.getByRole('button',{name:'Analizar y crear plan'}));
 expect((await screen.findAllByText('Proyecto con Python.')).length).toBeGreaterThan(0);expect(screen.getByText(/Extracción parcial del CV/)).toBeInTheDocument();
 await user.click(screen.getByRole('button',{name:'Aceptar propuesta s1'}));expect(await screen.findByText('Aceptada')).toBeInTheDocument();
 await waitFor(()=>expect(screen.getByLabelText('Diferencias propuestas')).toHaveTextContent('\\textbf{Python}'));
 await user.click(screen.getByRole('button',{name:'Rechazar propuesta s1'}));expect(await screen.findByText('Rechazada')).toBeInTheDocument();
 await waitFor(()=>expect(screen.getByRole('button',{name:'Generar CV adaptado'})).toBeEnabled());await user.click(screen.getByRole('button',{name:'Generar CV adaptado'}));
 expect(await screen.findByRole('link',{name:'Descargar .tex adaptado'})).toHaveAttribute('href',`/api/tailoring/plans/${plan.id}/download`);
 const create=fetch.mock.calls.find(([url,init])=>String(url)==='/api/tailoring/plans'&&init?.method==='POST');expect(JSON.parse(String(create?.[1]?.body))).toEqual({job_id:'job',cv_id:cv.id,expected_cv_sha256:cv.sha256,lang:'en'});
});
it('conflictos bloquean y revisión nueva se advierte',async()=>{
 mockFetch({'GET /api/cv':()=>[cv], 'GET /api/tailoring/jobs/job/analysis':()=>analysis,'POST /api/tailoring/plans':()=>({...plan,cv_changed:true}),[`GET /api/tailoring/plans/${plan.id}/preview`]:()=>({...preview,blockers:['Conflicto de cambios superpuestos']})});open();const user=userEvent.setup();await screen.findByLabelText('Currículum');await user.selectOptions(screen.getByLabelText('Currículum'),cv.id);await user.click(screen.getByRole('button',{name:'Analizar y crear plan'}));
 expect(await screen.findByText(/Conflicto de cambios/)).toBeInTheDocument();expect(screen.getByText(/versión más reciente/)).toBeInTheDocument();expect(screen.getByRole('button',{name:'Generar CV adaptado'})).toBeDisabled();
});

it('plan conservado sigue visible cuando la oferta actual fue eliminada',async()=>{
 mockFetch({'GET /api/cv':()=>[cv], 'GET /api/tailoring/jobs/job/analysis':()=>new Response(JSON.stringify({detail:'Oferta no encontrada'}),{status:404}),[`GET /api/tailoring/plans/${plan.id}`]:()=>({...plan,job_changed:true}),[`GET /api/tailoring/plans/${plan.id}/preview`]:()=>({...preview,blockers:['La oferta cambió']})});
 render(<MemoryRouter initialEntries={[`/ofertas/job/adaptar?plan=${plan.id}`]}><Routes><Route path="/ofertas/:jobId/adaptar" element={<TailoringPage/>}/></Routes></MemoryRouter>);
 expect(await screen.findByText('CV sintético')).toBeInTheDocument();
 expect(screen.getByText(/La oferta cambió. Crea un nuevo plan/)).toBeInTheDocument();
 expect((await screen.findAllByText('Proyecto con Python.')).length).toBeGreaterThan(0);
});
