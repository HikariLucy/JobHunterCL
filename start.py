"""Lanzador local de JobHunter CL (FastAPI + panel React).

Un solo proceso: uvicorn sirve la API y el frontend compilado en
http://127.0.0.1:<puerto>. Al pulsar Ctrl+C (o cerrar la consola) se
detienen el servidor y el programador de búsquedas. No instala servicios
del sistema ni abre puertos hacia la red.

Uso:
    python start.py                 # inicia y abre el navegador
    python start.py --no-browser    # solo servidor
    python start.py --build         # fuerza recompilar el frontend
"""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from launch import port_is_open

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
HOST = "127.0.0.1"
DEFAULT_PORT = 8765
READY_TIMEOUT = 45


def load_env(path: Path = ROOT / ".env") -> dict[str, str]:
    """Lee variables JOBHUNTER_* de un .env simple (sin sobrescribir el entorno)."""
    loaded = {}
    if not path.is_file():
        return loaded
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (s.strip() for s in line.split("=", 1))
        if key.startswith("JOBHUNTER_") and key not in os.environ:
            os.environ[key] = value.strip('"').strip("'")
            loaded[key] = os.environ[key]
    return loaded


def choose_port(start: int) -> int:
    for port in range(start, start + 20):
        if not port_is_open(HOST, port):
            return port
    raise RuntimeError(f"No hay puertos libres entre {start} y {start + 19}")


def frontend_needs_build(frontend: Path = FRONTEND) -> bool:
    """True si no hay compilado o si algún fuente es más nuevo que el compilado."""
    index = frontend / "dist" / "index.html"
    if not index.is_file():
        return True
    built = index.stat().st_mtime
    sources = [frontend / "index.html", frontend / "package.json", *(frontend / "src").rglob("*")]
    return any(p.is_file() and p.stat().st_mtime > built for p in sources)


def build_frontend(force: bool = False) -> bool:
    """Compila el frontend si hace falta. Devuelve False si no fue posible."""
    if not force and not frontend_needs_build():
        return True
    npm = shutil.which("npm")
    if npm is None:
        has_dist = (FRONTEND / "dist" / "index.html").is_file()
        print("[AVISO] No se encontró Node.js/npm; no se puede compilar el panel.", flush=True)
        print("        Instala Node.js 20+ (https://nodejs.org) o copia frontend/dist desde otro equipo.", flush=True)
        return has_dist
    steps = []
    if not (FRONTEND / "node_modules").is_dir():
        steps.append(([npm, "ci", "--no-audit", "--no-fund"], "Instalando dependencias del panel (solo la primera vez)..."))
    steps.append(([npm, "run", "build"], "Compilando el panel..."))
    for cmd, msg in steps:
        print(msg, flush=True)
        if subprocess.run(cmd, cwd=FRONTEND).returncode != 0:
            print("[ERROR] Falló: " + " ".join(cmd[1:]), flush=True)
            return (FRONTEND / "dist" / "index.html").is_file()
    return True


def open_browser_when_ready(url: str, stop: threading.Event) -> None:
    deadline = time.monotonic() + READY_TIMEOUT
    while time.monotonic() < deadline and not stop.is_set():
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=1) as r:
                if r.status == 200:
                    break
        except OSError:
            time.sleep(0.3)
    else:
        if not stop.is_set():
            print(f"[AVISO] El servidor tardó más de {READY_TIMEOUT} s. Abre {url} manualmente.", flush=True)
        return
    print(f"\nPanel listo: {url}", flush=True)
    print("Deja esta ventana abierta. Para cerrar JobHunter pulsa Ctrl+C.\n", flush=True)
    try:
        if not webbrowser.open(url, new=2):
            print("Abre manualmente la dirección anterior.", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"No se pudo abrir el navegador: {exc}", flush=True)


def main(argv: list[str] | None = None) -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Inicia JobHunter CL en este equipo (127.0.0.1).")
    parser.add_argument("--port", type=int, default=int(os.environ.get("JOBHUNTER_PORT", DEFAULT_PORT)))
    parser.add_argument("--no-browser", action="store_true", help="No abrir el navegador")
    parser.add_argument("--build", action="store_true", help="Forzar compilación del frontend")
    args = parser.parse_args(argv)

    try:
        import uvicorn
    except ImportError:
        print("[ERROR] Falta uvicorn/fastapi. Ejecuta: python -m pip install -r requirements.txt", flush=True)
        return 2

    if not build_frontend(force=args.build):
        print("[AVISO] Se iniciará solo la API (http://127.0.0.1:<puerto>/api/docs).", flush=True)
    try:
        port = choose_port(args.port)
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", flush=True)
        return 2

    url = f"http://{HOST}:{port}"
    print(f"Iniciando JobHunter CL en {url} ...", flush=True)
    stop = threading.Event()
    if not args.no_browser:
        threading.Thread(target=open_browser_when_ready, args=(url, stop), daemon=True).start()
    config = uvicorn.Config("backend.main:app", host=HOST, port=port, log_level="warning",
                            timeout_graceful_shutdown=5)
    server = uvicorn.Server(config)
    if hasattr(signal, "SIGBREAK"):
        # Windows: Ctrl+Pausa / cierre desde otro proceso -> mismo cierre ordenado que Ctrl+C.
        signal.signal(signal.SIGBREAK, lambda *_: setattr(server, "should_exit", True))
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
    print("JobHunter CL se ha cerrado.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
