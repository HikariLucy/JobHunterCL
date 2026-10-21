"""Compara el feed de Get on Board con su API pública (M1.2).

Uso:
    python scripts/compare_sources.py --fetch DIR   # 1 consulta al feed + 1 pasada del conector API
    python scripts/compare_sources.py DIR [--details]

`--fetch` guarda en DIR (fuera del repositorio): feed.json, api.json y requests.json.
Perfil: DEFAULT_PROFILE. Etiquetas (ver docs/ANALISIS_PUNTAJES.md):
- inicial:    nivel declarado Junior / Sin experiencia requerida y categoría técnica.
- compatible: por requisitos, no solo por nivel: categoría técnica, elegible desde las zonas
              del perfil, sin exigir más de 2 años, y nivel inicial o sin nivel declarado.
              (Una «Junior» que pide 3+ años NO es compatible.)
- dudosa:     técnica, elegible, Semi Senior y sin exigir más de 2 años (posible acceso).
"""
from __future__ import annotations
import argparse
import collections
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests  # noqa: E402

from jobhunter import collect  # noqa: E402
from jobhunter.config import DEFAULT_PROFILE  # noqa: E402
from jobhunter.matching import (contains, evaluate, is_place_list, location_terms, norm,  # noqa: E402
                                required_years, residency_restriction, source_meta)
from jobhunter.storage import job_id  # noqa: E402

TECH = {"programacion", "sysadmin / devops / qa", "data science / analytics", "machine learning / ai",
        "desarrollo mobile", "ciberseguridad", "soporte tecnico"}
ENTRY = {"junior", "sin experiencia requerida"}


class CountingSession(requests.Session):
    def __init__(self):
        super().__init__()
        self.headers["User-Agent"] = collect.UA
        self.log = []

    def request(self, method, url, **kw):
        r = super().request(method, url, **kw)
        self.log.append({"url": r.url, "status": r.status_code, "bytes": len(r.content),
                         "retry_after": r.headers.get("Retry-After"),
                         "ratelimit": {k: v for k, v in r.headers.items() if "ratelimit" in k.lower()}})
        return r


