import database as db

projetos = db.obter_projetos()
print(f"=== {len(projetos)} PROJETOS NO BANCO ===")
for p in projetos:
    rotas = db.obter_rotas_projeto(p['id'])
    print(f"ID={p['id']} | {p['nome']} | tipo={p['tipo']} | {p['estufa']} | {p['data_inicio']} | fases={len(rotas)}")
    for r in rotas:
        conc = r.get('concomitante', 0) if isinstance(r, dict) else 0
        print(f"    Fase {r['fase']}: {r['recipiente']} | {r['meses']}m | {r['quantidade']} un | conc={conc}")
