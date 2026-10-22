import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { App } from '../App';
import { mockFetch } from '../test/helpers';

const profile = { titles: [], skills: [], areas: [], learning_skills: [], skill_evidence: [], education: [],
  locations: [], min_score: 30, sources: {getonbrd: true, getonbrd_api: true, remotive: false, greenhouse_boards: [], lever_sites: []},
  experience: [], languages: [], preferences: {modalities: [], seniority: [], salary_min: null, salary_currency: 'CLP', salary_period: 'mensual', relocation: false, notes: ''} };
afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear(); });
function setup(exists = false, fail = false) {
  const fetch = mockFetch({
    'GET /api/health': () => ({status: 'ok'}),
    'GET /api/profile/status': () => ({exists, readable: true, error: null, backup_available: false, new_profile: profile}),
    'GET /api/profile': () => profile,
    'PUT /api/profile': (_u, init) => fail ? new Response(JSON.stringify({detail: 'Disco lleno'}), {status: 500}) : JSON.parse(String(init.body)),
  });
  render(<MemoryRouter initialEntries={['/perfil']}><App /></MemoryRouter>);
  return fetch;
}
it('primera ejecución: pasos opcionales, borrador conservado, resumen y guardado sin búsqueda', async () => {
  const u = userEvent.setup(); const fetch = setup();
  expect(await screen.findByText(/Paso 1 de 7/)).toBeInTheDocument();
  await u.type(screen.getByLabelText('Cargos objetivo'), 'soporte ti{Enter}');
  await u.click(screen.getByRole('button', {name: 'Siguiente'}));
  await u.click(screen.getByRole('button', {name: 'Anterior'}));
  expect(screen.getByText('soporte ti')).toBeInTheDocument();
  for (let i=0;i<6;i++) await u.click(screen.getByRole('button', {name: 'Siguiente'}));
  expect(screen.getByRole('heading', {name: 'Resumen y confirmación'})).toBeInTheDocument();
  await u.click(screen.getByRole('button', {name: 'Guardar perfil'}));
  expect(await screen.findByText('Perfil guardado en este equipo.')).toBeInTheDocument();
  const put = fetch.mock.calls.find(([,init]) => init?.method === 'PUT');
  expect(JSON.parse(String(put?.[1]?.body)).titles).toEqual(['soporte ti']);
  expect(fetch.mock.calls.some(([url]) => String(url).includes('/search'))).toBe(false);
});
it('perfil existente no fuerza wizard y cancelar asistente no guarda', async () => {
  const u = userEvent.setup(); const fetch = setup(true);
  await screen.findByLabelText('Cargos objetivo');
  expect(screen.queryByText(/Paso 1 de 7/)).not.toBeInTheDocument();
  await u.click(screen.getByRole('button', {name: 'Abrir asistente'}));
  await u.type(screen.getByLabelText('Cargos objetivo'), 'cambio{Enter}');
  await u.click(screen.getByRole('button', {name: 'Cancelar'}));
  expect(screen.queryByText('cambio')).not.toBeInTheDocument();
  expect(fetch.mock.calls.some(([,init]) => init?.method === 'PUT')).toBe(false);
});
it('error de escritura mantiene borrador y no muestra éxito', async () => {
  const u = userEvent.setup(); setup(false, true);
  await u.type(await screen.findByLabelText('Cargos objetivo'), 'analista{Enter}');
  for (let i=0;i<6;i++) await u.click(screen.getByRole('button', {name: 'Siguiente'}));
  await u.click(screen.getByRole('button', {name: 'Guardar perfil'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Disco lleno');
  expect(screen.getByText('analista')).toBeInTheDocument();
  expect(screen.queryByText('Perfil guardado en este equipo.')).not.toBeInTheDocument();
});
it('campos veraces: proyecto, formación en curso, aprendizaje y evidencia se guardan', async () => {
  const u = userEvent.setup(); const fetch = setup();
  await screen.findByLabelText('Cargos objetivo');
  await u.click(screen.getByRole('button', {name: 'Siguiente'}));
  await u.click(screen.getByRole('button', {name: '+ Añadir experiencia'}));
  await u.type(screen.getByLabelText('Cargo'), 'Laboratorio');
  await u.selectOptions(screen.getByLabelText('Tipo de experiencia'), 'proyecto');
  await u.click(screen.getByRole('button', {name: '+ Añadir formación'}));
  await u.type(screen.getByLabelText('Estudio'), 'Informática');
  await u.selectOptions(screen.getByLabelText('Estado de formación'), 'en_curso');
  await u.click(screen.getByRole('button', {name: 'Siguiente'}));
  await u.type(screen.getByLabelText('Habilidades reales'), 'linux{Enter}');
  await u.type(screen.getByLabelText('Evidencia: linux'), 'Laboratorio local');
  await u.type(screen.getByLabelText('Habilidades en aprendizaje'), 'rust{Enter}');
  for(let i=0;i<4;i++) await u.click(screen.getByRole('button', {name: 'Siguiente'}));
  expect(screen.getByText(/Informática.*en_curso/)).toBeInTheDocument();
  await u.click(screen.getByRole('button', {name: 'Guardar perfil'}));
  await screen.findByText('Perfil guardado en este equipo.');
  const put = fetch.mock.calls.find(([,init]) => init?.method === 'PUT');
  expect(JSON.parse(String(put?.[1]?.body))).toMatchObject({experience: [{kind:'proyecto', role:'Laboratorio'}], education:[{status:'en_curso'}], learning_skills:['rust'], skill_evidence:[{skill:'linux',evidence:'Laboratorio local'}]});
});
it('perfil corrupto no abre wizard ni escribe', async () => {
  const fetch = mockFetch({'GET /api/health': () => ({status:'ok'}), 'GET /api/profile/status': () => ({exists:true,readable:false,error:'JSON inválido',backup_available:true})});
  render(<MemoryRouter initialEntries={['/perfil']}><App /></MemoryRouter>);
  expect(await screen.findByRole('alert')).toHaveTextContent('copia .bak');
  expect(screen.queryByText(/Paso 1/)).not.toBeInTheDocument();
  expect(fetch.mock.calls.some(([,init]) => init?.method === 'PUT')).toBe(false);
});
