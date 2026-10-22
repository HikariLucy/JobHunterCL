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
  kind?: "" | "empleo" | "practica" | "proyecto" | "voluntariado";
}

export interface LanguageItem {
  name: string;
  level: string;
  evidence?: string;
}

export interface Preferences {
  modalities: string[];
  seniority: string[];
  salary_min: number | null;
  salary_currency: string;
  salary_period?: "mensual" | "anual";
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
  areas?: string[];
  learning_skills?: string[];
  skill_evidence?: { skill: string; evidence: string }[];
  education?: { title: string; institution: string; period: string; status: "" | "completado" | "en_curso" | "incompleto" }[];
  [legacy: string]: unknown;
}

export interface ProfileStatus {
  exists: boolean;
  readable: boolean;
  error: string | null;
  backup_available: boolean;
  new_profile: Profile;
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

/** M2.1: nunca contiene rutas internas. */
export interface CvMetadata {
  id: string; name: string; lang: 'es' | 'en'; sha256: string;
  imported_at: string; updated_at: string; size_bytes: number; is_primary: boolean;
}
export interface CvPreview {
  source: {id: string; lang: 'es' | 'en'; sha256: string; imported_at: string};
  source_text: string;
  sections: {key: string; kind: string; title: string; text: string; raw_tex: string; tex_span: [number, number]}[];
  skills: string[]; partial: boolean; warnings: string[];
  uninterpreted: {tex_span: [number, number]; raw_tex: string; reason: string}[];
}

export interface Requirement {
  text: string; kind: 'required'|'nice_to_have'|'unknown'; skill: string|null; category: string;
}
export interface JobAnalysis {
  job_id: string; title: string; company: string; lang: 'es'|'en'; description: string;
  description_sha256: string; requirements: Requirement[]; partial: boolean; warnings: string[];
}
export interface CvEvidence {section_key: string; quote: string; tex_span: [number,number]}
export interface CvSuggestion {
  id: string; action: 'reorder'|'emphasize'|'remove'|'gap'|'rephrase'; section_key: string;
  before: string; after: string|null; rationale: string; evidence: CvEvidence[];
  status: 'pending'|'accepted'|'rejected'; requirement_indices: number[]; tex_span: [number,number]|null;
}
export interface TailoringPlan {
  id: string; job_id: string; cv_id: string; cv_name: string; cv_sha256: string; lang: 'es'|'en';
  revision: number; state: 'review'|'generated'; analysis: JobAnalysis; coverage: number;
  suggestions: CvSuggestion[]; matches: {requirement_index: number; evidence: CvEvidence; confidence: string; rationale: string}[];
  blockers: string[]; cv_partial: boolean; cv_changed: boolean; job_changed: boolean; artifact_sha256: string|null;
}
export interface TailoringPreview {
  revision: number; original: string; result: string; diff: string; sha256: string; blockers: string[]; applied: string[];
}
