import pytest
from jobhunter.collect import parse_getonbrd_rss, valid_token, plain

RSS = b'''<?xml version="1.0"?><rss version="2.0"><channel><title>Trabajos</title>
<item><title>Soporte TI Junior</title><link>https://www.getonbrd.com/jobs/soporte-ti-junior</link>
<description><![CDATA[<p>Python y <b>SQL</b></p>]]></description></item>
</channel></rss>'''


def test_parse_public_feed():
    items = parse_getonbrd_rss(RSS)
    assert len(items) == 1
    assert items[0]["source"] == "Get on Board"
    assert "Python y SQL" in items[0]["description"]


def test_invalid_tokens():
    assert valid_token("ejemplo-tech")
    assert not valid_token("../../internal")
    assert not valid_token("https://evil.test")


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_null_nested_fields_do_not_break_connectors(monkeypatch):
    from jobhunter import collect
    payloads = {
        "greenhouse": {"jobs": [{"title": "Soporte", "absolute_url": "https://x.test/1", "location": None}]},
        "lever": [{"text": "Backend Jr", "hostedUrl": "https://x.test/2", "categories": None}],
    }
    monkeypatch.setattr(collect.SESSION, "get",
                        lambda url, **kw: _Resp(payloads["greenhouse" if "greenhouse" in url else "lever"]))
    assert collect.greenhouse("acme")[0]["location"] == ""
    assert collect.lever("acme")[0]["location"] == ""


def test_build_sources_respects_profile_flags():
    from jobhunter.collect import build_sources
    names = [n for n, _ in build_sources({"getonbrd": False, "remotive": True,
                                         "greenhouse_boards": ["acme"], "lever_sites": []})]
    assert names == ["Remotive", "Greenhouse/acme"]
