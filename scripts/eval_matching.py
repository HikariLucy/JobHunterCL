"""Evalúa el matching sobre un snapshot local de ofertas (no se versiona).

Uso:
    python scripts/eval_matching.py SNAPSHOT.json [--profile PERFIL.json] [--details]
    python scripts/eval_matching.py --fetch SNAPSHOT.json   # 1 consulta al feed público de Get on Board

Etiquetas de referencia (reproducibles, sin revisión manual): los campos `Nivel` y
`Categoría` que Get on Board publica en cada oferta.
- relevante: nivel inicial (Junior / Sin experiencia requerida) y categoría técnica.
- dudosa:    Semi Senior y categoría técnica.
- resto:     no relevante para un perfil inicial de TI.
Advertencia: si el matching usa esos mismos campos, la métrica es en parte circular;
complementar siempre con la revisión de la lista de coincidencias (`--details`).
Perfil por defecto: `DEFAULT_PROFILE` (nunca el perfil personal).
"""
from __future__ import annotations
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobhunter.config import DEFAULT_PROFILE  # noqa: E402
from jobhunter.matching import evaluate, source_meta  # noqa: E402

ENTRY = {"junior", "sin experiencia requerida"}
TECH = {"programacion", "sysadmin / devops / qa", "data science / analytics", "machine learning / ai",
        "desarrollo mobile", "ciberseguridad", "soporte tecnico"}


def label(job: dict) -> str:
    meta = source_meta(job.get("description", ""))
    level, category = meta.get("level"), meta.get("category")
    if category not in TECH:
        return "no"
    if level in ENTRY:
        return "relevante"
    return "dudosa" if level == "semi senior" else "no"


def run(jobs: list[dict], profile: dict, threshold: int) -> dict:
    t0 = time.perf_counter()
    scored = [(evaluate(j, profile), j) for j in jobs]
    elapsed = time.perf_counter() - t0
    labels = [label(j) for _, j in scored]
    hits = [lab for ((s, _, _), _), lab in zip(scored, labels) if s >= threshold]
    relevant = labels.count("relevante")
    ranked = sorted(zip(scored, labels), key=lambda x: -x[0][0][0])
    top10 = [lab for _, lab in ranked[:10]]
    return {
        "ofertas": len(jobs),
        "sobre_umbral": len(hits),
        "precision": round(hits.count("relevante") / len(hits), 3) if hits else None,
        "precision_con_dudosas": round((hits.count("relevante") + hits.count("dudosa")) / len(hits), 3) if hits else None,
        "recall": round(hits.count("relevante") / relevant, 3) if relevant else None,
        "relevantes_total": relevant,
        "top10_relevantes": top10.count("relevante"),
        "top10_dudosas": top10.count("dudosa"),
        "puntaje_mediano": statistics.median(s for (s, _, _), _ in scored),
        "segundos": round(elapsed, 3),
        "_ranked": ranked,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("snapshot", type=Path)
    ap.add_argument("--profile", type=Path)
    ap.add_argument("--fetch", action="store_true", help="descargar el snapshot (una consulta)")
    ap.add_argument("--details", action="store_true", help="listar coincidencias y relevantes omitidas")
    args = ap.parse_args(argv)
    if args.fetch:
        from jobhunter.collect import getonbrd
        jobs = getonbrd()
        args.snapshot.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
        print(f"{len(jobs)} ofertas guardadas en {args.snapshot}")
        return 0
    jobs = json.loads(args.snapshot.read_text(encoding="utf-8"))
    profile = json.loads(args.profile.read_text(encoding="utf-8")) if args.profile else DEFAULT_PROFILE
    threshold = int(profile.get("min_score", 30))
    result = run(jobs, profile, threshold)
    ranked = result.pop("_ranked")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.details:
        print(f"\n== Puntaje >= {threshold} ==")
        for ((s, pos, warn), j), lab in ranked:
            if s >= threshold:
                print(f"{s:3} {lab:<9} {j['title'][:60]} | {'; '.join(pos)} | {'; '.join(warn)}")
        print("\n== Relevantes bajo el umbral ==")
        for ((s, pos, warn), j), lab in ranked:
            if s < threshold and lab == "relevante":
                print(f"{s:3} {j['title'][:60]} | {'; '.join(pos)} | {'; '.join(warn)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
