import { StrictMode } from 'react';
import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { App } from '../App';
import { api } from '../api/client';
import type { Profile } from '../api/types';
import { mockFetch } from '../test/helpers';

const profile: Profile = { titles: [], skills: [], areas: [], learning_skills: [], skill_evidence: [], education: [],
  locations: [], min_score: 30, sources: {getonbrd: true, getonbrd_api: true, remotive: false, greenhouse_boards: [], lever_sites: []},
  experience: [], languages: [], preferences: {modalities: [], seniority: [], salary_min: null, salary_currency: 'CLP', salary_period: 'mensual', relocation: false, notes: ''} };
const status = {exists: false, readable: true, error: null, backup_available: false, new_profile: profile};
const counts = {Nueva: 0, Revisar: 0, Preparada: 0, Postulada: 0, Descartada: 0};
const search = {running: false, last_scan: null, next_allowed_at: null, min_interval_minutes: 30,
  scan_interval_minutes: 0, next_scheduled_at: null, recent_runs: []};

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); sessionStorage.clear(); });

function Location() {
  const location = useLocation();
  const navigate = useNavigate();
  return <><output aria-label="Ruta actual">{location.pathname}{location.search}{location.hash}</output>
    <button onClick={() => navigate(-1)}>Volver en historial</button></>;
}

function setup(exists = false) {
  const fetch = mockFetch({
    'GET /api/cv': () => [],
    'GET /api/health': () => ({status: 'ok'}),
    'GET /api/profile/status': () => ({...status, exists}),
    'GET /api/profile': () => profile,
    'GET /api/dashboard': () => ({total: 0, counts, min_score: 30, new_matches_count: 0,
      top_matches: [], seen_last_7_days: 0, search, recent_changes: []}),
    'GET /api/jobs': () => ({items: [], total: 0, stored: 0}),
    'GET /api/jobs/sources': () => [],
    'GET /api/tracking': () => ({statuses: Object.keys(counts), counts, items: [], recent_changes: []}),
    'GET /api/config': () => ({sources: profile.sources, scan_interval_minutes: 0, min_interval_minutes: 30}),
    'GET /api/search/status': () => search,
  });
  return fetch;
}

function open(path = '/') {
  return render(<StrictMode><MemoryRouter initialEntries={[path]}><App /><Location /></MemoryRouter></StrictMode>);
}

async function settled() { await act(async () => {}); }

async function visit(label: string, path: string) {
  await userEvent.setup().click(within(screen.getByRole('navigation', {name: 'Secciones'})).getByRole('link', {name: new RegExp(label)}));
  await settled();
  expect(screen.getByLabelText('Ruta actual')).toHaveTextContent(new RegExp(`^${path}$`));
  expect(screen.getByRole('heading', {name: label, level: 1})).toBeInTheDocument();
}

it('sin perfil permite abandonar el asistente y recorrer las seis secciones sin redirecciones', async () => {
  setup(); open();
  await screen.findByText('Paso 1 de 7');
  await visit('Dashboard', '/');
  await visit('Explorar ofertas', '/ofertas');
  await visit('Seguimiento', '/seguimiento');
  await visit('Mis CV', '/cv');
  await visit('Configuración', '/configuracion');
  await visit('Mi perfil', '/perfil');
});

it('cancelar respeta la omisión al volver a Mi perfil y no guarda datos', async () => {
  const fetch = setup(); open();
  await screen.findByText('Paso 1 de 7');
  await userEvent.setup().click(screen.getByRole('button', {name: 'Cancelar'}));
  for (const [label, path] of [['Dashboard', '/'], ['Explorar ofertas', '/ofertas'],
    ['Seguimiento', '/seguimiento'], ['Mis CV', '/cv'], ['Configuración', '/configuracion'], ['Mi perfil', '/perfil']]) {
    await visit(label, path);
  }
  expect(screen.queryByText('Paso 1 de 7')).not.toBeInTheDocument();
  await userEvent.setup().click(screen.getByRole('button', {name: 'Abrir asistente'}));
  expect(screen.getByText('Paso 1 de 7')).toBeInTheDocument();
  expect(fetch.mock.calls.some(([, init]) => init?.method === 'PUT')).toBe(false);
});

it('perfil existente permite las seis secciones sin abrir onboarding', async () => {
  setup(true); open(); await settled();
  for (const [label, path] of [['Explorar ofertas', '/ofertas'], ['Seguimiento', '/seguimiento'], ['Mis CV', '/cv'],
    ['Configuración', '/configuracion'], ['Mi perfil', '/perfil'], ['Dashboard', '/']]) {
    await visit(label, path);
    expect(screen.queryByText('Paso 1 de 7')).not.toBeInTheDocument();
  }
});

it('una respuesta tardía no redirige después de navegar ni al volver con el historial', async () => {
  setup();
  let resolve!: (value: typeof status) => void;
  const pending = new Promise<typeof status>(done => { resolve = done; });
  const check = vi.spyOn(api, 'profileStatus').mockReturnValue(pending);
  open();
  await visit('Explorar ofertas', '/ofertas');
  await userEvent.setup().click(screen.getByRole('button', {name: 'Volver en historial'}));
  await act(async () => { resolve(status); await pending; });
  expect(screen.getByLabelText('Ruta actual')).toHaveTextContent(/^\/$/);
  await visit('Seguimiento', '/seguimiento');
  expect(check).toHaveBeenCalledTimes(1);
});

it('cambiar solo la consulta invalida una redirección pendiente', async () => {
  setup();
  let resolve!: (value: typeof status) => void;
  const pending = new Promise<typeof status>(done => { resolve = done; });
  vi.spyOn(api, 'profileStatus').mockReturnValue(pending);
  open('/ofertas?status=Nueva');
  await visit('Explorar ofertas', '/ofertas');
  await act(async () => { resolve(status); await pending; });
  expect(screen.getByLabelText('Ruta actual')).toHaveTextContent(/^\/ofertas$/);
});
