"""
Módulo de banco de dados SQLite para o sistema de capacidade de estufas.
Armazena: projetos, rotas, simulações, capacidades e histórico.
"""
import sqlite3
import os
import json
from datetime import datetime

# Caminho do banco de dados
DB_PATH = os.path.join(os.path.dirname(__file__), 'capacidade_estufa.db')


def get_connection():
    """Retorna conexão com o banco de dados."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Inicializa o banco de dados criando as tabelas necessárias."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabela de Projetos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projetos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            tipo TEXT,
            data_inicio DATE NOT NULL,
            estufa TEXT NOT NULL,
            ativo BOOLEAN DEFAULT 1,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de Rotas (fases de cada projeto)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rotas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            fase INTEGER NOT NULL,
            recipiente TEXT NOT NULL,
            meses INTEGER NOT NULL,
            quantidade INTEGER NOT NULL,
            concomitante INTEGER DEFAULT 0,
            FOREIGN KEY (projeto_id) REFERENCES projetos(id) ON DELETE CASCADE
        )
    ''')
    
    # Tabela de Simulações
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS simulacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            tipo_projeto TEXT,
            recipiente TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            tempo_meses INTEGER NOT NULL,
            estufa TEXT NOT NULL,
            data_inicio DATE,
            aceita BOOLEAN DEFAULT 0,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de Capacidades por Setor
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS capacidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            estufa TEXT NOT NULL,
            setor TEXT NOT NULL,
            recipiente TEXT NOT NULL,
            capacidade_m2 REAL NOT NULL,
            UNIQUE(estufa, setor, recipiente)
        )
    ''')
    
    # Tabela de Tamanhos de Recipientes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tamanho_recipientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipiente TEXT UNIQUE NOT NULL,
            tamanho_m2 REAL NOT NULL
        )
    ''')
    
    # Tabela de Histórico de Demanda (para relatórios)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico_demanda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER,
            projeto_nome TEXT NOT NULL,
            ano INTEGER NOT NULL,
            mes INTEGER NOT NULL,
            recipiente TEXT NOT NULL,
            estufa TEXT NOT NULL,
            demanda_unidades INTEGER NOT NULL,
            demanda_m2 REAL NOT NULL,
            consumido_m2 REAL,
            capacidade_m2 REAL,
            uso_pct REAL,
            calculado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (projeto_id) REFERENCES projetos(id)
        )
    ''')
    
    # Adicionar coluna data_inicio se não existir
    try:
        cursor.execute('ALTER TABLE simulacoes ADD COLUMN data_inicio DATE')
        conn.commit()
    except sqlite3.OperationalError:
        # Coluna já existe
        pass
    
    # Adicionar coluna concomitante se não existir
    try:
        cursor.execute('ALTER TABLE rotas ADD COLUMN concomitante INTEGER DEFAULT 0')
        conn.commit()
    except sqlite3.OperationalError:
        # Coluna já existe
        pass
    
    # Adicionar coluna estufa na tabela rotas (estufa por fase)
    try:
        cursor.execute('ALTER TABLE rotas ADD COLUMN estufa TEXT')
        conn.commit()
    except sqlite3.OperationalError:
        # Coluna já existe
        pass
    
    conn.commit()
    conn.close()
    print(f"Banco de dados inicializado em: {DB_PATH}")


# =====================================================
# FUNÇÕES DE PROJETOS
# =====================================================
def inserir_projeto(nome, tipo, data_inicio, estufa):
    """Insere um novo projeto no banco."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO projetos (nome, tipo, data_inicio, estufa, ativo)
            VALUES (?, ?, ?, ?, 1)
        ''', (nome, tipo, data_inicio, estufa))
        projeto_id = cursor.lastrowid
        conn.commit()
        return projeto_id
    except sqlite3.IntegrityError:
        # Projeto já existe, atualiza
        cursor.execute('''
            UPDATE projetos SET tipo=?, data_inicio=?, estufa=?, ativo=1, atualizado_em=CURRENT_TIMESTAMP
            WHERE nome=?
        ''', (tipo, data_inicio, estufa, nome))
        conn.commit()
        cursor.execute('SELECT id FROM projetos WHERE nome=?', (nome,))
        return cursor.fetchone()['id']
    finally:
        conn.close()


def obter_projetos():
    """Retorna todos os projetos ativos."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM projetos WHERE ativo=1 ORDER BY nome')
    projetos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return projetos


def obter_projeto_por_nome(nome):
    """Retorna um projeto ativo pelo nome."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM projetos WHERE nome=? AND ativo=1', (nome,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def remover_projeto(proj_id, excluir_permanente=False):
    """
    Remove um projeto.
    Se excluir_permanente=True, exclui do banco de dados.
    Se excluir_permanente=False, apenas desativa (mantém histórico).
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if excluir_permanente:
        # Excluir rotas primeiro (integridade referencial)
        cursor.execute('DELETE FROM rotas WHERE projeto_id=?', (proj_id,))
        # Excluir projeto
        cursor.execute('DELETE FROM projetos WHERE id=?', (proj_id,))
    else:
        # Apenas desativa (soft delete)
        cursor.execute('UPDATE projetos SET ativo=0 WHERE id=?', (proj_id,))
        # Também remove as rotas para evitar conflitos
        cursor.execute('DELETE FROM rotas WHERE projeto_id=?', (proj_id,))
    
    conn.commit()
    conn.close()


# =====================================================
# FUNÇÕES DE ROTAS
# =====================================================
def inserir_rota(projeto_id, fase, recipiente, meses, quantidade, concomitante=0, estufa=None):
    """
    Insere uma fase de rota para um projeto. estufa=None usa a estufa do projeto.
    Se já existir uma rota para o mesmo projeto+fase, atualiza ao invés de duplicar.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Verificar se já existe rota para este projeto+fase
    cursor.execute('SELECT id FROM rotas WHERE projeto_id=? AND fase=?', (projeto_id, fase))
    existente = cursor.fetchone()
    
    if existente:
        # Atualizar ao invés de duplicar
        cursor.execute('''
            UPDATE rotas 
            SET recipiente=?, meses=?, quantidade=?, concomitante=?, estufa=?
            WHERE projeto_id=? AND fase=?
        ''', (recipiente, meses, quantidade, concomitante, estufa, projeto_id, fase))
    else:
        # Inserir nova rota
        cursor.execute('''
            INSERT INTO rotas (projeto_id, fase, recipiente, meses, quantidade, concomitante, estufa)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (projeto_id, fase, recipiente, meses, quantidade, concomitante, estufa))
    
    conn.commit()
    conn.close()


