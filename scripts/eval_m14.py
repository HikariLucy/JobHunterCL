"""Compara reglas M1.4 con HEAD de referencia usando solo ejemplos sintéticos.

Uso: .venv/bin/python scripts/eval_m14.py
"""
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jobhunter.matching import evaluate

old = {'__name__': 'm14_reference'}
exec(subprocess.check_output(['git', 'show', '614e394:jobhunter/matching.py'], text=True), old)

SCENARIOS = [
    ('Inicial soporte, modalidad desconocida', {'titles':['soporte ti'],'skills':['linux'],'locations':['chile'],'preferences':{'modalities':['remoto']}}, {'title':'Soporte TI N1/N2','description':'Linux','location':'Chile'}),
    ('Intermedio remoto confirmado', {'titles':['backend'],'skills':['python'],'locations':['chile'],'preferences':{'modalities':['remoto'],'seniority':['intermedio']}}, {'title':'Backend','description':'Nivel: Semi Senior · Python','location':'Remoto','geo':{'modality':'fully_remote'}}),
    ('Senior con años, perfil inicial', {'titles':['backend'],'skills':['python'],'locations':['chile']}, {'title':'Backend','description':'Nivel: Senior · Python. Requisito: 5+ años de experiencia','location':'Chile'}),
    ('Nivel estructurado Junior, título Senior', {'titles':['soporte ti'],'skills':['linux'],'locations':['chile']}, {'title':'Senior Soporte TI','description':'Nivel: Junior · Linux','location':'Chile'}),
    ('Idioma inferior y renta incomparable', {'titles':['analista'],'skills':['sql'],'locations':['chile'],'languages':[{'name':'English','level':'A2'}],'preferences':{'salary_min':800000,'salary_currency':'CLP'}}, {'title':'Analista','description':'SQL. English B2 required. Renta: 1000 - 1500 USD/mes','location':'Chile'}),
    ('Proyecto y aprendizaje, sin dominio supuesto', {'titles':['backend'],'skills':[],'locations':[],'learning_skills':['rust'],'experience':[{'role':'Laboratorio','kind':'proyecto'}]}, {'title':'Backend','description':'Obligatorio: Rust. Deseable: SQL.','location':'Remoto'}),
]

print('| Caso sintético | Antes | Después | Evidencia M1.4 |')
print('|---|---:|---:|---|')
for name, profile, job in SCENARIOS:
    before = old['evaluate'](job, profile)
    after = evaluate(job, profile)
    changed = [r for r in after[1] + after[2] if r not in before[1] + before[2]]
    print(f'| {name} | {before[0]} | {after[0]} | {"; ".join(changed) or "Sin mensajes nuevos; ver cambio de puntuación"} |')
