"""Offline fixed synthetic audit. Run: python -m scripts.audit_sandbox

Not imported by HTTP execution paths. Accepts no document, program, path or flags.
Compiles only the repository's trusted C fixture; all probes run inside the same
mandatory boundary. A failed preflight prevents every remaining probe.
JSON is evidence for human review, never a certificate accepted by JobHunter.
"""
from __future__ import annotations
from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import socket
import subprocess
import tempfile
import time

from backend.services.pdf_sandbox import PROFILE, document_readiness, profile_sha256

BWRAP = '/usr/bin/bwrap'
PRLIMIT = '/usr/bin/prlimit'
CC = '/usr/bin/cc'
READELF = '/usr/bin/readelf'
SOURCE = Path(__file__).resolve().parent / 'fixtures' / 'sandbox_probe.c'


class Scenario(str, Enum):
    BASIC = 'basic'
    FILESYSTEM = 'filesystem'
    NETWORK = 'network'
    LIMITS = 'limits'
    QUOTA = 'quota'
    CPU = 'cpu'
    TIMEOUT = 'timeout'
    DESCENDANT = 'descendant'


def _command(work: Path, scenario: Scenario, fixture_env: dict[str, str]) -> list[str]:
    if not isinstance(scenario, Scenario):
        raise TypeError('Only fixed synthetic scenarios are accepted')
    p = PROFILE
    args = [PRLIMIT, f'--as={p.address_space_bytes}:{p.address_space_bytes}',
            f'--cpu={p.cpu_seconds}:{p.cpu_seconds}',
            f'--nproc={p.processes_per_uid}:{p.processes_per_uid}',
            f'--nofile={p.descriptors}:{p.descriptors}',
            f'--fsize={p.file_bytes}:{p.file_bytes}', '--core=0:0', '--', BWRAP]
    for ns in p.namespaces:
        args.append('--unshare-' + ns)
    args += ['--disable-userns', '--assert-userns-disabled', '--cap-drop', 'ALL',
             '--die-with-parent', '--new-session', '--clearenv',
             '--hostname', 'jobhunter-synthetic', '--tmpfs', '/',
             '--ro-bind', str(work / 'probe'), '/probe',
             '--ro-bind', str(work / 'input'), '/input',
             '--proc', '/proc', '--remount-ro', '/proc',
             '--size', str(p.output_bytes), '--tmpfs', '/out',
             '--remount-ro', '/', '--chdir', '/out']
    for key, value in sorted(fixture_env.items()):
        args += ['--setenv', key, value]
    return args + ['--', '/probe', scenario.value]


