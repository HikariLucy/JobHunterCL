"""Pruebas offline del lanzador FastAPI + React."""
import os
import time
from unittest.mock import patch

import pytest

import start


def test_choose_port_skips_busy_ports():
    with patch("start.port_is_open", side_effect=[True, True, False]):
        assert start.choose_port(8765) == 8767


def test_choose_port_fails_when_exhausted():
    with patch("start.port_is_open", return_value=True), pytest.raises(RuntimeError, match="8765"):
        start.choose_port(8765)


def test_load_env_only_jobhunter_keys_and_no_override(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comentario\nJOBHUNTER_PORT=9000\nJOBHUNTER_DATA_DIR='/x'\nOTRA=1\n", encoding="utf-8")
    monkeypatch.delenv("JOBHUNTER_PORT", raising=False)
    monkeypatch.setenv("JOBHUNTER_DATA_DIR", "/ya-definido")
    monkeypatch.delenv("OTRA", raising=False)
    assert start.load_env(env) == {"JOBHUNTER_PORT": "9000"}
    assert os.environ["JOBHUNTER_DATA_DIR"] == "/ya-definido"
    assert "OTRA" not in os.environ


def test_frontend_needs_build_detects_missing_and_stale(tmp_path):
    (tmp_path / "src").mkdir()
    src = tmp_path / "src" / "App.tsx"
    src.write_text("x")
    assert start.frontend_needs_build(tmp_path)
    (tmp_path / "dist").mkdir()
    index = tmp_path / "dist" / "index.html"
    index.write_text("<html>")
    past = time.time() - 100
    os.utime(src, (past, past))
    assert not start.frontend_needs_build(tmp_path)
    os.utime(src, None)
    os.utime(index, (past - 10, past - 10))
    assert start.frontend_needs_build(tmp_path)


def test_host_is_loopback_only():
    assert start.HOST == "127.0.0.1"