def obter_rotas_projeto(projeto_id):
    """Retorna todas as fases de rota de um projeto."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM rotas WHERE projeto_id=? ORDER BY fase
    ''', (projeto_id,))
    rotas = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rotas


def obter_rotas_por_nome_projeto(nome_projeto):
    """Retorna as rotas de um projeto pelo nome."""
    projeto = obter_projeto_por_nome(nome_projeto)
    if projeto:
        return obter_rotas_projeto(projeto['id'])
    return []


def atualizar_rotas_projeto(projeto_id, fases):
    """Atualiza todas as fases de um projeto (delete + insert)."""
    conn = get_connection()
    cursor = conn.cursor()
    # Deletar rotas existentes
    cursor.execute('DELETE FROM rotas WHERE projeto_id=?', (projeto_id,))
    # Inserir novas
    for i, fase in enumerate(fases, 1):
        concomitante = fase.get('concomitante', 0)
        estufa = fase.get('estufa', None)
        cursor.execute('''
            INSERT INTO rotas (projeto_id, fase, recipiente, meses, quantidade, concomitante, estufa)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (projeto_id, i, fase['recipiente'], fase['meses'], fase['quantidade'], concomitante, estufa))
    conn.commit()
    conn.close()


def obter_todas_rotas():
    """Retorna todas as rotas com informações do projeto."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.nome as projeto_nome, p.tipo, p.data_inicio, p.estufa as projeto_estufa,
               r.fase, r.recipiente, r.meses, r.quantidade, r.concomitante,
               r.estufa as fase_estufa
        FROM projetos p
        JOIN rotas r ON p.id = r.projeto_id
        WHERE p.ativo = 1
        ORDER BY p.nome, r.fase
    ''')
    rotas = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rotas


# =====================================================
# FUNÇÕES DE SIMULAÇÕES
# =====================================================
def inserir_simulacao(nome, tipo_projeto, recipiente, quantidade, tempo_meses, estufa, data_inicio=None):
    """Insere uma nova simulação."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO simulacoes (nome, tipo_projeto, recipiente, quantidade, tempo_meses, estufa, data_inicio)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (nome, tipo_projeto, recipiente, quantidade, tempo_meses, estufa, data_inicio))
    sim_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return sim_id


def obter_simulacoes_pendentes():
    """Retorna simulações não aceitas."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM simulacoes WHERE aceita=0 ORDER BY criado_em DESC')
    sims = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return sims


def aceitar_simulacao(sim_id):
    """Marca uma simulação como aceita."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE simulacoes SET aceita=1 WHERE id=?', (sim_id,))
    conn.commit()
    conn.close()


def remover_simulacao(sim_id):
    """Remove uma simulação."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM simulacoes WHERE id=?', (sim_id,))
    conn.commit()
    conn.close()


def atualizar_simulacao(simulacao_id, estufa=None, recipiente=None, quantidade=None, tempo_meses=None, data_inicio=None):
    """Atualiza uma simulação existente com novos valores."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Construir query dinamicamente baseado nos campos fornecidos
    updates = []
    params = []
    
    if estufa is not None:
        updates.append("estufa = ?")
        params.append(estufa)
    if recipiente is not None:
        updates.append("recipiente = ?")
        params.append(recipiente)
    if quantidade is not None:
        updates.append("quantidade = ?")
        params.append(quantidade)
    if tempo_meses is not None:
        updates.append("tempo_meses = ?")
        params.append(tempo_meses)
    if data_inicio is not None:
        updates.append("data_inicio = ?")
        params.append(data_inicio)
    
    if updates:
        query = f"UPDATE simulacoes SET {', '.join(updates)} WHERE id = ?"
        params.append(simulacao_id)
        cursor.execute(query, params)
        conn.commit()
    
    conn.close()


def limpar_simulacoes_pendentes():
    """Remove todas as simulações não aceitas."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM simulacoes WHERE aceita=0')
    conn.commit()
    conn.close()


# =====================================================
# FUNÇÕES DE CAPACIDADES
# =====================================================
def inserir_capacidade(estufa, setor, recipiente, capacidade_m2):
    """Insere ou atualiza capacidade de um setor."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO capacidades (estufa, setor, recipiente, capacidade_m2)
        VALUES (?, ?, ?, ?)
    ''', (estufa, setor, recipiente, capacidade_m2))
    conn.commit()
    conn.close()


