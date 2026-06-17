import sys
sys.path.insert(0, 'venv')
import database as db

# Insert FwB Genitor default routes for project 22
fases = [
    {'recipiente': 'Citropote', 'meses': 5, 'quantidade': 360, 'concomitante': 0},
    {'recipiente': 'Bandeja', 'meses': 3, 'quantidade': 500, 'concomitante': 0},
    {'recipiente': 'Vaso', 'meses': 5, 'quantidade': 1280, 'concomitante': 0},
    {'recipiente': 'Bandeja', 'meses': 2, 'quantidade': 144, 'concomitante': 0},
]

db.atualizar_rotas_projeto(22, fases)

# Verify
rotas = db.obter_rotas_projeto(22)
print(f'Rotas inseridas: {len(rotas)}')
for r in rotas:
    print(dict(r))
