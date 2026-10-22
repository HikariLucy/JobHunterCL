"""Fixed bounded probes; capability failures skip integration, never fall back."""
from pathlib import Path
import pytest
from scripts import audit_sandbox as sandbox


def missing_test_capability(report):
    if report.get('reason') in ('missing_capability', 'fixture_socket_unavailable'):
        return True
    # Only this exact kernel permission rejection is an expected omission.
    # Invalid options, mounts, probe failures and build errors must fail CI.
    basic = report.get('checks', {}).get('basic', {})
    return (report.get('reason') == 'basic_failed' and basic.get('stdout') == '' and
            basic.get('stderr') == 'bwrap: Creating new namespace failed: Operation not permitted\n')


def test_synthetic_harness_rejects_arbitrary_programs():
    with pytest.raises(ValueError):
        sandbox.Scenario('/bin/sh')


@pytest.mark.parametrize('message', [
    'bwrap: Unknown option --broken\n',
    'bwrap: Can\'t bind mount input: No such file or directory\n',
    'failed line 51 errno 28\n',
])
def test_unknown_boundary_error_is_a_failure(message):
    report = {'reason': 'basic_failed', 'checks': {'basic': {'stderr': message, 'stdout': ''}}}
    assert not missing_test_capability(report)


def test_explicit_namespace_permission_failure_is_missing_capability():
    report = {'reason': 'basic_failed', 'checks': {'basic': {
        'stderr': 'bwrap: Creating new namespace failed: Operation not permitted\n', 'stdout': ''}}}
    assert missing_test_capability(report)


def test_missing_tool_blocks_without_starting_processes(monkeypatch):
    monkeypatch.setattr(sandbox, 'BWRAP', '/nonexistent-synthetic-bwrap')
    def forbidden(*args, **kwargs):
        pytest.fail('No subprocess permitted without required tools')
    monkeypatch.setattr(sandbox.subprocess, 'Popen', forbidden)
    report = sandbox.audit()
    assert report['status'] == 'blocked'
    assert report['reason'] == 'missing_capability'
    assert report['document_verified'] is False
    assert all(c['status'] == 'pending' for c in report['checks'].values())


def test_fixture_socket_failure_is_controlled_and_cleans_up(monkeypatch):
    def unavailable(*args, **kwargs):
        raise PermissionError('synthetic fixture socket denial')
    monkeypatch.setattr(sandbox.socket, 'socket', unavailable)
    report = sandbox.audit()
    if report.get('reason') == 'missing_capability':
        pytest.skip('Required build tools missing')
    assert report['status'] == 'blocked'
    assert report['reason'] == 'fixture_socket_unavailable'
    assert report['temporary_directory_removed'] is True
    assert not Path(report['temporary_directory']).exists()


def test_failed_boundary_never_runs_followup_probes(monkeypatch):
    invoked = []
    def unavailable(work, scenario, fixture_env):
        invoked.append(scenario)
        return {'status': 'failed', 'reason': 'synthetic-capability-failure'}
    monkeypatch.setattr(sandbox, '_run', unavailable)
    try:
        report = sandbox.audit()
    except PermissionError:
        pytest.skip('Host fixture sockets blocked by execution environment')
    if missing_test_capability(report):
        pytest.skip('Audit setup capability unavailable')
    assert invoked == [sandbox.Scenario.BASIC]
    assert report['status'] == 'blocked'
    assert report['document_verified'] is False
    assert all(report['checks'][s.value]['status'] == 'pending'
               for s in sandbox.Scenario if s != sandbox.Scenario.BASIC)
    assert report['temporary_directory_removed'] is True


@pytest.fixture(scope='module')
def audited():
    report = sandbox.audit()
    if report['status'] == 'blocked' and missing_test_capability(report):
        pytest.skip('Synthetic sandbox capability unavailable: ' + report['reason'])
    return report


@pytest.mark.parametrize('scenario', list(sandbox.Scenario))
def test_real_synthetic_isolation(audited, scenario):
    assert audited['checks'][scenario.value]['status'] == 'passed', audited
    assert audited['document_verified'] is False


def test_temporaries_removed(audited):
    assert audited['temporary_directory_removed'] is True
    assert not Path(audited['temporary_directory']).exists()
