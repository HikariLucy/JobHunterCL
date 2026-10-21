"""Pruebas offline del iniciador (sin instalar Streamlit)."""
import socket
from unittest.mock import patch

from launch import HOST, choose_port, port_is_open


def test_port_is_open_detects_listening_socket():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind((HOST, 0))
        server.listen(1)
        port = server.getsockname()[1]
        assert port_is_open(HOST, port)


def test_choose_port_skips_in_use():
    with patch("launch.port_is_open", side_effect=[True, False]):
        assert choose_port() == 8502


def test_choose_port_fails_when_all_are_in_use():
    with patch("launch.port_is_open", return_value=True):
        try:
            choose_port()
        except RuntimeError as exc:
            assert "8501" in str(exc)
        else:
            raise AssertionError("Se esperaba un error al agotar puertos")
