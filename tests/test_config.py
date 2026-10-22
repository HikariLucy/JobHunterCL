"""Persistencia segura de data/profile.json (siempre en directorios temporales)."""
import json
import os

import pytest

from jobhunter import config
from jobhunter.config import (DEFAULT_PROFILE, ProfileCorrupt, ProfileWriteError, backup_path, load_profile,
                              profile_status, save_profile)


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_save_writes_valid_json_and_leaves_no_temp_files(tmp_path):
    path = tmp_path / "profile.json"
    save_profile({"titles": ["soporte ti"], "nombre": "Ñandú"}, path)
    assert _read(path) == {"titles": ["soporte ti"], "nombre": "Ñandú"}
    assert sorted(p.name for p in tmp_path.iterdir()) == ["profile.json"]  # sin .bak en la primera escritura


def test_second_save_keeps_previous_valid_version_as_bak(tmp_path):
    path = tmp_path / "profile.json"
    save_profile({"titles": ["v1"]}, path)
    save_profile({"titles": ["v2"]}, path)
    save_profile({"titles": ["v3"]}, path)
    assert _read(path)["titles"] == ["v3"]
    assert _read(backup_path(path))["titles"] == ["v2"]
    assert not [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]


def test_unserializable_profile_is_rejected_before_touching_disk(tmp_path):
    path = tmp_path / "profile.json"
    save_profile({"titles": ["bueno"]}, path)
    for bad in ({"x": object()}, {"x": float("nan")}, ["no es objeto"]):
        with pytest.raises(ProfileWriteError):
            save_profile(bad, path)
    assert _read(path)["titles"] == ["bueno"]
    assert not backup_path(path).exists()


def test_failed_replace_preserves_profile_and_cleans_temp(tmp_path, monkeypatch):
    path = tmp_path / "profile.json"
    save_profile({"titles": ["original"]}, path)
    real_replace = os.replace

    def fail_on_target(src, dst):
        if str(dst) == str(path):
            raise OSError(28, "No space left on device")
        return real_replace(src, dst)

    monkeypatch.setattr(config.os, "replace", fail_on_target)
    with pytest.raises(ProfileWriteError, match="se conservó la versión anterior"):
        save_profile({"titles": ["nuevo"]}, path)
    assert _read(path)["titles"] == ["original"]
    assert _read(backup_path(path))["titles"] == ["original"]  # la copia .bak sigue siendo válida
    assert not [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]


def test_failed_temp_write_preserves_profile_and_backup(tmp_path, monkeypatch):
    path = tmp_path / "profile.json"
    save_profile({"titles": ["v1"]}, path)
    save_profile({"titles": ["v2"]}, path)

    def disk_full(fd):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(config.os, "fsync", disk_full)
    with pytest.raises(ProfileWriteError):
        save_profile({"titles": ["v3"]}, path)
    assert _read(path)["titles"] == ["v2"]
    assert _read(backup_path(path))["titles"] == ["v1"]
    assert not [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]


def test_transient_permission_error_on_windows_is_retried(tmp_path, monkeypatch):
    path = tmp_path / "profile.json"
    save_profile({"titles": ["v1"]}, path)
    real_replace, calls = os.replace, []

    def flaky(src, dst):
        calls.append(dst)
        if len(calls) == 1:
            raise PermissionError(13, "Acceso denegado")
        return real_replace(src, dst)

    monkeypatch.setattr(config.os, "replace", flaky)
    monkeypatch.setattr(config.time, "sleep", lambda s: None)
    save_profile({"titles": ["v2"]}, path)
    assert _read(path)["titles"] == ["v2"]


@pytest.mark.parametrize("content", [b"{\"titles\": [", b"[1, 2]", b"\xff\xfe\x00basura", b""])
def test_corrupt_profile_raises_and_is_not_overwritten_on_load(tmp_path, content):
    path = tmp_path / "profile.json"
    path.write_bytes(content)
    with pytest.raises(ProfileCorrupt):
        load_profile(path)
    assert path.read_bytes() == content
    status = profile_status(path)
    assert status["exists"] and not status["readable"] and status["error"]