def obter_capacidades():
    """Retorna todas as capacidades."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM capacidades ORDER BY estufa, setor, recipiente')
    caps = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return caps


# =====================================================
# FUNÇÕES DE TAMANHO DE RECIPIENTES
# =====================================================
def inserir_tamanho_recipiente(recipiente, tamanho_m2):
    """Insere ou atualiza tamanho de um recipiente."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO tamanho_recipientes (recipiente, tamanho_m2)
        VALUES (?, ?)
    ''', (recipiente, tamanho_m2))
    conn.commit()
    conn.close()


def obter_tamanhos_recipientes():
    """Retorna todos os tamanhos de recipientes."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tamanho_recipientes')
    tams = {row['recipiente']: row['tamanho_m2'] for row in cursor.fetchall()}
    conn.close()
    return tams


# =====================================================
# FUNÇÕES DE HISTÓRICO
# =====================================================
def salvar_historico_demanda(dados_demanda):
    """Salva o histórico de demanda calculada."""
    conn = get_connection()
    cursor = conn.cursor()
    
    for dado in dados_demanda:
        cursor.execute('''
            INSERT INTO historico_demanda 
            (projeto_nome, ano, mes, recipiente, estufa, demanda_unidades, 
             demanda_m2, consumido_m2, capacidade_m2, uso_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            dado['projeto'], dado['ano'], dado['mes'], dado['recipiente'],
            dado['estufa'], dado['demanda_unidades'], dado['demanda_m2'],
            dado.get('consumido_m2'), dado.get('capacidade_m2'), dado.get('uso_pct')
        ))
    
    conn.commit()
    conn.close()