def _run(work: Path, scenario: Scenario, fixture_env: dict[str, str]) -> dict:
    command = _command(work, scenario, fixture_env)
    started = time.monotonic()
    # No shell, preexec_fn, inherited descriptors, environment or terminal.
    # PIPE is bounded by the fixed trusted probe's finite diagnostic output.
    with subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, close_fds=True, start_new_session=True,
                          env={'LC_ALL': 'C', 'PATH': '/usr/bin:/bin'}) as proc:
        timed_out = False
        try:
            stdout, stderr = proc.communicate(timeout=PROFILE.wall_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            # Killing the bwrap monitor also activates die-with-parent; PID
            # namespace teardown must close even a setsid child's inherited pipe.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # Monitor exited between timeout and kill; still drain.
            try:
                stdout, stderr = proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                # Never hang on an inherited pipe. A leaked child is an audit
                # failure (the fixed probe exits after 30 s independently).
                proc.stdout.close()
                proc.stderr.close()
                proc.wait(timeout=2)
                return {'status': 'failed', 'reason': 'descendant_pipe_survived',
                        'timed_out': True, 'elapsed_seconds': round(time.monotonic()-started, 3)}
    output = stdout.decode('utf-8', 'replace')
    if scenario in (Scenario.TIMEOUT, Scenario.DESCENDANT):
        passed = timed_out and 'parent-ready\n' in output
        if scenario == Scenario.DESCENDANT:
            passed = passed and 'child-ready\n' in output
    elif scenario == Scenario.CPU:
        passed = not timed_out and proc.returncode in (-signal.SIGKILL, 128 + signal.SIGKILL)
    else:
        passed = not timed_out and proc.returncode == 0 and output == f'ok:{scenario.value}\n'
    return {'status': 'passed' if passed else 'failed', 'exit_code': proc.returncode,
            'timed_out': timed_out, 'elapsed_seconds': round(time.monotonic()-started, 3),
            'stdout': output[:1024], 'stderr': stderr.decode('utf-8', 'replace')[:1024]}


def _audit() -> dict:
    report = {'schema': 1, 'synthetic_only': True, 'document_verified': False,
              'at_utc': datetime.now(timezone.utc).isoformat(),
              'platform': dict(zip(('system', 'node', 'release', 'version', 'machine'), os.uname())),
              'profile': asdict(PROFILE),
              'profile_sha256': profile_sha256(),
              'pending_document_controls': document_readiness().pending,
              'checks': {s.value: {'status': 'pending'} for s in Scenario}}
    missing = [p for p in (BWRAP, PRLIMIT, CC, READELF) if not os.access(p, os.X_OK)]
    if platform.system() != 'Linux' or missing:
        return {**report, 'status': 'blocked', 'reason': 'missing_capability', 'missing': missing}
    report['source_sha256'] = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    report['harness_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['tool_sha256'] = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
                             for p in (BWRAP, PRLIMIT, CC, READELF)}
    with tempfile.TemporaryDirectory(prefix='jobhunter-synthetic-') as directory, ExitStack() as stack:
        work = Path(directory)
        report['temporary_directory'] = directory
        build = subprocess.run([CC, '-static', '-O2', '-Wall', '-Wextra', '-Werror',
                                '-o', str(work/'probe'), str(SOURCE)],
                               stdin=subprocess.DEVNULL, capture_output=True, timeout=30,
                               env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}, close_fds=True)
        if build.returncode:
            return {**report, 'status': 'blocked', 'reason': 'static_build_unavailable',
                    'build_stderr': build.stderr.decode('utf-8', 'replace')[:1024]}
        elf = subprocess.run([READELF, '-l', str(work/'probe')],
                             capture_output=True, check=True, timeout=5)
        if b'INTERP' in elf.stdout or b'DYNAMIC' in elf.stdout:
            return {**report, 'status': 'blocked', 'reason': 'probe_not_static'}
        report['probe_sha256'] = hashlib.sha256((work/'probe').read_bytes()).hexdigest()
        (work/'input').write_bytes(b'synthetic-input\n')
        hidden = work/'not-mounted'
        hidden.write_bytes(b'disposable hidden fixture\n')
        # These listeners are fixtures owned by this invocation. Never access
        # preexisting host sockets or services. The child must fail to reach them.
        try:
            tcp = stack.enter_context(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        except PermissionError:
            report.update(status='blocked', reason='fixture_socket_unavailable')
            # TemporaryDirectory and ExitStack clean up even on this return.
            return report
        tcp.bind(('127.0.0.1', 0)); tcp.listen(1)
        unix = stack.enter_context(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM))
        unix.bind(str(work/'host.sock')); unix.listen(1)
        abstract = stack.enter_context(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM))
        abstract_name = work.name
        abstract.bind('\0' + abstract_name); abstract.listen(1)
        fixtures = {'FIXTURE_HIDDEN': str(hidden), 'FIXTURE_SOCKET': str(work/'host.sock'),
                    'FIXTURE_ABSTRACT': abstract_name, 'FIXTURE_PORT': str(tcp.getsockname()[1]),
                    'FIXTURE_NETNS': os.readlink('/proc/self/ns/net')}
        for ns in PROFILE.namespaces:
            fixtures['FIXTURE_NS_' + ns.upper()] = os.readlink('/proc/self/ns/' + ns)
        for scenario in Scenario:
            result = _run(work, scenario, fixtures)
            report['checks'][scenario.value] = result
            if result['status'] != 'passed':
                # No risky follow-up if the configured boundary is not proven.
                report.update(status='blocked', reason=f'{scenario.value}_failed')
                break
        else:
            report['status'] = 'synthetic_passed'
    return report


def audit() -> dict:
    report = _audit()
    # _audit has left all context managers, including early capability failures.
    if 'temporary_directory' in report:
        report['temporary_directory_removed'] = not Path(report['temporary_directory']).exists()
    return report


def main() -> int:
    import sys
    if len(sys.argv) != 1:
        raise SystemExit('This audit accepts no arguments, documents or commands.')
    try:
        report = audit()
    except (OSError, subprocess.SubprocessError) as exc:
        report = {'schema': 1, 'status': 'blocked', 'document_verified': False,
                  'reason': type(exc).__name__}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report['status'] == 'synthetic_passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
