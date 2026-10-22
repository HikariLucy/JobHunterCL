import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";

const NAV = [
  { to: "/", label: "Dashboard", icon: "▦" },
  { to: "/ofertas", label: "Explorar ofertas", icon: "⌕" },
  { to: "/seguimiento", label: "Seguimiento", icon: "☰" },
  { to: "/cv", label: "Mis CV", icon: "▤" },
  { to: "/perfil", label: "Mi perfil", icon: "◉" },
  { to: "/configuracion", label: "Configuración", icon: "⚙" },
];

/** Indica si el backend local responde (los datos guardados funcionan sin internet). */
function useBackendOnline(): boolean | undefined {
  const [online, setOnline] = useState<boolean>();
  useEffect(() => {
    let alive = true;
    const check = () => api.health().then(() => alive && setOnline(true), () => alive && setOnline(false));
    check();
    const id = window.setInterval(check, 30000);
    return () => { alive = false; window.clearInterval(id); };
  }, []);
  return online;
}

export function Layout() {
  const online = useBackendOnline();
  const navigate = useNavigate();
  const location = useLocation();
  const onboarding = useRef<{
    location: typeof location;
    request?: ReturnType<typeof api.profileStatus>;
    finished: boolean;
  }>({ location, finished: false });
  useEffect(() => {
    const entry = onboarding.current;
    // Cualquier navegación cierra la oportunidad inicial, incluso al volver atrás.
    if (location !== entry.location) entry.finished = true;
    if (entry.finished || sessionStorage.getItem('jobhunter-onboarding-dismissed')) return;

    let alive = true;
    // Reutiliza la consulta cuando StrictMode repite setup/cleanup al montar.
    entry.request ??= api.profileStatus();
    entry.request.then(status => {
      if (!alive || entry.finished) return;
      entry.finished = true;
      if (!status.exists && status.readable && location.pathname !== '/perfil' &&
          !sessionStorage.getItem('jobhunter-onboarding-dismissed')) {
        navigate('/perfil', {replace: true});
      }
    }, () => {
      if (alive) entry.finished = true;
      /* La página de perfil ofrece el error y reintento. */
    });
    return () => {alive = false;};
  }, [location, navigate]);
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">JH</span>
          <span>JobHunter <small>CL</small></span>
        </div>
        <nav aria-label="Secciones">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === "/"} className="nav-link">
              <span className="nav-icon" aria-hidden="true">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className={`dot ${online === false ? "dot-off" : online ? "dot-on" : ""}`} aria-hidden="true" />
          {online === false ? "Servidor local detenido" : "Local · 127.0.0.1"}
        </div>
      </aside>
      <main className="content">
        {online === false && (
          <div className="alert alert-error" role="alert">
            El servidor local no responde. Vuelve a ejecutar el lanzador de JobHunter.
          </div>
        )}
        <Outlet />
      </main>
    </div>
  );
}
