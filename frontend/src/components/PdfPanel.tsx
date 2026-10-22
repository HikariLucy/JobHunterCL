import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { PdfCapabilities, PdfStatus, TailoringPlan } from '../api/types';
import { Card, ErrorBox, Loading, Notice } from './ui';

/** No preview URL is exposed until a backend can produce a verified PDF. */
export function PdfPanel({plan}: {plan: TailoringPlan}) {
  const [capability, setCapability] = useState<PdfCapabilities>();
  const [status, setStatus] = useState<PdfStatus>();
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let ignore = false;
    setLoading(true); setError(undefined); setStatus(undefined); setCapability(undefined);
    Promise.all([api.pdfCapabilities(), api.pdfStatus(plan)])
      .then(([cap, state]) => {if (!ignore) {setCapability(cap); setStatus(state);}})
      .catch(e => {if (!ignore) setError((e as Error).message);})
      .finally(() => {if (!ignore) setLoading(false);});
    return () => {ignore = true;};
  }, [plan.id, plan.revision, attempt]);
  return <Card title="PDF privado">
    {loading && <Loading label="Comprobando disponibilidad de PDF…"/>}
    {error && <ErrorBox error={error} onRetry={() => setAttempt(n => n + 1)}/>}
    {capability && <>
      {capability.reasons.map((reason, i) => <Notice key={i} tone="warning">{reason}</Notice>)}
      <p className="small muted">Herramientas detectadas: {capability.detected_tools.join(', ') || 'ninguna'}. Su presencia no verifica el aislamiento.</p>
    </>}
    <button className="btn" disabled aria-describedby="pdf-blocked">Generar PDF</button>
    <p id="pdf-blocked" className="muted">Generación no disponible. Puedes conservar y descargar la copia .tex verificada.</p>
    {status && <div aria-live="polite">
      <p>Estado: {status.status==='blocked' ? 'Bloqueado por aislamiento no verificado' : 'Sin PDF generado'} · Revisión {status.revision}</p>
      {status.tex_sha256 && <p className="cv-hash small">SHA-256 .tex: <code>{status.tex_sha256}</code></p>}
      {status.created_at && <p className="small">Último intento: {status.created_at}</p>}
      {status.attempt_id && <p className="cv-hash small">ID de intento: <code>{status.attempt_id}</code></p>}
      {status.diagnostics.map((message, i) => <Notice key={i} tone="warning">{message}</Notice>)}
    </div>}
    <p className="small muted">La revisión visual en el navegador y la descarga PDF se habilitarán cuando exista un resultado generado y verificado. No se ha comparado la maquetación.</p>
  </Card>;
}
