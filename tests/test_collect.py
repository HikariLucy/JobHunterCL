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


# Fixture sintético con la estructura real del feed de Get on Board (formato <source><job>, 2026-10).
JOB_FEED = '''<?xml version="1.0" encoding="UTF-8"?>
<source version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <publisher>Get on Board</publisher>
  <job>
    <title>
      <![CDATA[Soporte TI Junior]]>
    </title>
    <date><![CDATA[2026-10-07 20:51:56 UTC]]></date>
    <url><![CDATA[https://www.getonbrd.com/jobs/sysadmin-devops-qa/soporte-ti-junior-ejemplo]]></url>
    <company><![CDATA[Empresa Ejemplo]]></company>
    <city><![CDATA[Santiago]]></city>
    <country><![CDATA[Chile]]></country>
    <description><![CDATA[<ul><li>Linux y redes</li></ul>]]></description>
    <content><![CDATA[<p>Somos una empresa de ejemplo.</p>]]></content>
    <jobtype><![CDATA[Full time]]></jobtype>
    <category><![CDATA[SysAdmin / DevOps / QA]]></category>
    <experience><![CDATA[Junior]]></experience>
    <salary><![CDATA[1000 - 1500 USD/mes]]></salary>
  </job>
  <job>
    <title><![CDATA[Backend Remoto]]></title>
    <url><![CDATA[https://www.getonbrd.com/jobs/programming/backend-remoto-ejemplo]]></url>
    <company><![CDATA[Otra Empresa]]></company>
    <country><![CDATA[Remoto]]></country>
    <description><![CDATA[<p>Python</p>]]></description>
  </job>
  <job><title><![CDATA[Sin URL segura]]></title><url><![CDATA[http://inseguro.test/x]]></url></job>
</source>'''.encode("utf-8")


def test_parse_current_getonbrd_job_feed():
    items = parse_getonbrd_rss(JOB_FEED)
    assert [i["title"] for i in items] == ["Soporte TI Junior", "Backend Remoto"]
    first = items[0]
    assert first["company"] == "Empresa Ejemplo"
    assert first["location"] == "Santiago, Chile"
    assert first["posted_at"] == "2026-10-07 20:51:56 UTC"
    assert first["description"].startswith("Nivel: Junior · Jornada: Full time · Categoría: SysAdmin / DevOps / QA · Renta: 1000 - 1500 USD/mes")
    assert "Linux y redes" in first["description"] and "<" not in first["description"]
    assert items[1]["location"] == "Remoto"


def test_unknown_feed_format_is_reported():
    with pytest.raises(ValueError, match="no reconocido"):
        parse_getonbrd_rss(b"<html><body>mantenimiento</body></html>")