def obter_historico_demanda(ano=None, mes=None, estufa=None):
    """Retorna histórico de demanda com filtros opcionais."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = 'SELECT * FROM historico_demanda WHERE 1=1'
    params = []
    
    if ano:
        query += ' AND ano=?'
        params.append(ano)
    if mes:
        query += ' AND mes=?'
        params.append(mes)
    if estufa:
        query += ' AND estufa=?'
        params.append(estufa)
    
    query += ' ORDER BY ano, mes, estufa, recipiente, projeto_nome'
    
    cursor.execute(query, params)
    historico = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return historico


# =====================================================
# MIGRAÇÃO DE DADOS EXISTENTES
# =====================================================
def migrar_dados_existentes(projetos_df, rotas_config, capacidades_df, tamanho_recipientes):
    """Migra dados existentes (DataFrame/JSON) para o SQLite."""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("Migrando dados para SQLite...")
    
    # 1. Migrar tamanhos de recipientes
    for recipiente, tamanho in tamanho_recipientes.items():
        inserir_tamanho_recipiente(recipiente, tamanho)
    print(f"  - {len(tamanho_recipientes)} tamanhos de recipientes migrados")
    
    # 2. Migrar capacidades
    for _, row in capacidades_df.iterrows():
        inserir_capacidade(row['Estufa'], row.get('Setor', 'Geral'), 
                          row['Recipiente'], row['Capacidade_m2'])
    print(f"  - {len(capacidades_df)} capacidades migradas")
    
    # 3. Migrar projetos e rotas
    for _, proj in projetos_df.iterrows():
        nome = proj['Projeto']
        tipo = proj.get('Tipo', '')
        data_inicio = proj['Inicio'].strftime('%Y-%m-%d') if hasattr(proj['Inicio'], 'strftime') else str(proj['Inicio'])
        estufa = proj['Alocacao']
        
        projeto_id = inserir_projeto(nome, tipo, data_inicio, estufa)
        
        # Migrar rotas do projeto (do JSON)
        if nome in rotas_config:
            fases = rotas_config[nome].get('fases', [])
            for fase in fases:
                inserir_rota(projeto_id, fase.get('fase', 1), 
                           fase['recipiente'], fase['meses'], fase['quantidade'])
    
    print(f"  - {len(projetos_df)} projetos e suas rotas migrados")
    
    conn.close()
    print("Migração concluída!")


# =====================================================
# FUNÇÕES DE EXPORTAÇÃO
# =====================================================
def exportar_dados_excel():
    """Retorna todos os dados do banco em formato de dicionário para exportação."""
    dados = {
        'projetos': obter_projetos(),
        'rotas': obter_todas_rotas(),
        'simulacoes': obter_simulacoes_pendentes(),
        'capacidades': obter_capacidades(),
        'tamanhos': obter_tamanhos_recipientes()
    }
    return dados


# Inicializar banco ao importar o módulo
if not os.path.exists(DB_PATH):
    init_database()
