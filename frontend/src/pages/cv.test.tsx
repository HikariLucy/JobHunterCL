import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { CvPage } from './CvPage';
import { mockFetch } from '../test/helpers';
const cv = {id:'abc', name:'CV sintético', lang:'es', sha256:'a'.repeat(64), imported_at:'2026-10-21', updated_at:'2026-10-21', size_bytes:100, is_primary:false};
const preview = {source:cv, source_text:'<script>window.bad=1</script>', sections:[{key:'skills[1]',title:'Habilidades',kind:'skills',text:'<img src=x onerror=alert(1)>Python',tex_span:[0,20],raw_tex:'fuente'}],skills:[],partial:true,warnings:['Extracción parcial'],uninterpreted:[{tex_span:[20,40],raw_tex:'\\unknown{dato}',reason:'Macro desconocida'}]};
afterEach(() => {vi.restoreAllMocks();vi.unstubAllGlobals();});
it('importa en inglés, previsualiza texto seguro y selecciona principal', async () => {
 let rows: typeof cv[]=[];
 const fetch=mockFetch({'GET /api/cv':()=>rows,'POST /api/cv/import':()=>{rows=[{...cv,lang:'en'}];return rows[0];},'GET /api/cv/abc/preview':()=>preview,'PUT /api/cv/abc/primary':()=>{rows=[{...rows[0],is_primary:true}];return rows[0];}});
 const user=userEvent.setup(); const {container}=render(<CvPage/>);
 await screen.findByText('Todavía no tienes CV registrados');
 await user.type(screen.getByLabelText('Nombre descriptivo'),'CV sintético');
 await user.selectOptions(screen.getByLabelText('Idioma del CV'),'en');
 await user.upload(screen.getByLabelText('Archivo LaTeX (.tex)'),new File(['\\section{Skills}Python'],'cv.tex'));
 // jsdom no considera válido el FileList sintético para required; se verifica submit real en Chromium.
 fireEvent.submit(screen.getByRole('button',{name:'Importar CV'}).closest('form')!);
 await screen.findByText('CV importado en este equipo.');
 await user.click(screen.getByRole('button',{name:'Ver contenido'}));
 await screen.findByText('<img src=x onerror=alert(1)>Python');
 expect(screen.getByText('\\unknown{dato}')).toBeInTheDocument();
 expect(container.querySelector('script, img')).toBeNull();
 await user.click(screen.getByRole('button',{name:'Usar como principal'}));
 await screen.findByText('Principal · English');
 const post=fetch.mock.calls.find(([,i])=>i?.method==='POST');
 expect((post?.[1]?.headers as Record<string,string>)['X-CV-Lang']).toBe('en');
});
it('cancelar no muta; confirmar sustituye o elimina con el hash revisado', async () => {
 let rows=[cv];
 const fetch=mockFetch({'GET /api/cv':()=>rows,'PUT /api/cv/abc':()=>cv,'DELETE /api/cv/abc':()=>{rows=[];return {deleted:true};}});
 const user=userEvent.setup();render(<CvPage/>);await screen.findByText('CV sintético');
 await user.click(screen.getByRole('button',{name:'Sustituir'}));
 await user.click(screen.getByRole('button',{name:'Cancelar sustitución'}));
 await user.click(screen.getByRole('button',{name:'Eliminar'}));
 await user.click(screen.getByRole('button',{name:'Cancelar eliminación'}));
 expect(fetch.mock.calls.some(([,i])=>['PUT','DELETE'].includes(i?.method??''))).toBe(false);
 await user.click(screen.getByRole('button',{name:'Sustituir'}));
 await user.upload(screen.getByLabelText('Nuevo archivo .tex'),new File(['\\section{Skills}SQL'],'new.tex'));
 await user.click(screen.getByRole('button',{name:'Confirmar sustitución'}));
 await screen.findByText('Copia gestionada sustituida.');
 await user.click(screen.getByRole('button',{name:'Eliminar'}));
 await user.click(screen.getByRole('button',{name:'Confirmar eliminación'}));
 await screen.findByText('Copia gestionada eliminada.');
 const put=fetch.mock.calls.find(([,i])=>i?.method==='PUT');
 expect(String(put?.[0])).toContain('expected_sha256='+cv.sha256);
 expect(String(put?.[0])).toContain('confirm=true');
});
it('el error conserva el formulario y no informa éxito', async () => {
 mockFetch({'GET /api/cv':()=>[],'POST /api/cv/import':()=>new Response(JSON.stringify({detail:'Archivo demasiado grande'}),{status:413})});
 const user=userEvent.setup();render(<CvPage/>);await screen.findByText('Todavía no tienes CV registrados');
 await user.type(screen.getByLabelText('Nombre descriptivo'),'Ejemplo');
 await user.upload(screen.getByLabelText('Archivo LaTeX (.tex)'),new File(['datos'],'cv.tex'));
 // jsdom no considera válido el FileList sintético para required; se verifica submit real en Chromium.
 fireEvent.submit(screen.getByRole('button',{name:'Importar CV'}).closest('form')!);
 await waitFor(()=>expect(screen.getByRole('alert')).toHaveTextContent('Archivo demasiado grande'));
 expect(screen.getByLabelText('Nombre descriptivo')).toHaveValue('Ejemplo');
 expect(screen.queryByText('CV importado en este equipo.')).not.toBeInTheDocument();
});
