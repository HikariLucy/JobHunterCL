import type {
  CvMetadata, CvPreview, AppConfig, Dashboard, Health, HistoryEntry, ImportResult, Job, JobPage, JobQuery,
  Profile, ProfileStatus, ScanRun, SearchStatus, Status, Tracking,
} from "./types";

export const OFFLINE_MESSAGE =
  "No se pudo conectar con el servidor local de JobHunter. ¿Sigue abierta la ventana del lanzador?";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** Convierte el `detail` de FastAPI (texto, objeto o lista de validación) en un mensaje legible. */
export function messageFromDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string; loc?: unknown[] };
    const field = Array.isArray(first.loc) ? first.loc.slice(1).join(".") : "";
    return [field, first.msg].filter(Boolean).join(": ") || fallback;
  }
  if (detail && typeof detail === "object" && "message" in detail) {
    return String((detail as { message: unknown }).message);
  }
  return fallback;
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: { Accept: "application/json", ...(init.body ? { "Content-Type": "application/json" } : {}), ...init.headers },
    });
  } catch {
    throw new ApiError(0, OFFLINE_MESSAGE);
  }
  if (!response.ok) {
    let detail: unknown;
    try {
      detail = (await response.json()).detail;
    } catch {
      detail = undefined;
    }
    throw new ApiError(response.status, messageFromDetail(detail, `Error ${response.status}`), detail);
  }
  return (await response.json()) as T;
}

export function toQuery(params: JobQuery): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "" || value === null) continue;
    if (Array.isArray(value)) value.forEach((v) => search.append(key, String(v)));
    else search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

const json = (body: unknown) => JSON.stringify(body);

export const api = {
  cvs: () => request<CvMetadata[]>("/cv"),
  cvPreview: (id: string) => request<CvPreview>(`/cv/${encodeURIComponent(id)}/preview`),
  importCv: (file: File, name: string, lang: 'es' | 'en') => request<CvMetadata>("/cv/import", {
    method: "POST", body: file, headers: {"Content-Type": "application/x-tex",
      "X-CV-Filename": encodeURIComponent(file.name), "X-CV-Name": encodeURIComponent(name), "X-CV-Lang": lang},
  }),
  primaryCv: (id: string) => request<CvMetadata>(`/cv/${encodeURIComponent(id)}/primary`, {method: "PUT"}),
  replaceCv: (cv: CvMetadata, file: File) => request<CvMetadata>(`/cv/${encodeURIComponent(cv.id)}?confirm=true&expected_sha256=${cv.sha256}`, {
    method: "PUT", body: file, headers: {"Content-Type": "application/x-tex", "X-CV-Filename": encodeURIComponent(file.name)},
  }),
  deleteCv: (cv: CvMetadata) => request<{deleted: boolean}>(`/cv/${encodeURIComponent(cv.id)}?confirm=true&expected_sha256=${cv.sha256}`, {method: "DELETE"}),
  health: () => request<Health>("/health"),
  dashboard: () => request<Dashboard>("/dashboard"),
  jobs: (q: JobQuery = {}) => request<JobPage>(`/jobs${toQuery(q)}`),
  jobSources: () => request<string[]>("/jobs/sources"),
  job: (id: string) => request<Job>(`/jobs/${encodeURIComponent(id)}`),
  updateJob: (id: string, patch: { status?: Status; notes?: string }) =>
    request<Job>(`/jobs/${encodeURIComponent(id)}`, { method: "PATCH", body: json(patch) }),
  history: (id: string) => request<HistoryEntry[]>(`/jobs/${encodeURIComponent(id)}/history`),
  tracking: () => request<Tracking>("/tracking"),
  searchStatus: () => request<SearchStatus>("/search/status"),
  runSearch: () => request<ScanRun>("/search", { method: "POST" }),
  profile: () => request<Profile>("/profile"),
  profileStatus: () => request<ProfileStatus>("/profile/status"),
  saveProfile: (p: Profile) => request<Profile>("/profile", { method: "PUT", body: json(p) }),
  config: () => request<AppConfig>("/config"),
  saveConfig: (c: Partial<Pick<AppConfig, "sources" | "scan_interval_minutes">>) =>
    request<AppConfig>("/config", { method: "PUT", body: json(c) }),
  exportUrl: "/api/backup/export",
  importBackup: (content: string) =>
    request<ImportResult>("/backup/import", { method: "POST", body: content }),
};