def test_explicit_save_over_corrupt_file_sets_damaged_copy_aside(tmp_path):
    path = tmp_path / "profile.json"
    save_profile({"titles": ["bueno"]}, path)
    save_profile({"titles": ["bueno 2"]}, path)
    path.write_text("{roto", encoding="utf-8")
    save_profile({"titles": ["nuevo"]}, path)
    assert _read(path)["titles"] == ["nuevo"]
    assert _read(backup_path(path))["titles"] == ["bueno"]  # la última copia válida no se sustituye por basura
    corrupt = [p for p in tmp_path.iterdir() if ".corrupt-" in p.name]
    assert len(corrupt) == 1 and corrupt[0].read_text(encoding="utf-8") == "{roto"


def test_status_of_missing_profile_and_backup(tmp_path):
    path = tmp_path / "profile.json"
    assert profile_status(path) == {"exists": False, "readable": True, "error": None, "backup_available": False}
    save_profile({"titles": ["a"]}, path)
    save_profile({"titles": ["b"]}, path)
    assert profile_status(path)["backup_available"] is True


def test_legacy_mvp_profile_loads_with_defaults_and_keeps_unknown_keys(tmp_path):
    path = tmp_path / "profile.json"
    legacy = {"titles": ["soporte ti"], "skills": ["linux"], "locations": ["santiago"], "min_score": 40,
              "sources": {"getonbrd": True, "remotive": False, "greenhouse_boards": [], "lever_sites": []},
              "clave_antigua": {"x": 1}}
    path.write_text(json.dumps(legacy), encoding="utf-8-sig")  # BOM de editores de Windows
    loaded = load_profile(path)
    assert loaded["clave_antigua"] == {"x": 1} and loaded["min_score"] == 40
    assert "getonbrd_api" not in loaded["sources"]  # no se activa la API en perfiles existentes
    save_profile(loaded, path)
    assert _read(path)["clave_antigua"] == {"x": 1}


def test_missing_profile_returns_independent_defaults(tmp_path):
    a = load_profile(tmp_path / "no.json")
    a["titles"].append("x")
    assert load_profile(tmp_path / "no.json") == DEFAULT_PROFILE


@pytest.mark.parametrize('value', [{'titles': 'python'}, {'skills': [None]}, {'sources': []},
                                  {'preferences': 'remote'}, {'min_score': 101}])
def test_semantically_invalid_profile_is_corrupt(tmp_path, value):
    path = tmp_path / 'profile.json'
    path.write_text(json.dumps(value))
    assert profile_status(path)['readable'] is False
    with pytest.raises(ProfileCorrupt):
        load_profile(path)
    before = path.read_bytes()
    with pytest.raises(ProfileWriteError):
        save_profile(value, path)
    assert path.read_bytes() == before


@pytest.mark.parametrize('invalid', [
    {'preferences': {'salary_min': 'bad'}}, {'sources': {'greenhouse_boards': None}},
    {'languages': [{'name': 123}]}, {'education': [{'title':'Estudio','status':'inventado'}]},
    {'experience': [{'role':'Cargo','kind':'inventado'}]}, {'preferences': {'modalities': [123]}},
])
def test_nested_corruption_cannot_replace_good_backup(tmp_path, invalid):
    path = tmp_path / 'profile.json'
    save_profile({'titles':['bueno']}, path)
    save_profile({'titles':['otro']}, path)
    path.write_text(json.dumps(invalid))
    assert not profile_status(path)['readable']
    with pytest.raises(ProfileWriteError):
        save_profile(invalid, path)
    save_profile({'titles':['recuperado']}, path)
    assert _read(backup_path(path)) == {'titles':['bueno']}
