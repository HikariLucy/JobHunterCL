"""Perfil vía API: estado para el asistente, campos M1.4 y errores sin éxito falso."""
import json

from jobhunter import config
from jobhunter.config import backup_path


def _write(settings, value):
    settings.profile_path.parent.mkdir(parents=True, exist_ok=True)
    text = value if isinstance(value, str) else json.dumps(value)
    settings.profile_path.write_text(text, encoding="utf-8")


def test_status_without_profile_offers_new_template_with_api_enabled(client, settings):
    body = client.get("/api/profile/status").json()
    assert body["exists"] is False and body["readable"] is True and body["backup_available"] is False
    template = body["new_profile"]
    assert template["titles"] == [] and template["skills"] == []  # nada supuesto
    assert template["sources"]["getonbrd_api"] is True and template["sources"]["getonbrd"] is True
    assert not settings.profile_path.exists()  # consultar el estado no crea archivos


def test_existing_profile_keeps_its_sources(client, settings):
    _write(settings, {"titles": ["soporte ti"], "sources": {"getonbrd": True, "remotive": False,
                                                            "greenhouse_boards": [], "lever_sites": []}})
    assert client.get("/api/profile/status").json()["exists"] is True
    assert client.get("/api/profile").json()["sources"]["getonbrd_api"] is False


def test_corrupt_profile_is_reported_and_left_untouched(client, settings):
    _write(settings, "{roto")
    status = client.get("/api/profile/status").json()
    assert status["exists"] is True and status["readable"] is False and "JSON" in status["error"]
    r = client.get("/api/profile")
    assert r.status_code == 500 and "dañado" in r.json()["detail"] and "PERFIL.md" in r.json()["detail"]
    # Guardar fuentes desde Configuración no puede pisar el archivo dañado con valores por defecto.
    assert client.put("/api/config", json={"sources": {"getonbrd": False}}).status_code == 500
    assert settings.profile_path.read_text(encoding="utf-8") == "{roto"


def test_new_fields_roundtrip(client, settings):
    p = client.get("/api/profile/status").json()["new_profile"]
    p.update(titles=["Soporte TI"], areas=["Soporte", "Infraestructura"], skills=["Linux"], learning_skills=["AWS"],
             skill_evidence=[{"skill": "Linux", "evidence": "Proyecto de título: servidor Ubuntu"}],
             experience=[{"role": "Técnico en práctica", "organization": "Municipalidad", "period": "2025",
                          "summary": "Mesa de ayuda", "kind": "practica"}],
             education=[{"title": "Ingeniería en Informática", "institution": "IP", "period": "2022–", "status": "en_curso"}],
             languages=[{"name": "Inglés", "level": "B1", "evidence": ""}])
    p["preferences"].update(modalities=["remoto", "híbrido"], seniority=["junior"], salary_min=900000,
                            salary_period="mensual")
    r = client.put("/api/profile", json=p)
    assert r.status_code == 200, r.text
    again = client.get("/api/profile").json()
    assert again["education"][0]["status"] == "en_curso" and again["experience"][0]["kind"] == "practica"
    assert again["learning_skills"] == ["AWS"] and again["skill_evidence"][0]["skill"] == "Linux"
    assert again["preferences"]["salary_period"] == "mensual"


def test_invalid_enums_are_rejected_without_writing(client, settings):
    _write(settings, {"titles": ["original"]})
    for patch in ({"education": [{"title": "X", "status": "titulado"}]},
                  {"experience": [{"role": "X", "kind": "senior"}]},
                  {"preferences": {"salary_period": "semanal"}}):
        assert client.put("/api/profile", json={"titles": ["nuevo"], **patch}).status_code == 422
    assert json.loads(settings.profile_path.read_text(encoding="utf-8"))["titles"] == ["original"]


def test_unknown_keys_only_survive_if_already_stored(client, settings):
    _write(settings, {"titles": ["a"], "custom_legacy": 1, "sources": {"getonbrd": True, "flag_mvp": True}})
    body = client.get("/api/profile").json()
    body["inyectado"] = {"x": "y"}
    body["sources"]["otro"] = True
    saved = client.put("/api/profile", json=body).json()
    on_disk = json.loads(settings.profile_path.read_text(encoding="utf-8"))
    assert on_disk["custom_legacy"] == 1 and on_disk["sources"]["flag_mvp"] is True
    assert "inyectado" not in on_disk and "otro" not in on_disk["sources"]
    assert "inyectado" not in saved


def test_write_failure_returns_error_and_keeps_previous(client, settings, monkeypatch):
    _write(settings, {"titles": ["original"]})

    def disk_full(src, dst):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(config.os, "replace", disk_full)
    r = client.put("/api/profile", json={"titles": ["nuevo"]})
    assert r.status_code == 500 and "se conservó la versión anterior" in r.json()["detail"]
    assert json.loads(settings.profile_path.read_text(encoding="utf-8"))["titles"] == ["original"]


def test_saves_keep_backup_of_previous_version(client, settings):
    client.put("/api/profile", json={"titles": ["v1"]})
    client.put("/api/profile", json={"titles": ["v2"]})
    assert json.loads(backup_path(settings.profile_path).read_text(encoding="utf-8"))["titles"] == ["v1"]
    assert client.get("/api/profile/status").json()["backup_available"] is True


def test_score_cache_follows_profile_changes(seeded):
    first = seeded.get("/api/jobs").json()["items"][0]
    profile = seeded.get("/api/profile").json()
    profile["titles"], profile["skills"] = ["contador"], ["excel"]
    seeded.put("/api/profile", json=profile)
    after = next(j for j in seeded.get("/api/jobs").json()["items"] if j["id"] == first["id"])
    assert after["score"] < first["score"]
