"""Inicio local comprobable de JobHunter CL: Streamlit + navegador.

Este lanzador no instala dependencias ni gestiona credenciales. Windows llama
al lanzador despues de comprobar el entorno; Linux puede usarlo tambien.
"""
from __future__ import annotations

import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

HOST = "127.0.0.1"
DEFAULT_PORT = 8501
READY_TIMEOUT = 45


def port_is_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def choose_port() -> int:
    """No confundir un servidor antiguo en 8501 con el actual."""
    for port in range(DEFAULT_PORT, DEFAULT_PORT + 20):
        if not port_is_open(HOST, port):
            return port
    raise RuntimeError("No hay puertos libres entre 8501 y 8520")


def launch() -> int:
    root = Path(__file__).resolve().parent
    if not (root / "app.py").is_file():
        print("[ERROR] No se encontro app.py junto a launch.py.", flush=True)
        return 2
    try:
        port = choose_port()
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", flush=True)
        return 2

    url = f"http://{HOST}:{port}"
    args = [
        sys.executable, "-m", "streamlit", "run", str(root / "app.py"),
        "--server.address", HOST,
        "--server.port", str(port),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    print(f"Abriendo servidor local en {url} ...", flush=True)
    try:
        process = subprocess.Popen(args, cwd=root)
    except OSError as exc:
        print(f"[ERROR] No se pudo iniciar Streamlit: {exc}", flush=True)
        return 2

    try:
        deadline = time.monotonic() + READY_TIMEOUT
        while time.monotonic() < deadline:
            if process.poll() is not None:
                print(f"[ERROR] Streamlit termino con codigo {process.returncode}.", flush=True)
                print("Lee el error que aparece mas arriba en esta consola.", flush=True)
                return process.returncode or 1
            if port_is_open(HOST, port):
                print(f"\nPanel listo: {url}", flush=True)
                try:
                    opened = webbrowser.open(url, new=2)
                except Exception as exc:
                    opened = False
                    print(f"No se pudo abrir el navegador automaticamente: {exc}", flush=True)
                if not opened:
                    print("Abre o copia manualmente la direccion anterior.", flush=True)
                print("Para cerrar el programa, pulsa Ctrl+C en esta consola.\n", flush=True)
                return process.wait()
            time.sleep(0.3)
        print("[ERROR] Streamlit no respondio en 45 segundos.", flush=True)
        print("Comprueba la salida anterior o revisa el antivirus/firewall.", flush=True)
        return 3
    except KeyboardInterrupt:
        print("\nCerrando JobHunter CL...", flush=True)
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    sys.exit(launch())
