import { vi } from "vitest";
import type { Job } from "../api/types";

export function makeJob(overrides: Partial<Job> = {}): Job {
  return {
    id: "abc123",
    source: "Get on Board",
    title: "Desarrollador Junior Python",
    company: "Acme",
    location: "Santiago, Chile",
    url: "https://example.org/jobs/1",
    description: "Python y SQL",
    posted_at: "",
    first_seen: "2026-10-20T12:00:00+00:00",
    last_seen: "2026-10-20T12:00:00+00:00",
    status: "Nueva",
    notes: "",
    score: 72,
    reasons: ["Cargo objetivo: desarrollador junior"],
    warnings: ["Revisar nivel de inglés exigido"],
    eligibility: { status: "compatible", evidence: "ubicación: Santiago, Chile", basis: "texto" },
    ...overrides,
  };
}

type Handler = (url: URL, init: RequestInit) => unknown | Response;

/** Sustituye fetch por un enrutador simple: { "GET /api/jobs": handler }. */
export function mockFetch(routes: Record<string, Handler>) {
  const fn = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input), "http://127.0.0.1");
    const key = `${init.method ?? "GET"} ${url.pathname}`;
    const handler = routes[key];
    if (!handler) return new Response(JSON.stringify({ detail: `Sin mock: ${key}` }), { status: 404 });
    const result = handler(url, init);
    return result instanceof Response ? result : new Response(JSON.stringify(result), { status: 200 });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}
