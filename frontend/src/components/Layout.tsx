import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "../api/client";

const NAV = [
  { to: "/", label: "Dashboard", icon: "▦" },
  { to: "/ofertas", label: "Explorar ofertas", icon: "⌕" },
  { to: "/seguimiento", label: "Seguimiento", icon: "☰" },
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
  useEffect(() => {
    let alive = true;
    if (!sessionStorage.getItem('jobhunter-onboarding-dismissed')) {
      api.profileStatus().then(status => {
        if (alive && !status.exists && status.readable) navigate('/perfil', {replace: true});
      }, () => { /* La página de perfil ofrece el error y reintento. */ });
    }
    return () => {alive = false;};
  }, [navigate]);
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
