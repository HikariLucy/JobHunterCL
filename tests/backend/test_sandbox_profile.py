import pytest


def test_document_readiness_is_closed_and_profile_is_fixed(monkeypatch):
    from backend.services.pdf_sandbox import PROFILE, document_readiness, profile_sha256
    from backend.services.pdf_environment import capabilities
    monkeypatch.setenv('JOBHUNTER_PDF_ENABLED', 'true')
    monkeypatch.setenv('JOBHUNTER_SANDBOX_AUDITED', 'true')
    state = document_readiness()
    assert state.document_verified is False
    assert 'document_runner' in state.pending
    assert 'aggregate_resources' in state.pending
    assert len(profile_sha256()) == 64
    assert PROFILE.output_bytes == 1024 * 1024
    with pytest.raises(AttributeError):
        PROFILE.output_bytes = 0
    assert capabilities().available is False
