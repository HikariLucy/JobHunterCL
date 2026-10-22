"""Smoke real Linux del lanzador. Datos sintéticos en TemporaryDirectory.

Ejecutar desde la raíz: .venv/bin/python scripts/smoke_m14.py
No consulta fuentes externas. No lee ni modifica data/ ni CV.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='jobhunter-smoke-m14-') as directory:
        env = {**os.environ, 'JOBHUNTER_DATA_DIR': directory, 'JOBHUNTER_SCHEDULER': '1'}
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def request(path, body=None, **headers):
            req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                         method='GET' if body is None else 'PUT',
                                         headers={'Content-Type':'application/json', **headers})
            with opener.open(req, timeout=5) as response:
                return response.read(), response.headers

        def start():
            process = subprocess.Popen(['bash', 'iniciar-jobhunter.sh', '--no-browser', '--port', str(port)],
                                       cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise AssertionError(process.communicate()[0])
                try:
                    raw, _ = request('/api/health')
                    assert json.loads(raw)['status'] == 'ok'
                    return process
                except OSError:
                    time.sleep(.1)
            stop(process)
            raise AssertionError('Timeout de arranque')

        def stop(process):
            process.send_signal(signal.SIGINT)
            output, _ = process.communicate(timeout=10)
            assert process.returncode == 0, output
            assert 'JobHunter CL se ha cerrado.' in output, output
            with socket.socket() as sock:
                assert sock.connect_ex(('127.0.0.1', port)) != 0, 'El puerto sigue abierto'
            print('PASS cierre SIGINT: proceso terminado, puerto cerrado')

        process = start()
        try:
            # /proc describe el listener real del sistema, no solo la constante HOST.
            listeners = []
            for netfile in ('/proc/net/tcp', '/proc/net/tcp6'):
                for line in Path(netfile).read_text().splitlines()[1:]:
                    parts = line.split()
                    if parts[3] == '0A' and int(parts[1].split(':')[1], 16) == port:
                        listeners.append(parts[1].split(':')[0])
            assert listeners == ['0100007F'], listeners
            print('PASS listener real exclusivo 127.0.0.1')
            for route in ('/', '/perfil', '/ofertas', '/seguimiento', '/configuracion'):
                raw, headers = request(route)
                assert 'text/html' in headers['Content-Type'] and b'id="root"' in raw
            print('PASS frontend y 4 rutas profundas SPA')
            try:
                request('/api/health', Host='outside.invalid')
                raise AssertionError('Host externo aceptado')
            except urllib.error.HTTPError as exc:
                assert exc.code == 400
            status = json.loads(request('/api/profile/status')[0])
            assert not status['exists'] and status['new_profile']['sources']['getonbrd_api']
            profile = status['new_profile']
            profile.update(titles=['soporte ti'], skills=['linux'], locations=['chile'],
                           learning_skills=['rust'], education=[{'title':'Estudio sintético','status':'en_curso'}])
            request('/api/profile', profile)
            profile['titles'] = ['analista ti']
            request('/api/profile', profile)
            assert json.loads(request('/api/profile')[0])['titles'] == ['analista ti']
            assert json.loads((Path(directory)/'profile.json.bak').read_text())['titles'] == ['soporte ti']
            previous = (Path(directory)/'profile.json').read_bytes()
            try:
                request('/api/profile', {**profile, 'min_score':101})
                raise AssertionError('Perfil inválido aceptado')
            except urllib.error.HTTPError as exc:
                assert exc.code == 422
            assert (Path(directory)/'profile.json').read_bytes() == previous
            assert json.loads(request('/api/search/status')[0])['recent_runs'] == []
            print('PASS perfil nuevo, guardar/recargar, .bak, 422 sin modificación y sin búsquedas de inicio')
        finally:
            stop(process)
        # Sembrar oferta offline sin usar API de portales.
        import sys
        sys.path.insert(0, str(ROOT))
        from jobhunter.storage import connection, upsert_jobs
        db = connection(Path(directory)/'jobs.sqlite3')
        upsert_jobs(db, [{'source':'Fixture offline','title':'Analista TI Linux','company':'Empresa sintética',
                         'url':'https://example.org/synthetic', 'location':'Chile', 'description':'Linux'}])
        db.close()
        process = start()
        try:
            assert json.loads(request('/api/profile')[0])['titles'] == ['analista ti']
            jobs = json.loads(request('/api/jobs')[0])
            assert jobs['total'] == 1 and jobs['items'][0]['source'] == 'Fixture offline'
            assert json.loads(request('/api/search/status')[0])['recent_runs'] == []
            print('PASS reinicio: perfil persistido y oferta guardada disponible sin consultar portales')
        finally:
            stop(process)
    print('PASS smoke Linux: datos temporales eliminados')


if __name__ == '__main__':
    main()
