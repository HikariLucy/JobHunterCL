import type { ReactNode } from "react";
import type { Status } from "../api/types";
import { scoreLevel } from "../utils/format";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

export function Card({ title, children, actions, className = "" }: {
  title?: string; children: ReactNode; actions?: ReactNode; className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-head">
          {title && <h2>{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatCard({ label, value, hint, tone = "default" }: {
  label: string; value: ReactNode; hint?: string; tone?: "default" | "accent" | "success" | "warning";
}) {
  return (
    <div className={`stat stat-${tone}`}>
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{value}</strong>
      {hint && <span className="stat-hint">{hint}</span>}
    </div>
  );
}

export function StatusBadge({ status }: { status: Status | string }) {
  return <span className={`badge status-${String(status).toLowerCase()}`}>{status}</span>;
}

export function ScoreBadge({ score }: { score: number }) {
  return (
    <span className={`score score-${scoreLevel(score)}`} title="Puntuación orientativa (0–100)" aria-label={`Puntuación ${score} de 100`}>
      {score}
    </span>
  );
}

export function Loading({ label = "Cargando…" }: { label?: string }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      {label}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: Error | string; onRetry?: () => void }) {
  const message = typeof error === "string" ? error : error.message;
  return (
    <div className="alert alert-error" role="alert">
      <span>{message}</span>
      {onRetry && <button className="btn btn-small" onClick={onRetry}>Reintentar</button>}
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "success" | "warning"; children: ReactNode }) {
  return <div className={`alert alert-${tone}`} role={tone === "warning" ? "alert" : "status"}>{children}</div>;
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {children && <div className="muted">{children}</div>}
    </div>
  );
}

/** Envoltura estándar para datos asíncronos: carga → error → contenido. */
export function AsyncView<T>({ state, children, label }: {
  state: { data: T | undefined; error: Error | undefined; loading: boolean; reload: () => void };
  children: (data: T) => ReactNode;
  label?: string;
}) {
  if (state.error) return <ErrorBox error={state.error} onRetry={state.reload} />;
  if (state.data === undefined) return <Loading label={label} />;
  return <>{children(state.data)}</>;
}
