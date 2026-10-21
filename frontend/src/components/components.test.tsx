import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeJob, mockFetch } from "../test/helpers";
import { JobCard } from "./JobCard";
import { ListEditor } from "./ListEditor";
import { SearchButton } from "./SearchButton";

afterEach(() => vi.unstubAllGlobals());

function Harness({ validate }: { validate?: (v: string) => string | null }) {
  const [values, setValues] = useState(["python"]);
  return <ListEditor label="Habilidades" values={values} onChange={setValues} validate={validate} />;
}

describe("ListEditor", () => {
  it("agrega varios valores, evita duplicados y permite quitar", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.type(screen.getByLabelText("Habilidades"), "SQL, Python, linux{Enter}");
    expect(screen.getByText("SQL")).toBeInTheDocument();
    expect(screen.getByText("linux")).toBeInTheDocument();
    expect(screen.queryByText("Python")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Quitar SQL" }));
    expect(screen.queryByText("SQL")).not.toBeInTheDocument();
  });

  it("muestra el error de validación", async () => {
    const user = userEvent.setup();
    render(<Harness validate={(v) => (v.includes("/") ? "inválido" : null)} />);
    await user.type(screen.getByLabelText("Habilidades"), "../x{Enter}");
    expect(screen.getByText("inválido")).toBeInTheDocument();
  });
});

describe("JobCard", () => {
  it("explica el puntaje, enlaza al original y cambia el estado", async () => {
    const user = userEvent.setup();
    const job = makeJob();
    const fetch = mockFetch({
      "GET /api/jobs/abc123/history": () => [],
      "PATCH /api/jobs/abc123": (_u, init) => ({ ...job, ...JSON.parse(String(init.body)) }),
    });
    const onChange = vi.fn();
    render(<JobCard job={job} onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /Desarrollador Junior Python/ }));
    expect(screen.getByText(/Cargo objetivo/)).toBeInTheDocument();
    expect(screen.getByText(/Revisar nivel de inglés/)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Abrir oferta original/ });
    expect(link).toHaveAttribute("href", job.url);
    expect(link).toHaveAttribute("rel", "noopener noreferrer");

    await user.selectOptions(screen.getByLabelText("Estado"), "Postulada");
    await waitFor(() => expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ status: "Postulada" })));
    expect(fetch).toHaveBeenCalledWith("/api/jobs/abc123", expect.objectContaining({ method: "PATCH" }));
  });

  it("muestra el error si falla el guardado", async () => {
    const user = userEvent.setup();
    mockFetch({
      "GET /api/jobs/abc123/history": () => [],
      "PATCH /api/jobs/abc123": () => new Response(JSON.stringify({ detail: "Oferta no encontrada" }), { status: 404 }),
    });
    render(<JobCard job={makeJob()} onChange={() => {}} defaultOpen />);
    await user.type(screen.getByLabelText("Notas privadas"), "hola");
    await user.click(screen.getByRole("button", { name: "Guardar nota" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Oferta no encontrada");
  });
});

describe("SearchButton", () => {
  it("explica la espera mínima cuando la API responde 429", async () => {
    const user = userEvent.setup();
    const soon = new Date(Date.now() + 20 * 60000).toISOString();
    mockFetch({
      "POST /api/search": () => new Response(JSON.stringify({ detail: { message: "x", next_allowed_at: soon } }), { status: 429 }),
    });
    render(<SearchButton />);
    await user.click(screen.getByRole("button", { name: "Buscar nuevas ofertas" }));
    expect(await screen.findByText(/Podrás buscar de nuevo en 20 min/)).toBeInTheDocument();
  });

  it("se deshabilita durante la espera mínima sin llamar a la búsqueda", async () => {
    const soon = new Date(Date.now() + 45 * 60000).toISOString();
    const fetch = mockFetch({ "GET /api/search/status": () => ({ next_allowed_at: soon }) });
    render(<SearchButton />);
    expect(await screen.findByText(/Disponible en 45 min/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Buscar nuevas ofertas" })).toBeDisabled();
    expect(fetch.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });

  it("queda habilitado si la espera ya venció", async () => {
    const past = new Date(Date.now() - 5 * 60000).toISOString();
    mockFetch({ "GET /api/search/status": () => ({ next_allowed_at: past }) });
    render(<SearchButton />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Buscar nuevas ofertas" })).toBeEnabled());
    expect(screen.queryByText(/Disponible/)).not.toBeInTheDocument();
  });

  it("si fallan todas las fuentes muestra error y cuándo reintentar", async () => {
    const user = userEvent.setup();
    let next: string | null = null;
    mockFetch({
      "GET /api/search/status": () => ({ next_allowed_at: next }),
      "POST /api/search": () => {
        next = new Date(Date.now() + 30 * 60000).toISOString();
        return { id: 2, started_at: "", finished_at: "", trigger: "manual", status: "error",
                 fetched: 0, added: 0, errors: ["Get on Board: HTTP 503"] };
      },
    });
    render(<SearchButton />);
    await user.click(screen.getByRole("button", { name: "Buscar nuevas ofertas" }));
    const msg = await screen.findByText(/No se pudo consultar ninguna fuente/);
    expect(msg).toHaveClass("text-error");
    expect(msg).toHaveTextContent("Fallos: Get on Board: HTTP 503 Podrás reintentar en 30 min.");
    expect(screen.getByRole("button", { name: "Buscar nuevas ofertas" })).toBeDisabled();
  });

  it("sin conexión a las fuentes indica que se puede reintentar ya", async () => {
    const user = userEvent.setup();
    mockFetch({
      "GET /api/search/status": () => ({ next_allowed_at: null }),
      "POST /api/search": () => ({ id: 3, started_at: "", finished_at: "", trigger: "manual", status: "error",
                                   fetched: 0, added: 0, errors: ["Get on Board: Connection refused"] }),
    });
    render(<SearchButton />);
    await user.click(screen.getByRole("button", { name: "Buscar nuevas ofertas" }));
    expect(await screen.findByText(/puedes reintentar ahora/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Buscar nuevas ofertas" })).toBeEnabled();
  });

  it("resume ofertas leídas y fallos parciales", async () => {
    const user = userEvent.setup();
    const onDone = vi.fn();
    mockFetch({
      "POST /api/search": () => ({ id: 1, started_at: "", finished_at: "", trigger: "manual", status: "partial",
                                   fetched: 12, added: 3, errors: ["Remotive: HTTP 429"] }),
    });
    render(<SearchButton onDone={onDone} />);
    await user.click(screen.getByRole("button", { name: "Buscar nuevas ofertas" }));
    expect(await screen.findByText(/12 ofertas leídas, 3 nuevas\. Fallos: Remotive: HTTP 429/)).toBeInTheDocument();
    expect(onDone).toHaveBeenCalled();
  });
});
