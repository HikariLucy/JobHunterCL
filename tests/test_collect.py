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