def fetch(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    session = CountingSession()
    t0 = time.perf_counter()
    r = session.get("https://www.getonbrd.com/jobs/feed", timeout=(6, 30))
    r.raise_for_status()
    feed = collect.parse_getonbrd_rss(r.content)
    t1 = time.perf_counter()
    stats = {}
    api = collect.getonbrd_api(session=session, stats=stats)
    t2 = time.perf_counter()
    (out / "feed.json").write_text(json.dumps(feed, ensure_ascii=False), encoding="utf-8")
    (out / "api.json").write_text(json.dumps(api, ensure_ascii=False), encoding="utf-8")
    (out / "requests.json").write_text(json.dumps({"log": session.log, "api_stats": stats,
                                                    "seconds": {"feed": round(t1 - t0, 1), "api": round(t2 - t1, 1)}},
                                                   indent=1), encoding="utf-8")
    print(f"feed: {len(feed)} ofertas, api: {len(api)} ofertas, peticiones: {len(session.log)} {stats}")


def facts(job: dict, profile: dict) -> dict:
    meta = source_meta(job.get("description", ""))
    loc = norm(job.get("location", ""))
    zones = location_terms(profile)
    restricted = residency_restriction(norm(job.get("description", "")), zones)
    outside = is_place_list(loc) and not any(contains(loc, z) for z in zones)
    years = required_years(norm(f"{job.get('title', '')} {job.get('description', '')}"))
    tech = meta["category"] in TECH
    eligible = not outside and not restricted
    return {"tech": tech, "inicial": tech and meta["level"] in ENTRY, "eligible": eligible, "years": years,
            "level": meta["level"],
            "compatible": tech and eligible and (years is None or years <= 2)
                          and (meta["level"] in ENTRY or meta["level"] is None),
            "dudosa": tech and eligible and (years is None or years <= 2) and meta["level"] == "semi senior"}


def years_bucket(y):
    return "sin exigencia" if y is None else ("1-2" if y <= 2 else ("3-4" if y <= 4 else "5+"))


def metrics(jobs: list[dict], profile: dict, threshold: int) -> dict:
    rows = [(evaluate(j, profile), facts(j, profile), j) for j in jobs]
    hits = [f for (s, _, _), f, _ in rows if s >= threshold]
    out = {"ofertas": len(rows), "tecnicas": sum(f["tech"] for _, f, _ in rows),
           "nivel_inicial": sum(f["inicial"] for _, f, _ in rows),
           "compatibles": sum(f["compatible"] for _, f, _ in rows),
           "dudosas": sum(f["dudosa"] for _, f, _ in rows),
           "inicial_que_pide_3_o_mas_anos": sum(f["inicial"] and (f["years"] or 0) >= 3 for _, f, _ in rows),
           "no_elegibles_desde_zonas": sum(not f["eligible"] for _, f, _ in rows),
           "experiencia_exigida": dict(collections.Counter(years_bucket(f["years"]) for _, f, _ in rows)),
           "sobre_umbral": len(hits)}
    for label in ("inicial", "compatible"):
        total = sum(f[label] for _, f, _ in rows)
        good = sum(f[label] for f in hits)
        out[f"precision_{label}"] = round(good / len(hits), 3) if hits else None
        out[f"recall_{label}"] = round(good / total, 3) if total else None
    out["precision_compatible_o_dudosa"] = (round(sum(f["compatible"] or f["dudosa"] for f in hits) / len(hits), 3)
                                            if hits else None)
    return out, rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", type=Path)
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--details", action="store_true")
    args = ap.parse_args(argv)
    if args.fetch:
        fetch(args.dir)
        return 0
    feed = json.loads((args.dir / "feed.json").read_text(encoding="utf-8"))
    api = json.loads((args.dir / "api.json").read_text(encoding="utf-8"))
    req = json.loads((args.dir / "requests.json").read_text(encoding="utf-8"))
    profile, threshold = DEFAULT_PROFILE, int(DEFAULT_PROFILE.get("min_score", 30))
    fids, aids = {job_id(j["url"]) for j in feed}, {job_id(j["url"]) for j in api}
    union = list({job_id(j["url"]): j for j in feed + api}.values())  # gana la API, como en la búsqueda
    report = {"solicitudes": {"feed": sum("jobs/feed" in r["url"] for r in req["log"]),
                              "api": sum("/api/v0/" in r["url"] for r in req["log"]),
                              "estados": dict(collections.Counter(r["status"] for r in req["log"])),
                              "cabeceras_de_limite": sorted({k for r in req["log"] for k in r["ratelimit"]}),
                              "api_stats": req.get("api_stats"), "segundos": req.get("seconds")},
              "solapamiento": {"feed": len(fids), "api": len(aids), "comunes": len(fids & aids),
                               "solo_feed": len(fids - aids), "solo_api": len(aids - fids), "union": len(union)}}
    details = {}
    for name, jobs in (("feed", feed), ("api", api), ("union", union)):
        report[name], details[name] = metrics(jobs, profile, threshold)
    only_api = [j for j in api if job_id(j["url"]) not in fids]
    only_feed = [j for j in feed if job_id(j["url"]) not in aids]
    report["solo_api"], _ = metrics(only_api, profile, threshold)
    report["solo_feed"], _ = metrics(only_feed, profile, threshold)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.details:
        for name in ("feed", "union"):
            print(f"\n== {name}: puntaje >= {threshold} ==")
            for (s, pos, warn), f, j in sorted(details[name], key=lambda x: -x[0][0]):
                if s >= threshold:
                    tag = "compatible" if f["compatible"] else ("dudosa" if f["dudosa"] else ("inicial" if f["inicial"] else "-"))
                    print(f"{s:3} {tag:<10} [{f['level']}] {j['title'][:55]} | {j['location'][:28]}")
        print("\n== union: compatibles bajo el umbral ==")
        for (s, pos, warn), f, j in sorted(details["union"], key=lambda x: -x[0][0]):
            if s < threshold and f["compatible"]:
                print(f"{s:3} [{f['level']}] {j['title'][:55]} | {'; '.join(warn)[:90]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
