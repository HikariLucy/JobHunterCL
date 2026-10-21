import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, messageFromDetail, OFFLINE_MESSAGE, toQuery } from "./client";
import { mockFetch } from "../test/helpers";

afterEach(() => vi.unstubAllGlobals());

describe("toQuery", () => {
  it("repite parámetros de lista y omite vacíos", () => {
    expect(toQuery({ status: ["Nueva", "Revisar"], q: "", min_score: 0 })).toBe("?status=Nueva&status=Revisar&min_score=0");
    expect(toQuery({})).toBe("");
  });
});

describe("messageFromDetail", () => {
  it("entiende los formatos de error de FastAPI", () => {
    expect(messageFromDetail("Oferta no encontrada", "x")).toBe("Oferta no encontrada");
    expect(messageFromDetail([{ loc: ["body", "status"], msg: "Input should be 'Nueva'" }], "x"))
      .toBe("status: Input should be 'Nueva'");
    expect(messageFromDetail({ message: "Espera" }, "x")).toBe("Espera");
    expect(messageFromDetail(undefined, "fallback")).toBe("fallback");
  });
});

describe("request", () => {
  it("lanza ApiError con estado y detalle", async () => {
    mockFetch({
      "POST /api/search": () => new Response(JSON.stringify({ detail: { message: "Reciente", next_allowed_at: "2026-10-21T13:00:00Z" } }), { status: 429 }),
    });
    const err = await api.runSearch().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(429);
    expect(err.message).toBe("Reciente");
    expect(err.detail.next_allowed_at).toBe("2026-10-21T13:00:00Z");
  });

  it("informa claramente cuando el servidor local no responde", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(api.health()).rejects.toMatchObject({ status: 0, message: OFFLINE_MESSAGE });
  });

  it("envía PATCH con JSON", async () => {
    const fetch = mockFetch({ "PATCH /api/jobs/a%2Fb": (_u, init) => ({ ok: JSON.parse(String(init.body)) }) });
    await api.updateJob("a/b", { status: "Revisar" });
    const [, init] = fetch.mock.calls[0];
    expect(init?.method).toBe("PATCH");
    expect((init?.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });
});
