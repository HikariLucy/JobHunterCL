import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { makeJob, mockFetch } from "../test/helpers";

afterEach(() => vi.unstubAllGlobals());

const SEARCH = { running: false, last_scan: null, next_allowed_at: null, min_interval_minutes: 30,
                 scan_interval_minutes: 0, next_scheduled_at: null, recent_runs: [] };
const COUNTS = { Nueva: 1, Revisar: 0, Preparada: 0, Postulada: 2, Descartada: 0 };
const base = {
  "GET /api/health": () => ({ status: "ok" }),
  "GET /api/jobs/sources": () => ["Get on Board"],
};

const renderAt = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);

describe("navegación y páginas", () => {
  it("Dashboard muestra métricas y navega a Explorar", async () => {
    const user = userEvent.setup();
    mockFetch({
      ...base,
      "GET /api/dashboard": () => ({ total: 3, counts: COUNTS, min_score: 30, new_matches_count: 1,
                                     top_matches: [makeJob()], seen_last_7_days: 3, search: SEARCH, recent_changes: [] }),
      "GET /api/jobs": () => ({ items: [], total: 0, stored: 3 }),
    });
    renderAt("/");
    expect(await screen.findByText("Nuevas coincidencias")).toBeInTheDocument();
    expect(screen.getByText("Desarrollador Junior Python")).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: /Explorar ofertas/ }));
    expect(await screen.findByRole("heading", { name: "Explorar ofertas" })).toBeInTheDocument();
  });

  it("Explorar envía los filtros a la API", async () => {
    const user = userEvent.setup();
    const fetch = mockFetch({ ...base, "GET /api/jobs": () => ({ items: [makeJob()], total: 1, stored: 5 }) });
    renderAt("/ofertas");
    expect(await screen.findByText("1 ofertas visibles de 5 guardadas")).toBeInTheDocument();
    await user.click(screen.getByLabelText("Postulada"));
    await waitFor(() => {
      const last = String(fetch.mock.calls.filter(([u]) => String(u).startsWith("/api/jobs?")).at(-1)?.[0]);
      expect(last).toContain("status=Nueva&status=Revisar&status=Postulada");
    });
  });

  it("muestra error con opción de reintentar si la API falla", async () => {
    const user = userEvent.setup();
    let fail = true;
    mockFetch({
      ...base,
      "GET /api/tracking": () => fail
        ? new Response(JSON.stringify({ detail: "Base bloqueada" }), { status: 500 })
        : { statuses: ["Nueva", "Revisar", "Preparada", "Postulada", "Descartada"], counts: COUNTS,
            items: [makeJob({ status: "Postulada" })], recent_changes: [] },
    });
    renderAt("/seguimiento");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Base bloqueada");
    fail = false;
    await user.click(within(alert).getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Desarrollador Junior Python")).toBeInTheDocument();
  });

  it("Configuración avisa cuando la frecuencia real es mayor por límites de fuentes", async () => {
    const user = userEvent.setup();
    mockFetch({
      ...base,
      "GET /api/config": () => ({ sources: { getonbrd: true, remotive: true, greenhouse_boards: [], lever_sites: [] },
                                  scan_interval_minutes: 0, min_interval_minutes: 390 }),
      "GET /api/search/status": () => SEARCH,
    });
    renderAt("/configuracion");
    await user.selectOptions(await screen.findByLabelText("Frecuencia"), "60");
    expect(screen.getByText(/la frecuencia real será cada 6.5 h/)).toBeInTheDocument();
  });

  it("Perfil guarda y confirma", async () => {
    const user = userEvent.setup();
    const profile = { titles: ["soporte ti"], skills: ["python"], locations: ["chile"], min_score: 30,
                      sources: { getonbrd: true, remotive: false, greenhouse_boards: [], lever_sites: [] },
                      experience: [], languages: [],
                      preferences: { modalities: [], seniority: [], salary_min: null, salary_currency: "CLP", relocation: false, notes: "" } };
    const fetch = mockFetch({ ...base, "GET /api/profile": () => profile, "PUT /api/profile": (_u, init) => JSON.parse(String(init.body)) });
    renderAt("/perfil");
    await user.type(await screen.findByLabelText("Habilidades reales"), "docker{Enter}");
    await user.click(screen.getByRole("button", { name: "Guardar perfil" }));
    expect(await screen.findByText("Perfil guardado en este equipo.")).toBeInTheDocument();
    const put = fetch.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(JSON.parse(String(put?.[1]?.body)).skills).toEqual(["python", "docker"]);
  });
});
