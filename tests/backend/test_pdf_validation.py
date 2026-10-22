import hashlib
import pytest
from backend.services.cv_store import CvError


def test_preliminary_pdf_envelope_is_not_structural_validation():
    from backend.services.pdf_validation import inspect_envelope
    data = b'%PDF-1.4\nsynthetic envelope only\n%%EOF\n'
    result = inspect_envelope(data)
    assert result['sha256'] == hashlib.sha256(data).hexdigest()
    assert result['size_bytes'] == len(data)
    assert result['structurally_verified'] is False
    assert result['pages'] is None


@pytest.mark.parametrize('data', [b'', b'not pdf', b'%PDF-1.4\nbroken', b'%PDF-1.4\n%%EOF\n'+b'x'*100])
def test_bad_or_large_pdf_envelope(data):
    from backend.services.pdf_validation import inspect_envelope
    with pytest.raises(CvError):
        inspect_envelope(data, max_bytes=80)
