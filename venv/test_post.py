import urllib.parse
import urllib.request

data = urllib.parse.urlencode({
    'nome_projeto': 'TESTE_DEBUG2',
    'tipo_projeto': 'Pipeline GM',
    'estufa': 'CDV1',
    'data_inicio': '2026-01-01',
    'fase_0_recipiente': 'Citropote',
    'fase_0_meses': '6',
    'fase_0_quantidade': '900',
    'fase_0_concomitante': '3',
    'fase_1_recipiente': 'Bandeja',
    'fase_1_meses': '3',
    'fase_1_quantidade': '1170',
    'fase_1_concomitante': '0'
}).encode('utf-8')

req = urllib.request.Request('http://127.0.0.1:5000/rotas', data=data, method='POST')
try:
    response = urllib.request.urlopen(req)
    print('Status:', response.status)
    print('OK - projeto criado')
except Exception as e:
    print('Erro:', e)

# Agora verificar no banco
import sys
sys.path.insert(0, '.')
import database as db
projetos = db.obter_projetos()
for p in projetos:
    if 'TESTE' in p['nome'] or 'Pesquisa' in p['nome']:
        rotas = db.obter_rotas_projeto(p['id'])
        print(f"\n{p['nome']}: {len(rotas)} fases")
        for r in rotas:
            print(f"  Fase {r['fase']}: {r['recipiente']} {r['meses']}m {r['quantidade']}un conc={r.get('concomitante',0)}")
