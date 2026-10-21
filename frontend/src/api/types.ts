// Contratos espejo de backend/schemas.py

export const STATUSES = ["Nueva", "Revisar", "Preparada", "Postulada", "Descartada"] as const;
export type Status = (typeof STATUSES)[number];

export type EligibilityStatus = "compatible" | "desconocida" | "incompatible";

/** Elegibilidad geográfica para las zonas del perfil, con la evidencia usada. */
export interface Eligibility {
  status: EligibilityStatus;
  evidence: string;
  basis: string;
}

export interface Job {
  id: string;
  source: string;
  title: string;
  company: string;
  location: string | null;
  url: string;
  description: string | null;
  posted_at: string | null;
  first_seen: string;
  last_seen: string;
  status: Status;
  notes: string;
  score: number;
  reasons: string[];
  warnings: string[];
  eligibility: Eligibility;
}

export interface JobPage {
  items: Job[];
  total: number;
  stored: number;
}

export interface JobQuery {
  status?: Status[];
  min_score?: number;
  q?: string;
  source?: string;
  sort?: "score" | "recent";
  eligibility?: EligibilityStatus | "";
  limit?: number;
  offset?: number;
}

export interface HistoryEntry {
  id: number;
  job_id: string;
  old_status: string | null;
  new_status: string;
  changed_at: string;
  origin: string;
  title?: string | null;
  company?: string | null;
}

export interface ScanRun {
  id: number;
  started_at: string;
  finished_at: string | null;
  trigger: "manual" | "scheduled" | string;
  status: "running" | "ok" | "partial" | "error" | "empty" | "interrupted" | string;
  fetched: number;
  added: number;
  errors: string[];
}

export interface SearchStatus {
  running: boolean;
  last_scan: string | null;
  next_allowed_at: string | null;
  min_interval_minutes: number;
  scan_interval_minutes: number;
  next_scheduled_at: string | null;
  recent_runs: ScanRun[];
}

export interface Dashboard {
  total: number;
  counts: Record<Status, number>;
  min_score: number;
  new_matches_count: number;
  top_matches: Job[];
  seen_last_7_days: number;
  search: SearchStatus;
  recent_changes: HistoryEntry[];
}

export interface Tracking {
  statuses: Status[];
  counts: Record<Status, number>;
  items: Job[];
  recent_changes: HistoryEntry[];
}

export interface Sources {
  getonbrd: boolean;
  getonbrd_api: boolean;
  remotive: boolean;
  greenhouse_boards: string[];
  lever_sites: string[];
}

export interface ExperienceItem {
  role: string;
  organization: string;
  period: string;
  summary: string;
}

export interface LanguageItem {
  name: string;
  level: string;
}

export interface Preferences {
  modalities: string[];
  seniority: string[];
  salary_min: number | null;
  salary_currency: string;
  relocation: boolean;
  notes: string;
}

export interface Profile {
  titles: string[];
  skills: string[];
  locations: string[];
  min_score: number;
  sources: Sources;
  experience: ExperienceItem[];
  languages: LanguageItem[];
  preferences: Preferences;
  [legacy: string]: unknown;
}

export interface AppConfig {
  sources: Sources;
  scan_interval_minutes: number;
  min_interval_minutes: number;
}

export interface ImportResult {
  imported: number;
  profile_restored: boolean;
  safety_copy: string | null;
  history_imported: number;
  history_skipped: number;
}

export interface Health {
  status: string;
  version: string;
  schema_version: number;
  statuses: Status[];
  scheduler: boolean;
}
