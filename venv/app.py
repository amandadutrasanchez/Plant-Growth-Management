from flask import Flask, render_template, request, send_file, redirect, url_for, flash, jsonify
import pandas as pd
import numpy as np
import json
import os
from dateutil.relativedelta import relativedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors

# Importar módulo de banco de dados
import database as db

# Importar módulo de Agente de IA para otimização
import agente_ia

app = Flask(__name__)
app.secret_key = 'capacidade_estufa_secret_key_2026'

# Caminho do arquivo de configuração de rotas personalizadas (legado)
ROTAS_CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'rotas_config.json')

# =====================================================
# REFATORAÇÃO PARA MODELO BASEADO EM METROS QUADRADOS (m²)
# 
# MUDANÇA CONCEITUAL:
# - ANTES: Capacidade = quantidade de recipientes (unidades)
# - DEPOIS: Capacidade = área ocupada (m²)
#
# Esta refatoração permite análise mais precisa da ocupação física
# das estufas, respeitando o tamanho real de cada tipo de recipiente
# e a disponibilidade de espaço em metros quadrados.
# =====================================================

# =====================================================
# 📐 DADOS FÍSICOS DOS RECIPIENTES (METROS QUADRADOS)
# =====================================================
# Define o tamanho físico de cada tipo de recipiente em m²
tamanho_recipientes = {
    "Bandeja": 0.16,      # m² por bandeja
    "Citropote": 0.02,    # m² por citropote
    "Vaso": 0.3           # m² por vaso
}

# =====================================================
# �️ REGRAS FÍSICAS DE ARMAZENAMENTO
# =====================================================
# - Bandejas e Citropotes são armazenados em MESAS
# - Vasos são armazenados em BLOCOS
# - Cada BLOCO contém exatamente 4 vasos
# =====================================================

# =====================================================
# 📏 INFRAESTRUTURA FÍSICA POR SETOR
# =====================================================
# Dados reais de mesas e blocos por estufa/setor
# Tamanho da mesa CDV1: 2,24 m²  |  Tamanho da mesa CDV9: 2,88 m²
# Tamanho do bloco (ambas): 1,2 m² (comporta 4 vasos)

TAMANHO_MESA_CDV1 = 2.24  # m² por mesa
TAMANHO_MESA_CDV9 = 2.88  # m² por mesa
TAMANHO_BLOCO = 1.2       # m² por bloco
VASOS_POR_BLOCO = 4       # cada bloco contém 4 vasos

# Infraestrutura física por setor
infraestrutura_setores = pd.DataFrame([
    # ===== CDV1 =====
    # Setores com MESAS (para Bandejas e Citropotes)
    {"Estufa": "CDV1", "Setor": "1-A1", "Tipo": "Mesa", "Quantidade": 34, "Tamanho_unitario": 2.24, "Ocupacao_m2": 76.16},
    {"Estufa": "CDV1", "Setor": "1-A2", "Tipo": "Mesa", "Quantidade": 68, "Tamanho_unitario": 2.24, "Ocupacao_m2": 152.32},
    {"Estufa": "CDV1", "Setor": "5", "Tipo": "Mesa", "Quantidade": 8, "Tamanho_unitario": 2.24, "Ocupacao_m2": 17.92},
    {"Estufa": "CDV1", "Setor": "8", "Tipo": "Mesa", "Quantidade": 27, "Tamanho_unitario": 2.24, "Ocupacao_m2": 60.48},
    # Setores com BLOCOS (para Vasos - 4 vasos por bloco)
    {"Estufa": "CDV1", "Setor": "2", "Tipo": "Bloco", "Quantidade": 152, "Tamanho_unitario": 1.2, "Ocupacao_m2": 182.4},
    {"Estufa": "CDV1", "Setor": "3", "Tipo": "Bloco", "Quantidade": 168, "Tamanho_unitario": 1.2, "Ocupacao_m2": 201.6},
    {"Estufa": "CDV1", "Setor": "4", "Tipo": "Bloco", "Quantidade": 104, "Tamanho_unitario": 1.2, "Ocupacao_m2": 124.8},
    {"Estufa": "CDV1", "Setor": "6", "Tipo": "Bloco", "Quantidade": 112, "Tamanho_unitario": 1.2, "Ocupacao_m2": 134.4},
    {"Estufa": "CDV1", "Setor": "7", "Tipo": "Bloco", "Quantidade": 120, "Tamanho_unitario": 1.2, "Ocupacao_m2": 144.0},
    {"Estufa": "CDV1", "Setor": "9", "Tipo": "Bloco", "Quantidade": 116, "Tamanho_unitario": 1.2, "Ocupacao_m2": 139.2},
    {"Estufa": "CDV1", "Setor": "10", "Tipo": "Bloco", "Quantidade": 116, "Tamanho_unitario": 1.2, "Ocupacao_m2": 139.2},
    
    # ===== CDV9 =====
    # Setores com MESAS (para Bandejas e Citropotes)
    {"Estufa": "CDV9", "Setor": "1", "Tipo": "Mesa", "Quantidade": 50, "Tamanho_unitario": 2.88, "Ocupacao_m2": 144.0},
    {"Estufa": "CDV9", "Setor": "2", "Tipo": "Mesa", "Quantidade": 10, "Tamanho_unitario": 2.88, "Ocupacao_m2": 28.8},
    {"Estufa": "CDV9", "Setor": "3", "Tipo": "Mesa", "Quantidade": 42, "Tamanho_unitario": 2.88, "Ocupacao_m2": 120.96},
    {"Estufa": "CDV9", "Setor": "4", "Tipo": "Mesa", "Quantidade": 60, "Tamanho_unitario": 2.88, "Ocupacao_m2": 172.8},
    {"Estufa": "CDV9", "Setor": "5", "Tipo": "Mesa", "Quantidade": 28, "Tamanho_unitario": 2.88, "Ocupacao_m2": 80.64},
    {"Estufa": "CDV9", "Setor": "6", "Tipo": "Mesa", "Quantidade": 24, "Tamanho_unitario": 2.88, "Ocupacao_m2": 69.12},
    # Setores com BLOCOS (para Vasos - 4 vasos por bloco)
    {"Estufa": "CDV9", "Setor": "7", "Tipo": "Bloco", "Quantidade": 116, "Tamanho_unitario": 1.2, "Ocupacao_m2": 139.2},
    {"Estufa": "CDV9", "Setor": "8", "Tipo": "Bloco", "Quantidade": 116, "Tamanho_unitario": 1.2, "Ocupacao_m2": 139.2},
    {"Estufa": "CDV9", "Setor": "9", "Tipo": "Bloco", "Quantidade": 116, "Tamanho_unitario": 1.2, "Ocupacao_m2": 139.2},
    {"Estufa": "CDV9", "Setor": "10", "Tipo": "Bloco", "Quantidade": 116, "Tamanho_unitario": 1.2, "Ocupacao_m2": 139.2},
])

# =====================================================
# 🧮 CÁLCULO AUTOMÁTICO DE CAPACIDADE POR SETOR
# =====================================================
# Regras:
# - MESA: pode armazenar Bandejas OU Citropotes (capacidade exclusiva)
# - BLOCO: armazena apenas Vasos (4 vasos por bloco)
# =====================================================

def calcular_capacidade_por_setor():
    """
    Calcula a capacidade de recipientes por setor baseado na infraestrutura.
    
    Mesas: capacidade em m² (Bandejas e Citropotes compartilham as mesas, mas são calculados separadamente)
    Blocos: capacidade em vasos (4 por bloco) convertida para m²
    """
    import math
    capacidade_list = []
    
    for _, row in infraestrutura_setores.iterrows():
        estufa = row["Estufa"]
        setor = row["Setor"]
        tipo = row["Tipo"]
        quantidade = row["Quantidade"]
        ocupacao_m2 = row["Ocupacao_m2"]
        
        if tipo == "Mesa":
            # Mesas armazenam Bandejas e Citropotes
            # Capacidade em m² é a ocupação total das mesas
            # Bandejas: ocupacao_m2 (área total disponível)
            # Citropotes: ocupacao_m2 (área total disponível)
            # NOTA: Bandejas e Citropotes COMPARTILHAM as mesas!
            
            capacidade_list.append({
                "Estufa": estufa,
                "Setor": setor,
                "Recipiente": "Bandeja",
                "Capacidade_m2": ocupacao_m2,
                "Qtd_mesas": quantidade,
                "Tipo_infra": "Mesa"
            })
            capacidade_list.append({
                "Estufa": estufa,
                "Setor": setor,
                "Recipiente": "Citropote",
                "Capacidade_m2": ocupacao_m2,
                "Qtd_mesas": quantidade,
                "Tipo_infra": "Mesa"
            })
            
        elif tipo == "Bloco":
            # Blocos armazenam Vasos (4 vasos por bloco)
            qtd_vasos = quantidade * VASOS_POR_BLOCO
            capacidade_m2_vasos = qtd_vasos * tamanho_recipientes["Vaso"]
            
            capacidade_list.append({
                "Estufa": estufa,
                "Setor": setor,
                "Recipiente": "Vaso",
                "Capacidade_m2": capacidade_m2_vasos,
                "Qtd_blocos": quantidade,
                "Qtd_vasos": qtd_vasos,
                "Tipo_infra": "Bloco"
            })
    
    return pd.DataFrame(capacidade_list)

# Gerar tabela de capacidade baseada na infraestrutura
capacidade_por_setor_raw = calcular_capacidade_por_setor()

# =====================================================
# 📊 RESUMO DA INFRAESTRUTURA
# =====================================================
# CDV1 Mesas: 34 + 68 + 8 + 27 = 137 mesas (306.88 m²)
# CDV1 Blocos: 152 + 168 + 104 + 112 + 120 + 116 + 116 = 888 blocos (1065.6 m²) = 3552 vasos
#
# CDV9 Mesas: 50 + 10 + 42 + 60 + 28 + 24 = 214 mesas (616.32 m²)
# CDV9 Blocos: 116 * 4 = 464 blocos (556.8 m²) = 1856 vasos
# =====================================================

# =====================================================
# 🔄 FUNÇÕES DE CONVERSÃO: QUANTIDADE ↔ METROS QUADRADOS
# =====================================================
def quantidade_para_m2(quantidade, tipo_recipiente):
    """
    Converte quantidade de recipientes para m² ocupados.
    
    Args:
        quantidade: número de recipientes
        tipo_recipiente: "Bandeja", "Citropote" ou "Vaso"
    
    Returns:
        m² ocupados
    """
    return quantidade * tamanho_recipientes.get(tipo_recipiente, 0)

def m2_para_quantidade(area_m2, tipo_recipiente):
    """
    Converte m² para quantidade de recipientes (arredonda para cima).
    
    Args:
        area_m2: área em m²
        tipo_recipiente: "Bandeja", "Citropote" ou "Vaso"
    
    Returns:
        quantidade de recipientes (inteiro arredondado para cima)
    """
    import math
    tamanho = tamanho_recipientes.get(tipo_recipiente, 1)
    return math.ceil(area_m2 / tamanho)

# =====================================================
# 📊 CONSTRUÇÃO DA TABELA DE CAPACIDADE (JÁ EM m²)
# =====================================================
# REGRAS DE COMPARTILHAMENTO:
# - MESAS: Bandejas e Citropotes COMPARTILHAM o mesmo espaço (ocupação conjunta)
# - BLOCOS: Vasos usam capacidade independente (não compartilham com mesas)
#
# Capacidades Calculadas (baseadas na infraestrutura):
# CDV1: 137 mesas (306.88 m²) + 888 blocos (1065.6 m² / 3552 vasos)
# CDV9: 214 mesas (616.32 m²) + 464 blocos (556.8 m² / 1856 vasos)
# =====================================================

# Consolidar por estufa e recipiente (soma de todos setores)
capacidade = capacidade_por_setor_raw.groupby(
    ["Estufa", "Recipiente"]
).agg({
    "Capacidade_m2": "sum"
}).reset_index()
capacidade.rename(columns={"Capacidade_m2": "Capacidade"}, inplace=True)

# =====================================================
# CAPACIDADE DE MESAS POR ESTUFA (Bandeja + Citropote COMPARTILHAM)
# CAPACIDADE DE BLOCOS POR ESTUFA (Vasos independentes)
# =====================================================
# Calcular capacidade de mesas por estufa (usando infraestrutura)
capacidade_mesas_estufa = infraestrutura_setores[
    infraestrutura_setores["Tipo"] == "Mesa"
].groupby("Estufa")["Ocupacao_m2"].sum().to_dict()
# Ex: {"CDV1": 306.88, "CDV9": 616.32}

# Calcular capacidade de blocos (vasos) por estufa
capacidade_blocos_estufa = {}
for estufa in infraestrutura_setores["Estufa"].unique():
    blocos_estufa = infraestrutura_setores[
        (infraestrutura_setores["Estufa"] == estufa) & 
        (infraestrutura_setores["Tipo"] == "Bloco")
    ]
    if not blocos_estufa.empty:
        total_blocos = blocos_estufa["Quantidade"].sum()
        total_vasos = total_blocos * VASOS_POR_BLOCO
        capacidade_blocos_estufa[estufa] = total_vasos * tamanho_recipientes["Vaso"]
    else:
        capacidade_blocos_estufa[estufa] = 0
# Ex: {"CDV1": 1065.6, "CDV9": 556.8}

# Capacidade total por estufa (mesas + blocos)
capacidade_total_estufa = {
    est: capacidade_mesas_estufa.get(est, 0) + capacidade_blocos_estufa.get(est, 0)
    for est in infraestrutura_setores["Estufa"].unique()
}
# Ex: {"CDV1": 1372.48, "CDV9": 1173.12}

# =====================================================
# PROJETOS — GERENCIADOS EXCLUSIVAMENTE PELO BANCO DE DADOS
# =====================================================
# Todos os projetos são criados/editados na página "Projetos & Rotas" (/rotas)
# e armazenados no SQLite (tabela projetos + rotas).
# O DataFrame hardcoded foi removido — o sistema agora é 100% baseado no DB.

# =====================================================
# ROTAS PADRÃO (BASE)
# =====================================================
# Rotas padrão por tipo de projeto
# Formato: [(recipiente, meses, quantidade, concomitante), ...]
# concomitante = meses extras que a fase se perdura junto com a próxima fase
rotas_padrao = {
    "Pipeline GM": [("Citropote", 6, 900, 3), ("Bandeja", 3, 1170, 0), ("Vaso", 10, 1000, 0)],
    "Fast Track": [("Vaso", 6, 2000, 0), ("Citropote", 6, 12240, 3), ("Bandeja", 3, 650, 0)],
    " PoT": [("Citropote", 6, 1250, 3), ("Bandeja", 3, 625, 0)],
    "FwB Genitor": [("Citropote", 5, 360, 0), ("Bandeja", 3, 500, 0), ("Vaso", 5, 1280, 0), ("Bandeja", 2, 144, 0)],
    "Produção MGC": [("Bandeja", 4, 150, 0)],
    "PROD PALMITO": [("Citropote", 6, 7560, 0)]
}

# =====================================================
# FUNÇÕES PARA GERENCIAR ROTAS PERSONALIZADAS
# =====================================================
def carregar_rotas_config():
    """Carrega configuração de rotas personalizadas do arquivo JSON."""
    if os.path.exists(ROTAS_CONFIG_FILE):
        try:
            with open(ROTAS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def salvar_rotas_config(config):
    """Salva configuração de rotas personalizadas no arquivo JSON."""
    with open(ROTAS_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def obter_rota_projeto(nome_projeto, tipo_projeto):
    """
    Obtém a rota para um projeto específico.
    Primeiro verifica se há rota personalizada, senão usa a padrão.
    Retorna lista de tuplas: (recipiente, meses, quantidade, concomitante)
    """
    config = carregar_rotas_config()
    
    # Se existe rota personalizada para este projeto
    if nome_projeto in config:
        return [(f["recipiente"], f["meses"], f["quantidade"], f.get("concomitante", 0)) for f in config[nome_projeto]["fases"]]
    
    # Senão, usa a rota padrão do tipo
    if tipo_projeto in rotas_padrao:
        return rotas_padrao[tipo_projeto]
    
    # Tentar com strip (ex: ' PoT' vs 'PoT')
    tipo_strip = tipo_projeto.strip() if tipo_projeto else ""
    for chave in rotas_padrao:
        if chave.strip() == tipo_strip:
            return rotas_padrao[chave]
    
    return None

def corrigir_concomitante_db():
    """
    Corrige valores de concomitante no banco de dados.
    A migração original não copiou concomitante do JSON.
    Lê rotas_config.json e atualiza o DB onde concomitante está faltando.
    """
    import sqlite3 as _sqlite3
    config = carregar_rotas_config()
    if not config:
        return
    
    conn = _sqlite3.connect(db.DB_PATH)
    conn.row_factory = _sqlite3.Row
    cursor = conn.cursor()
    
    atualizados = 0
    for nome_projeto, dados in config.items():
        # Buscar projeto no DB
        cursor.execute('SELECT id FROM projetos WHERE nome=? AND ativo=1', (nome_projeto,))
        row = cursor.fetchone()
        if not row:
            continue
        projeto_id = row['id']
        
        for fase_cfg in dados.get('fases', []):
            conc = fase_cfg.get('concomitante', 0)
            if conc > 0:
                fase_num = fase_cfg.get('fase', 1)
                cursor.execute('''
                    UPDATE rotas SET concomitante=?
                    WHERE projeto_id=? AND fase=? AND concomitante=0
                ''', (conc, projeto_id, fase_num))
                atualizados += cursor.rowcount
    
    conn.commit()
    conn.close()
    if atualizados > 0:
        print(f"Concomitante corrigido em {atualizados} fases.")

# Corrigir concomitante ao carregar o app
corrigir_concomitante_db()

# =====================================================
# FUNÇÃO PARA RECALCULAR TODA A DEMANDA
# =====================================================
def _processar_projeto_demanda(nome_projeto, tipo_projeto, data_inicio, estufa, demanda, fases):
    """
    Processa um projeto (hardcoded ou do banco) e adiciona demanda e fases às listas.
    Cada fase pode ter sua própria estufa (fase_estufa); se não tiver, usa a estufa do projeto.
    """
    # Primeiro tenta rotas do banco de dados
    rotas_banco = db.obter_rotas_por_nome_projeto(nome_projeto)
    if rotas_banco:
        rota = [(r["recipiente"], r["meses"], r["quantidade"], r.get("concomitante", 0), r.get("estufa", None)) for r in rotas_banco]
    else:
        # Tenta rota personalizada (JSON) ou padrão
        rota = obter_rota_projeto(nome_projeto, tipo_projeto)
    
    if not rota:
        return
    
    data = data_inicio
    for fase_tuple in rota:
        recipiente = fase_tuple[0]
        meses = fase_tuple[1]
        qtd = fase_tuple[2]
        concomitante = fase_tuple[3] if len(fase_tuple) > 3 else 0
        # Estufa por fase: se definida, usa; senão, usa estufa do projeto
        fase_estufa = fase_tuple[4] if len(fase_tuple) > 4 and fase_tuple[4] else estufa
        duracao_total = meses + concomitante
        
        # Adicionar fase ao Gantt (mostra duração total incluindo concomitância)
        fases.append({
            "Projeto": nome_projeto,
            "Recipiente": recipiente,
            "Inicio": data,
            "Fim": data + relativedelta(months=duracao_total)
        })
        
        # Adicionar demanda para duração total (meses + concomitante)
        for i in range(duracao_total):
            d = data + relativedelta(months=i)
            demanda.append({
                "Projeto": nome_projeto,
                "Recipiente": recipiente,
                "Ano": d.year,
                "Mes": d.month,
                "Quantidade": qtd,
                "Estufa": fase_estufa
            })
        # Próxima fase começa após 'meses' (não inclui concomitante)
        data += relativedelta(months=meses)


def calcular_demanda_e_alocacao():
    """
    Recalcula toda a demanda e alocação baseado nos projetos do banco de dados.
    Retorna: df_demanda, df_fases, df_alocado
    """
    global inicio_global, fim_global
    
    demanda = []
    fases = []
    
    # Buscar TODOS os projetos do banco de dados
    projetos_banco = db.obter_projetos()
    
    # Calcular inicio_global e fim_global a partir dos projetos do banco
    datas_inicio = []
    for proj_db in projetos_banco:
        try:
            dt = pd.to_datetime(proj_db["data_inicio"])
            datas_inicio.append(dt)
        except:
            continue
    
    if datas_inicio:
        inicio_global = min(datas_inicio)
        fim_global = max(datas_inicio) + relativedelta(years=5)
    else:
        from datetime import datetime
        inicio_global = pd.to_datetime(datetime.now())
        fim_global = inicio_global + relativedelta(years=5)
    
    # Processar cada projeto do banco
    for proj_db in projetos_banco:
        nome = proj_db["nome"]
        try:
            data_inicio_db = pd.to_datetime(proj_db["data_inicio"])
        except:
            continue
        
        _processar_projeto_demanda(
            nome_projeto=nome,
            tipo_projeto=proj_db.get("tipo", ""),
            data_inicio=data_inicio_db,
            estufa=proj_db["estufa"],
            demanda=demanda,
            fases=fases
        )
    
    df_demanda = pd.DataFrame(demanda)
    df_fases = pd.DataFrame(fases)
    
    # Se não há demanda, retornar DataFrames vazios com colunas esperadas
    if df_demanda.empty:
        colunas_alocado = ["Ano","Mes","Projeto","Recipiente","Estufa","Quantidade",
                          "Capacidade_m2","Demanda_projeto_m2","Consumido_projeto_m2",
                          "Consumido_total_m2","Demanda_total_m2","Demanda_efetiva_m2",
                          "Demanda_grupo_m2","Disponivel_grupo_m2","Uso_grupo_pct",
                          "Excesso_m2","Acima_Capacidade","Tipo_infra",
                          "Demanda_unidades","Consumido","Capacidade","Disponivel","Uso","Excesso"]
        return df_demanda, df_fases, pd.DataFrame(columns=colunas_alocado)
    
    # =====================================================
    # ALOCAÇÃO COM COMPARTILHAMENTO DE MESAS
    # =====================================================
    # REGRAS FÍSICAS:
    # - MESAS: Bandejas e Citropotes COMPARTILHAM (ocupação conjunta)
    # - BLOCOS: Vasos têm capacidade independente
    # 
    # Cálculo de ocupação:
    # - Ocupação de mesas = demanda_m2(Bandeja) + demanda_m2(Citropote)
    # - Ocupação de blocos = demanda_m2(Vaso)
    # =====================================================
    
    # PASSO 1: Calcular demanda total por mês/recipiente/estufa
    consumo_por_grupo = df_demanda.groupby(
        ["Ano", "Mes", "Recipiente", "Estufa"]
    )["Quantidade"].sum().reset_index()
    consumo_por_grupo.rename(columns={"Quantidade": "Demanda_total_unidades"}, inplace=True)
    
    # PASSO 2: Converter demanda total para m²
    consumo_por_grupo["Demanda_total_m2"] = consumo_por_grupo.apply(
        lambda row: quantidade_para_m2(row["Demanda_total_unidades"], row["Recipiente"]),
        axis=1
    )
    
    # PASSO 3: Calcular demanda de MESAS por mês/estufa (Bandeja + Citropote juntos)
    # e demanda de BLOCOS (Vasos)
    demanda_mesas = consumo_por_grupo[
        consumo_por_grupo["Recipiente"].isin(["Bandeja", "Citropote"])
    ].groupby(["Ano", "Mes", "Estufa"])["Demanda_total_m2"].sum().reset_index()
    demanda_mesas.rename(columns={"Demanda_total_m2": "Demanda_mesas_m2"}, inplace=True)
    
    # PASSO 4: Agrupar por tipo de infraestrutura para cálculo de ocupação
    def calcular_capacidade_e_ocupacao(row):
        """Retorna capacidade e demanda total do grupo (mesa ou bloco)"""
        estufa = row["Estufa"]
        recipiente = row["Recipiente"]
        
        if recipiente in ["Bandeja", "Citropote"]:
            # Usa capacidade de MESAS (compartilhada)
            capacidade = capacidade_mesas_estufa.get(estufa, 0)
            # Demanda total de mesas = Bandeja + Citropote na mesma estufa/mês
            return capacidade, "Mesa"
        else:  # Vaso
            # Usa capacidade de BLOCOS (independente)
            capacidade = capacidade_blocos_estufa.get(estufa, 0)
            return capacidade, "Bloco"
    
    # PASSO 5: Adicionar capacidade por tipo de infraestrutura
    consumo_por_grupo["Capacidade_infra_m2"] = consumo_por_grupo.apply(
        lambda row: capacidade_mesas_estufa.get(row["Estufa"], 0) 
                    if row["Recipiente"] in ["Bandeja", "Citropote"]
                    else capacidade_blocos_estufa.get(row["Estufa"], 0),
        axis=1
    )
    consumo_por_grupo["Tipo_infra"] = consumo_por_grupo["Recipiente"].apply(
        lambda r: "Mesa" if r in ["Bandeja", "Citropote"] else "Bloco"
    )
    
    # PASSO 6: Juntar demanda de mesas para cálculo de ocupação compartilhada
    consumo_por_grupo = consumo_por_grupo.merge(
        demanda_mesas,
        on=["Ano", "Mes", "Estufa"],
        how="left"
    )
    consumo_por_grupo["Demanda_mesas_m2"] = consumo_por_grupo["Demanda_mesas_m2"].fillna(0)
    
    # PASSO 7: Demanda efetiva do grupo (mesas ou blocos)
    consumo_por_grupo["Demanda_grupo_m2"] = consumo_por_grupo.apply(
        lambda row: row["Demanda_mesas_m2"] if row["Tipo_infra"] == "Mesa" else row["Demanda_total_m2"],
        axis=1
    )
    
    # Capacidade do recipiente individual (para manter compatibilidade)
    # Mesas: capacidade é compartilhada, então usamos a capacidade total de mesas
    # Blocos: capacidade é independente (só vasos)
    consumo_por_grupo["Capacidade_m2"] = consumo_por_grupo["Capacidade_infra_m2"]
    consumo_por_grupo["Demanda_efetiva_m2"] = consumo_por_grupo["Demanda_grupo_m2"]
    
    # PASSO 8: Calcular consumo total (limitado à capacidade)
    consumo_por_grupo["Consumido_total_m2"] = consumo_por_grupo.apply(
        lambda row: min(row["Demanda_grupo_m2"], row["Capacidade_m2"]) if row["Capacidade_m2"] > 0 else 0,
        axis=1
    )
    
    # Consumo proporcional por recipiente (para mesas compartilhadas)
    consumo_por_grupo["Fator_grupo"] = consumo_por_grupo.apply(
        lambda row: row["Demanda_total_m2"] / row["Demanda_grupo_m2"] 
                    if row["Demanda_grupo_m2"] > 0 else 0,
        axis=1
    )
    consumo_por_grupo["Consumido_recipiente_m2"] = consumo_por_grupo["Consumido_total_m2"] * consumo_por_grupo["Fator_grupo"]
    
    # PASSO 9: Fator de alocação baseado na demanda efetiva
    consumo_por_grupo["Fator_alocacao"] = consumo_por_grupo.apply(
        lambda row: row["Consumido_total_m2"] / row["Demanda_grupo_m2"]
        if row["Demanda_grupo_m2"] > 0 else 1.0,
        axis=1
    )
    
    # PASSO 10: Juntar com demanda original
    alocado = df_demanda.merge(
        consumo_por_grupo[["Ano", "Mes", "Recipiente", "Estufa", "Capacidade_m2", 
                            "Fator_alocacao", "Demanda_total_m2", "Demanda_efetiva_m2", 
                            "Consumido_total_m2", "Tipo_infra", "Demanda_grupo_m2"]],
        on=["Ano", "Mes", "Recipiente", "Estufa"],
        how="left"
    )
    
    # PASSO 11: Demanda individual em m²
    alocado["Demanda_projeto_m2"] = alocado.apply(
        lambda row: quantidade_para_m2(row["Quantidade"], row["Recipiente"]),
        axis=1
    )
    
    # PASSO 12: Consumo individual proporcional
    alocado["Consumido_projeto_m2"] = alocado["Demanda_projeto_m2"] * alocado["Fator_alocacao"]
    
    # PASSO 13: Disponível e Uso (baseado na demanda do GRUPO compartilhado)
    alocado["Disponivel_grupo_m2"] = (alocado["Capacidade_m2"] - alocado["Demanda_grupo_m2"]).clip(lower=0)
    alocado["Uso_grupo_pct"] = alocado.apply(
        lambda row: round(row["Demanda_grupo_m2"] / row["Capacidade_m2"] * 100, 1) 
            if row["Capacidade_m2"] > 0 else 0,
        axis=1
    )
    
    # PASSO 14: Calcular excesso (demanda do grupo - capacidade)
    alocado["Excesso_m2"] = (alocado["Demanda_grupo_m2"] - alocado["Capacidade_m2"]).clip(lower=0)
    alocado["Acima_Capacidade"] = alocado["Demanda_grupo_m2"] > alocado["Capacidade_m2"]
    
    # PASSO 15: Calcular consumido proporcional por RECIPIENTE (não pelo grupo)
    # Para mesas compartilhadas, o consumo é proporcional à demanda de cada recipiente
    alocado["Consumido_recipiente_m2"] = alocado["Demanda_total_m2"] * alocado["Fator_alocacao"]
    
    # PASSO 16: Agrupar por projeto final
    alocado_final = alocado.groupby(["Ano", "Mes", "Projeto", "Recipiente", "Estufa"]).agg({
        "Quantidade": "sum",
        "Capacidade_m2": "max",
        "Demanda_projeto_m2": "sum",
        "Consumido_projeto_m2": "sum",
        "Consumido_total_m2": "first",
        "Consumido_recipiente_m2": "first",
        "Demanda_total_m2": "first",
        "Demanda_efetiva_m2": "first",
        "Demanda_grupo_m2": "first",
        "Disponivel_grupo_m2": "first",
        "Uso_grupo_pct": "first",
        "Excesso_m2": "first",
        "Acima_Capacidade": "first",
        "Tipo_infra": "first"
    }).reset_index()
    
    df_alocado = alocado_final.copy()
    df_alocado["Demanda_unidades"] = df_alocado["Quantidade"]
    df_alocado["Consumido"] = df_alocado["Consumido_projeto_m2"].round(2)
    df_alocado["Capacidade"] = df_alocado["Capacidade_m2"].round(2)
    df_alocado["Disponivel"] = df_alocado["Disponivel_grupo_m2"].round(2)
    df_alocado["Uso"] = df_alocado["Uso_grupo_pct"]
    df_alocado["Excesso"] = df_alocado["Excesso_m2"].round(2)
    
    # Consumido_total_m2 agora mostra o consumo proporcional do recipiente específico
    # (não o consumo do grupo inteiro)
    df_alocado["Consumido_total_m2"] = df_alocado["Consumido_recipiente_m2"]
    
    return df_demanda, df_fases, df_alocado

# =====================================================
# CALCULAR DADOS INICIAIS
# =====================================================
df_demanda, df_fases, df = calcular_demanda_e_alocacao()
# =====================================================
# ROTAS - MANTIDAS COM COMPATIBILIDADE m²
# =====================================================
# As rotas visualizam os dados em m² e % de ocupação
# Os valores de consumido, capacidade e disponível agora representam m²

@app.route("/")
def index():
    """
    Exibe dashboard visual com:
    - Cards de resumo com barras de progresso coloridas
    - Cards por recipiente/estufa
    - Gráfico de barras empilhadas (consumido vs disponível)
    - Heatmap de ocupação mensal
    - Gráfico de ocupação ao longo do tempo
    - Gantt dos projetos
    - Tabela detalhada com barras visuais
    """
    # Recalcular para refletir projetos mais recentes do banco
    global df_demanda, df_fases, df
    df_demanda, df_fases, df = calcular_demanda_e_alocacao()
    
    ano = request.args.get("ano", type=int)
    mes = request.args.get("mes", type=int)
    estufa = request.args.get("estufa")
    projeto = request.args.get("projeto")
    recipiente_filtro = request.args.get("recipiente")

    df_f = df.copy()

    if ano: df_f = df_f[df_f["Ano"] == ano]
    if mes: df_f = df_f[df_f["Mes"] == mes]
    if estufa: df_f = df_f[df_f["Estufa"] == estufa]
    if projeto: df_f = df_f[df_f["Projeto"].str.contains(projeto)]
    if recipiente_filtro: df_f = df_f[df_f["Recipiente"] == recipiente_filtro]

    # ============================
    # TOTAIS GERAIS (para cards principais)
    # ============================
    from datetime import datetime
    mes_atual = datetime.now().month
    ano_atual = datetime.now().year
    
    if df_f.empty:
        total_cap = 0
        total_cons_grupo = 0
        total_disp = 0
        total_uso = 0
        resumo_cdv1 = {"capacidade": 0, "consumido": 0, "disponivel": 0, "uso": 0, "excesso": 0}
        resumo_cdv9 = {"capacidade": 0, "consumido": 0, "disponivel": 0, "uso": 0, "excesso": 0}
        alertas = []
        mes_referencia = f"{mes_atual:02d}/{ano_atual}"
        pico_geral = {"uso": 0, "mes": "-"}
    else:
        # Filtrar apenas mês atual ou futuro para cálculo principal
        df_futuro = df_f[(df_f["Ano"] > ano_atual) | ((df_f["Ano"] == ano_atual) & (df_f["Mes"] >= mes_atual))]
        if df_futuro.empty:
            df_futuro = df_f  # Se não houver dados futuros, usar todos
        
        # Pegar o primeiro mês disponível como referência
        primeiro_mes = df_futuro.sort_values(["Ano", "Mes"]).iloc[0]
        mes_ref = int(primeiro_mes["Mes"])
        ano_ref = int(primeiro_mes["Ano"])
        mes_referencia = f"{mes_ref:02d}/{ano_ref}"
        
        # Dados do mês de referência
        df_mes_ref = df_f[(df_f["Ano"] == ano_ref) & (df_f["Mes"] == mes_ref)]
        grupos = df_mes_ref.drop_duplicates(subset=["Recipiente", "Estufa"])
        
        # ========== CALCULAR POR ESTUFA (CADA RECIPIENTE SEPARADAMENTE) ==========
        def calcular_resumo_estufa(estufa_nome):
            df_est = grupos[grupos["Estufa"] == estufa_nome]
            if df_est.empty:
                return {"capacidade": 0, "consumido": 0, "disponivel": 0, "uso": 0, "excesso": 0}
            
            # Capacidade real (sem duplicar mesas compartilhadas)
            cap = capacidade_total_estufa.get(estufa_nome, 0)
            
            # Demanda real: pegar Demanda_grupo_m2 por tipo de infraestrutura
            demanda_mesas = 0
            demanda_blocos = 0
            excesso_mesas = 0
            excesso_blocos = 0
            for _, row in df_est.iterrows():
                if row["Tipo_infra"] == "Mesa":
                    demanda_mesas = row["Demanda_grupo_m2"]
                    excesso_mesas = row["Excesso"]
                elif row["Tipo_infra"] == "Bloco":
                    demanda_blocos = row["Demanda_grupo_m2"]
                    excesso_blocos = row["Excesso"]
            
            demanda = demanda_mesas + demanda_blocos
            excesso = excesso_mesas + excesso_blocos
            disp = max(0, cap - demanda)
            uso = round((demanda / cap) * 100, 1) if cap > 0 else 0
            
            return {
                "capacidade": round(cap, 1),
                "consumido": round(demanda, 1),
                "disponivel": round(disp, 1),
                "uso": uso,
                "excesso": round(excesso, 1)
            }
        
        resumo_cdv1 = calcular_resumo_estufa("CDV1")
        resumo_cdv9 = calcular_resumo_estufa("CDV9")
        
        # Total geral (soma das duas estufas)
        total_cap = resumo_cdv1["capacidade"] + resumo_cdv9["capacidade"]
        total_cons_grupo = resumo_cdv1["consumido"] + resumo_cdv9["consumido"]
        total_disp = resumo_cdv1["disponivel"] + resumo_cdv9["disponivel"]
        total_uso = round((total_cons_grupo / total_cap) * 100, 1) if total_cap > 0 else 0
        
        # ========== CALCULAR PICO DE OCUPAÇÃO ==========
        # Encontrar o mês com maior ocupação
        pico_geral = {"uso": 0, "mes": "-"}
        for (ano_p, mes_p, est_p), g in df_f.groupby(["Ano", "Mes", "Estufa"]):
            g_unique = g.drop_duplicates(subset=["Recipiente"])
            
            # Capacidade real (sem duplicar mesas)
            cap = capacidade_total_estufa.get(est_p, 0)
            # Demanda real por tipo de infraestrutura
            dm = 0
            db = 0
            for _, r in g_unique.iterrows():
                if r["Tipo_infra"] == "Mesa":
                    dm = r["Demanda_grupo_m2"]
                elif r["Tipo_infra"] == "Bloco":
                    db = r["Demanda_grupo_m2"]
            demanda_p = dm + db
            
            uso_p = round((demanda_p / cap) * 100, 1) if cap > 0 else 0
            if uso_p > pico_geral["uso"]:
                pico_geral = {"uso": uso_p, "mes": f"{int(mes_p):02d}/{int(ano_p)}", "estufa": est_p}
        
        # ========== ALERTAS ==========
        alertas = []
        if resumo_cdv1["excesso"] > 0:
            alertas.append({"tipo": "danger", "msg": f"CDV1 acima da capacidade em {mes_referencia}! Excesso: {resumo_cdv1['excesso']} m²"})
        if resumo_cdv9["excesso"] > 0:
            alertas.append({"tipo": "danger", "msg": f"CDV9 acima da capacidade em {mes_referencia}! Excesso: {resumo_cdv9['excesso']} m²"})
        if resumo_cdv1["uso"] >= 85:
            alertas.append({"tipo": "warning", "msg": f"CDV1 em alta ocupação: {resumo_cdv1['uso']}%"})
        if resumo_cdv9["uso"] >= 85:
            alertas.append({"tipo": "warning", "msg": f"CDV9 em alta ocupação: {resumo_cdv9['uso']}%"})
    total = {
        "Consumido": round(total_cons_grupo, 2),
        "Capacidade": round(total_cap, 2),
        "Disponivel": round(total_disp, 2),
        "Uso": total_uso,
        "CDV1": resumo_cdv1,
        "CDV9": resumo_cdv9,
        "mes_referencia": mes_referencia,
        "pico": pico_geral,
        "alertas": alertas
    }


    # ============================
    # CARDS POR RECIPIENTE + ESTUFA
    # ============================
    card_recipientes = []
    for (est, rec), g in (df_f.groupby(["Estufa", "Recipiente"]) if not df_f.empty else []):
        g_unique = g.drop_duplicates(subset=["Ano", "Mes", "Recipiente", "Estufa"])
        # Usar capacidade correta por tipo de infraestrutura
        tipo_infra = g_unique["Tipo_infra"].iloc[0] if "Tipo_infra" in g_unique.columns else "Mesa"
        if tipo_infra == "Mesa":
            cap_base = capacidade_mesas_estufa.get(est, 0)
        else:
            cap_base = capacidade_blocos_estufa.get(est, 0)
        # Somar demanda do grupo por mês
        demanda_total = g_unique["Demanda_grupo_m2"].sum() if "Demanda_grupo_m2" in g_unique.columns else 0
        n_meses = g_unique["Mes"].nunique()
        cap = cap_base * n_meses  # capacidade total ao longo dos meses
        cons = demanda_total
        disp = max(0, cap - cons)
        uso = round((cons / cap) * 100, 1) if cap > 0 else 0
        # Cor baseada no uso
        if uso < 60:
            cor = "#28a745"  # verde
            badge = "success"
        elif uso < 85:
            cor = "#ffc107"  # amarelo
            badge = "warning"
        else:
            cor = "#dc3545"  # vermelho
            badge = "danger"
        card_recipientes.append({
            "estufa": est,
            "recipiente": rec,
            "capacidade": round(cap, 1),
            "consumido": round(cons, 1),
            "disponivel": round(disp, 1),
            "uso": uso,
            "cor": cor,
            "badge": badge
        })

    # ============================
    # GRÁFICO: BARRAS EMPILHADAS (CONSUMIDO vs DISPONÍVEL por recipiente+estufa)
    # ============================
    bar_data = pd.DataFrame(card_recipientes)
    if not bar_data.empty:
        bar_data["label"] = bar_data["estufa"] + " – " + bar_data["recipiente"]
        fig_barras = go.Figure()
        fig_barras.add_trace(go.Bar(
            name="Consumido (m²)",
            x=bar_data["label"],
            y=bar_data["consumido"],
            marker_color="#e74c3c",
            text=bar_data["consumido"].apply(lambda v: f"{v:.0f}"),
            textposition="inside"
        ))
        fig_barras.add_trace(go.Bar(
            name="Disponível (m²)",
            x=bar_data["label"],
            y=bar_data["disponivel"],
            marker_color="#2ecc71",
            text=bar_data["disponivel"].apply(lambda v: f"{v:.0f}"),
            textposition="inside"
        ))
        fig_barras.update_layout(
            barmode="stack",
            title="Capacidade × Ocupação por Recipiente / Estufa",
            yaxis_title="Área (m²)",
            xaxis_title="",
            legend=dict(orientation="h", y=1.12, x=0.3, font=dict(color="#94a3b8")),
            height=400,
            margin=dict(t=80),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94a3b8", size=11),
            title_font=dict(color="#e8edf3"),
            xaxis=dict(tickfont=dict(color="#94a3b8"), gridcolor="rgba(255,255,255,0.04)", linecolor="rgba(255,255,255,0.08)"),
            yaxis=dict(tickfont=dict(color="#94a3b8"), gridcolor="rgba(255,255,255,0.04)", linecolor="rgba(255,255,255,0.08)")
        )
        barras_html = fig_barras.to_html(full_html=False)
    else:
        barras_html = "<p>Sem dados para exibir.</p>"

    # ============================
    # GRÁFICO: HEATMAP MENSAL DE OCUPAÇÃO
    # ============================
    heat_src = df_f.copy()
    if not heat_src.empty:
        heat_grp = heat_src.drop_duplicates(subset=["Ano", "Mes", "Recipiente", "Estufa"])
        heat_grp["Periodo"] = heat_grp["Ano"].astype(str) + "-" + heat_grp["Mes"].astype(str).str.zfill(2)
        heat_grp["Grupo"] = heat_grp["Estufa"] + " – " + heat_grp["Recipiente"]
        heat_pivot = heat_grp.pivot_table(
            values="Uso", index="Grupo", columns="Periodo", aggfunc="first"
        ).fillna(0)
        # Ordenar colunas cronologicamente
        heat_pivot = heat_pivot[sorted(heat_pivot.columns)]
        fig_heat = go.Figure(data=go.Heatmap(
            z=heat_pivot.values,
            x=heat_pivot.columns.tolist(),
            y=heat_pivot.index.tolist(),
            colorscale=[
                [0, "#0d253f"],
                [0.25, "#1b4f72"],
                [0.5, "#2e86c1"],
                [0.7, "#f39c12"],
                [0.85, "#e74c3c"],
                [1, "#922b21"]
            ],
            zmin=0, zmax=100,
            text=heat_pivot.values.round(1),
            texttemplate="%{text}%",
            textfont={"size": 11, "color": "#e8edf3"},
            colorbar=dict(
                title=dict(text="Uso %", font=dict(color="#94a3b8")),
                ticksuffix="%",
                tickfont=dict(color="#94a3b8")
            ),
            hovertemplate="%{y}<br>%{x}<br>Uso: %{z:.1f}%<extra></extra>"
        ))
        fig_heat.update_layout(
            title="Mapa de Calor – Ocupação Mensal (%)",
            xaxis_title="Período",
            yaxis_title="",
            height=max(300, len(heat_pivot) * 55 + 120),
            margin=dict(l=160, t=60),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94a3b8", size=11),
            title_font=dict(color="#e8edf3"),
            xaxis=dict(tickfont=dict(color="#94a3b8"), gridcolor="rgba(255,255,255,0.04)"),
            yaxis=dict(tickfont=dict(color="#94a3b8"), gridcolor="rgba(255,255,255,0.04)")
        )
        heatmap_html = fig_heat.to_html(full_html=False)
    else:
        heatmap_html = "<p>Sem dados para exibir.</p>"

    # ============================
    # GRÁFICO: OCUPAÇÃO AO LONGO DO TEMPO (LINHA)
    # ============================
    if not df.empty:
        # Calcular demanda real por estufa/mês sem duplicar mesas
        ocup_list = []
        df_ocup_dedup = df.drop_duplicates(subset=["Ano", "Mes", "Recipiente", "Estufa"])
        for (ano_o, mes_o, est_o), g_o in df_ocup_dedup.groupby(["Ano", "Mes", "Estufa"]):
            dm_o = 0
            db_o = 0
            for _, r_o in g_o.iterrows():
                if r_o["Tipo_infra"] == "Mesa":
                    dm_o = r_o["Demanda_grupo_m2"]
                elif r_o["Tipo_infra"] == "Bloco":
                    db_o = r_o["Demanda_grupo_m2"]
            ocup_list.append({"Ano": ano_o, "Mes": mes_o, "Estufa": est_o, "Ocupacao_m2": dm_o + db_o})
        
        ocupacao_mes = pd.DataFrame(ocup_list)
        ocupacao_mes["Capacidade"] = ocupacao_mes["Estufa"].map(capacidade_total_estufa)
        ocupacao_mes["Data"] = pd.to_datetime(
            dict(year=ocupacao_mes.Ano, month=ocupacao_mes.Mes, day=1)
        )
        ocupacao_mes["Uso_%"] = (
            ocupacao_mes["Ocupacao_m2"] / ocupacao_mes["Capacidade"] * 100
        ).round(1)

        fig_ocupacao = px.line(
            ocupacao_mes,
            x="Data",
            y="Uso_%",
            color="Estufa",
            markers=True,
            title="Ocupação das Estufas (%) ao longo do tempo",
            hover_data={"Ocupacao_m2": ":.2f"}
        )
        fig_ocupacao.update_yaxes(title="Ocupação (%)")
        fig_ocupacao.update_xaxes(title="Data")
        fig_ocupacao.update_layout(
            height=400,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94a3b8", size=11),
            title_font=dict(color="#e8edf3"),
            legend=dict(font=dict(color="#94a3b8")),
            xaxis=dict(tickfont=dict(color="#94a3b8"), gridcolor="rgba(255,255,255,0.04)", linecolor="rgba(255,255,255,0.08)"),
            yaxis=dict(tickfont=dict(color="#94a3b8"), gridcolor="rgba(255,255,255,0.04)", linecolor="rgba(255,255,255,0.08)")
        )
        ocupacao_html = fig_ocupacao.to_html(full_html=False)
    else:
        ocupacao_html = "<p>Sem dados para exibir.</p>"

    # ============================
    # GRÁFICO GANTT
    # ============================
    if not df_fases.empty:
        gantt = px.timeline(
            df_fases,
            x_start="Inicio",
            x_end="Fim",
            y="Projeto",
            color="Recipiente"
        )
        gantt.update_yaxes(autorange="reversed")
        gantt.update_layout(
            height=500,
            margin=dict(l=180, r=40, t=30, b=50),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94a3b8", size=12),
            title_font=dict(color="#e8edf3", size=15),
            legend=dict(font=dict(color="#94a3b8", size=12)),
            xaxis=dict(tickfont=dict(color="#94a3b8", size=11), gridcolor="rgba(255,255,255,0.04)", linecolor="rgba(255,255,255,0.08)"),
            yaxis=dict(tickfont=dict(color="#94a3b8", size=11), gridcolor="rgba(255,255,255,0.04)", linecolor="rgba(255,255,255,0.08)")
        )
        gantt_html = gantt.to_html(full_html=False)
    else:
        gantt_html = "<p>Sem dados para exibir.</p>"

    # ============================
    # TABELA AGRUPADA POR RECIPIENTE (projetos na mesma linha)
    # ============================
    tabela_rows = []
    # Agrupar por Ano/Mes/Recipiente/Estufa
    for (ano_g, mes_g, rec_g, est_g), grupo in (df_f.groupby(["Ano", "Mes", "Recipiente", "Estufa"]) if not df_f.empty else []):
        # Pegar valores do grupo (únicos) - já calculados com demanda do grupo compartilhado
        cap = grupo["Capacidade"].iloc[0]
        disp = grupo["Disponivel"].iloc[0]
        uso_val = grupo["Uso"].iloc[0]  # Uso já calculado com demanda do grupo
        
        # Calcular demanda total deste recipiente (soma das demandas dos projetos)
        demanda_total_m2 = grupo["Demanda_projeto_m2"].sum() if "Demanda_projeto_m2" in grupo.columns else 0
        
        # Excesso do grupo (já calculado no DataFrame)
        excesso = grupo["Excesso"].iloc[0] if "Excesso" in grupo.columns else max(0, demanda_total_m2 - cap)
        acima_capacidade = grupo["Acima_Capacidade"].iloc[0] if "Acima_Capacidade" in grupo.columns else (demanda_total_m2 > cap)
        
        # Cor baseada no uso do grupo
        if uso_val < 60:
            cor_barra = "#28a745"
        elif uso_val < 85:
            cor_barra = "#ffc107"
        else:
            cor_barra = "#dc3545"
        
        # Montar lista de projetos com seus detalhes
        projetos_lista = []
        for _, row in grupo.iterrows():
            demanda_m2 = row["Demanda_projeto_m2"] if "Demanda_projeto_m2" in row else row["Demanda_unidades"] * tamanho_recipientes.get(rec_g, 1)
            projetos_lista.append({
                "nome": row["Projeto"],
                "demanda": int(row["Demanda_unidades"]),
                "demanda_m2": round(demanda_m2, 2),
                "consumido": round(row["Consumido"], 2)
            })
        
        tabela_rows.append({
            "ano": int(ano_g),
            "mes": int(mes_g),
            "recipiente": rec_g,
            "estufa": est_g,
            "projetos": projetos_lista,
            "demanda_total": round(demanda_total_m2, 2),
            "capacidade": round(cap, 2),
            "disponivel": round(disp, 2),
            "excesso": round(excesso, 2),
            "acima_capacidade": acima_capacidade,
            "uso": uso_val,
            "cor": cor_barra
        })
    
    # Ordenar por ano, mês, estufa, recipiente
    tabela_rows = sorted(tabela_rows, key=lambda x: (x["ano"], x["mes"], x["estufa"], x["recipiente"]))    
    # ============================
    # RESUMO MENSAL POR CDV (PARA TIMELINE)
    # ============================
    resumo_mensal_display = []
    
    if not df.empty:
        df_mensal = df.drop_duplicates(subset=["Ano", "Mes", "Recipiente", "Estufa"])
        
        for (ano, mes, estufa), grupo in df_mensal.groupby(["Ano", "Mes", "Estufa"]):
            # Capacidade real da estufa (sem duplicação de mesas)
            cap_total = capacidade_total_estufa.get(estufa, 0)
            
            # Demanda real: pegar Demanda_grupo_m2 por tipo de infraestrutura
            # Mesas (Bandeja+Citropote compartilham): pegar UMA VEZ o valor do grupo
            # Blocos (Vaso): demanda independente
            demanda_mesas = 0
            demanda_blocos = 0
            for _, row in grupo.iterrows():
                if row["Tipo_infra"] == "Mesa":
                    demanda_mesas = row["Demanda_grupo_m2"]  # Mesmo valor para Bandeja e Citropote
                elif row["Tipo_infra"] == "Bloco":
                    demanda_blocos = row["Demanda_grupo_m2"]
            
            demanda_total = demanda_mesas + demanda_blocos
            disp = max(0, cap_total - demanda_total)
            uso_pct = round((demanda_total / cap_total) * 100, 1) if cap_total > 0 else 0
            
            # Definir cor baseada no uso
            if uso_pct < 60:
                cor = "success"
            elif uso_pct < 85:
                cor = "warning"
            else:
                cor = "danger"
            
            resumo_mensal_display.append({
                "ano": int(ano),
                "mes": int(mes),
                "mes_display": f"{int(mes):02d}/{int(ano)}",
                "estufa": estufa,
                "capacidade": round(cap_total, 1),
                "consumido": round(demanda_total, 1),
                "disponivel": round(disp, 1),
                "uso": uso_pct,
                "cor": cor
            })
    
    # Agrupar por estufa para facilitar renderização
    resumo_cdv1 = [r for r in resumo_mensal_display if r["estufa"] == "CDV1"]
    resumo_cdv9 = [r for r in resumo_mensal_display if r["estufa"] == "CDV9"]

    return render_template(
        "index.html",
        tabela_rows=tabela_rows,
        barras=barras_html,
        heatmap=heatmap_html,
        ocupacao=ocupacao_html,
        gantt=gantt_html,
        anos=sorted(df["Ano"].unique()) if not df.empty else [],
        meses=sorted(df["Mes"].unique()) if not df.empty else [],
        estufas=sorted(df["Estufa"].unique()) if not df.empty else [],
        projetos=sorted(df["Projeto"].unique()) if not df.empty else [],
        recipientes=sorted(df["Recipiente"].unique()) if not df.empty else [],
        total=total,
        cards=card_recipientes,
        resumo_cdv1=resumo_cdv1,
        resumo_cdv9=resumo_cdv9
    )

@app.route("/excel")
def export_excel():
    """
    Exporta consolidado mensal por recipiente/estufa em Excel.
    
    Valores exportados por recipiente:
    - Consumido: m² ocupados
    - Capacidade: m² disponíveis
    - Disponível: m² não utilizados
    - Uso (%): % de ocupação
    
    Abas: Resumo Mensal/Anual por estufa + Detalhado por recipiente
    """

    # ============================
    # CONSOLIDADO POR RECIPIENTE (em m²)
    # ============================
    df_grupos = df.drop_duplicates(subset=["Ano", "Mes", "Recipiente", "Estufa"])
    df_grupos = df_grupos.copy()
    
    # ============================
    # RESUMO MENSAL POR ESTUFA (CDV1 e CDV9 separados)
    # ============================
    # LÓGICA: Cada recipiente tem sua própria capacidade independente
    # Simplesmente somar todos os recipientes
    
    resumo_lista = []
    for (ano, mes, estufa), grupo in df_grupos.groupby(["Ano", "Mes", "Estufa"]):
        # Cada recipiente é independente: simplesmente somar
        consumo_total = grupo["Consumido_total_m2"].sum()
        demanda_total = grupo["Demanda_total_m2"].sum()
        excesso_total = grupo["Excesso_m2"].sum()
        
        resumo_lista.append({
            "Ano": ano,
            "Mes": mes,
            "Estufa": estufa,
            "Consumido_total_m2": consumo_total,
            "Demanda_total_m2": demanda_total,
            "Excesso_m2": excesso_total
        })
    
    resumo_mensal = pd.DataFrame(resumo_lista)
    
    # Usar capacidade FIXA por estufa (não varia com os meses)
    resumo_mensal["Capacidade Total (m²)"] = resumo_mensal["Estufa"].map(capacidade_total_estufa)
    resumo_mensal["Disponível Total (m²)"] = resumo_mensal["Capacidade Total (m²)"] - resumo_mensal["Demanda_total_m2"]
    resumo_mensal["Uso (%)"] = (resumo_mensal["Demanda_total_m2"] / resumo_mensal["Capacidade Total (m²)"] * 100).round(1)
    resumo_mensal["Excesso (m²)"] = resumo_mensal["Excesso_m2"].round(2)
    resumo_mensal["Status"] = resumo_mensal["Excesso_m2"].apply(lambda x: "⚠️ ACIMA" if x > 0 else "OK")
    resumo_mensal.rename(columns={
        "Demanda_total_m2": "Demanda Total (m²)"
    }, inplace=True)
    
    # Separar por estufa
    colunas_mensal = ["Ano", "Mes", "Demanda Total (m²)", "Capacidade Total (m²)", "Disponível Total (m²)", "Excesso (m²)", "Uso (%)", "Status"]
    resumo_mensal_cdv1 = resumo_mensal[resumo_mensal["Estufa"] == "CDV1"][colunas_mensal].copy()
    resumo_mensal_cdv9 = resumo_mensal[resumo_mensal["Estufa"] == "CDV9"][colunas_mensal].copy()
    
    # ============================
    # RESUMO ANUAL POR ESTUFA
    # ============================
    # Agrupar do resumo mensal (já correto) por ano
    resumo_anual = resumo_mensal.groupby(["Ano", "Estufa"]).agg({
        "Demanda Total (m²)": "mean",    # Média mensal da demanda no ano
        "Excesso (m²)": "mean"           # Média mensal do excesso no ano
    }).reset_index()
    
    # Renomear de volta para o formato esperado
    resumo_anual.rename(columns={
        "Demanda Total (m²)": "Demanda_total_m2",
        "Excesso (m²)": "Excesso_m2"
    }, inplace=True)
    
    # Usar capacidade FIXA por estufa (não varia com os anos)
    resumo_anual["Capacidade Total (m²)"] = resumo_anual["Estufa"].map(capacidade_total_estufa)
    resumo_anual["Disponível Total (m²)"] = resumo_anual["Capacidade Total (m²)"] - resumo_anual["Demanda_total_m2"]
    resumo_anual["Uso (%)"] = (resumo_anual["Demanda_total_m2"] / resumo_anual["Capacidade Total (m²)"] * 100).round(1)
    resumo_anual["Excesso (m²)"] = resumo_anual["Excesso_m2"].round(2)
    resumo_anual["Status"] = resumo_anual["Excesso_m2"].apply(lambda x: "⚠️ ACIMA" if x > 0 else "OK")
    resumo_anual.rename(columns={
        "Demanda_total_m2": "Demanda Total (m²)"
    }, inplace=True)
    
    # Separar por estufa
    colunas_anual = ["Ano", "Demanda Total (m²)", "Capacidade Total (m²)", "Disponível Total (m²)", "Excesso (m²)", "Uso (%)", "Status"]
    resumo_anual_cdv1 = resumo_anual[resumo_anual["Estufa"] == "CDV1"][colunas_anual].copy()
    resumo_anual_cdv9 = resumo_anual[resumo_anual["Estufa"] == "CDV9"][colunas_anual].copy()
    
    # ============================
    # CONSOLIDADO POR RECIPIENTE (detalhado)
    # ============================
    consolidado = df_grupos[[
        "Ano", "Mes", "Estufa", "Recipiente",
        "Demanda_total_m2", "Consumido_total_m2", "Capacidade", "Disponivel", "Excesso", "Uso"
    ]].copy()
    
    consolidado.rename(columns={
        "Demanda_total_m2": "Demanda (m²)",
        "Consumido_total_m2": "Consumido (m²)",
        "Capacidade": "Capacidade (m²)",
        "Disponivel": "Disponível (m²)",
        "Excesso": "Excesso (m²)",
        "Uso": "Uso (%)"
    }, inplace=True)
    
    # Adicionar status
    consolidado["Status"] = consolidado["Excesso (m²)"].apply(lambda x: "⚠️ ACIMA" if x > 0 else "OK")
    
    # Ordenar
    consolidado["Data"] = pd.to_datetime(
        dict(year=consolidado.Ano, month=consolidado.Mes, day=1)
    )
    consolidado = consolidado.sort_values(["Data", "Estufa", "Recipiente"])
    
    # ============================
    # SEPARA POR ESTUFA
    # ============================
    colunas = ["Ano", "Mes", "Recipiente", "Demanda (m²)", "Consumido (m²)", "Capacidade (m²)", "Disponível (m²)", "Excesso (m²)", "Uso (%)", "Status"]
    
    cdv1 = consolidado[consolidado["Estufa"] == "CDV1"][colunas].copy()
    cdv9 = consolidado[consolidado["Estufa"] == "CDV9"][colunas].copy()

    # ============================
    # RESUMO GERAL POR RECIPIENTE (todas as datas)
    # ============================
    resumo = df_grupos.groupby(["Estufa", "Recipiente"]).agg(
        Consumido_total=("Consumido_total_m2", "sum"),
        Capacidade_total=("Capacidade", "sum"),
    ).reset_index()
    resumo["Disponível (m²)"] = resumo["Capacidade_total"] - resumo["Consumido_total"]
    resumo["Uso (%)"] = (resumo["Consumido_total"] / resumo["Capacidade_total"] * 100).round(1)
    resumo.rename(columns={
        "Consumido_total": "Consumido (m²)",
        "Capacidade_total": "Capacidade (m²)"
    }, inplace=True)

    # ============================
    # DETALHES POR RECIPIENTE (igual à aba do dashboard)
    # Uma linha por projeto mostrando sua contribuição em cada mês/recipiente/estufa
    # ============================
    detalhes_rows = []
    for (ano_g, mes_g, rec_g, est_g), grupo in df.groupby(["Ano", "Mes", "Recipiente", "Estufa"]):
        cap = grupo["Capacidade"].iloc[0]
        disp = grupo["Disponivel"].iloc[0]
        uso_val = grupo["Uso"].iloc[0]
        demanda_total_m2 = grupo["Demanda_projeto_m2"].sum() if "Demanda_projeto_m2" in grupo.columns else 0
        excesso = grupo["Excesso"].iloc[0] if "Excesso" in grupo.columns else max(0, demanda_total_m2 - cap)
        status = "ACIMA" if excesso > 0 else "OK"

        for _, row in grupo.iterrows():
            demanda_m2 = row["Demanda_projeto_m2"] if "Demanda_projeto_m2" in row else row["Demanda_unidades"] * tamanho_recipientes.get(rec_g, 1)
            detalhes_rows.append({
                "Ano": int(ano_g),
                "Mês": int(mes_g),
                "Estufa": est_g,
                "Recipiente": rec_g,
                "Projeto": row["Projeto"],
                "Demanda (un.)": int(row["Demanda_unidades"]),
                "Demanda Projeto (m²)": round(demanda_m2, 2),
                "Demanda Total (m²)": round(demanda_total_m2, 2),
                "Capacidade (m²)": round(cap, 2),
                "Disponível (m²)": round(disp, 2),
                "Excesso (m²)": round(excesso, 2),
                "Uso (%)": uso_val,
                "Status": status
            })

    df_detalhes = pd.DataFrame(detalhes_rows)
    if not df_detalhes.empty:
        df_detalhes = df_detalhes.sort_values(["Ano", "Mês", "Estufa", "Recipiente", "Projeto"])

    # ============================
    # PROJETO MÊS COMPLETO (todos os projetos com todos os meses)
    # Visão completa: cada projeto em cada mês com recipiente, estufa e valores
    # ============================
    projeto_mes_rows = []
    for _, row in df.iterrows():
        demanda_m2 = row["Demanda_projeto_m2"] if "Demanda_projeto_m2" in row else row["Demanda_unidades"] * tamanho_recipientes.get(row["Recipiente"], 1)
        projeto_mes_rows.append({
            "Ano": int(row["Ano"]),
            "Mês": int(row["Mes"]),
            "Projeto": row["Projeto"],
            "Recipiente": row["Recipiente"],
            "Estufa": row["Estufa"],
            "Quantidade (un.)": int(row["Demanda_unidades"]),
            "Demanda Projeto (m²)": round(demanda_m2, 2),
            "Consumido (m²)": round(row["Consumido"], 2),
            "Capacidade (m²)": round(row["Capacidade"], 2),
            "Disponível (m²)": round(row["Disponivel"], 2),
            "Excesso (m²)": round(row["Excesso"], 2),
            "Uso (%)": row["Uso"],
            "Status": "ACIMA" if row["Excesso"] > 0 else "OK"
        })

    df_projeto_mes = pd.DataFrame(projeto_mes_rows)
    if not df_projeto_mes.empty:
        df_projeto_mes = df_projeto_mes.sort_values(["Projeto", "Ano", "Mês", "Recipiente", "Estufa"])

    # ============================
    # EXPORTA EXCEL
    # ============================
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        # Escrever dados - Abas separadas por estufa
        resumo_mensal_cdv1.to_excel(writer, index=False, sheet_name="CDV1 - Mensal Total")
        resumo_mensal_cdv9.to_excel(writer, index=False, sheet_name="CDV9 - Mensal Total")
        resumo_anual_cdv1.to_excel(writer, index=False, sheet_name="CDV1 - Anual Total")
        resumo_anual_cdv9.to_excel(writer, index=False, sheet_name="CDV9 - Anual Total")
        cdv1.to_excel(writer, index=False, sheet_name="CDV1 - Detalhado")
        cdv9.to_excel(writer, index=False, sheet_name="CDV9 - Detalhado")
        resumo.to_excel(writer, index=False, sheet_name="Resumo por Recipiente")

        # ============================
        # NOVAS ABAS: Detalhes por Recipiente + Projeto Mês
        # ============================
        if not df_detalhes.empty:
            df_detalhes.to_excel(writer, index=False, sheet_name="Detalhes por Recipiente")

        if not df_projeto_mes.empty:
            df_projeto_mes.to_excel(writer, index=False, sheet_name="Projeto Mês Completo")
        
        # ============================
        # DADOS DO BANCO DE DADOS SQLite
        # ============================
        # Projetos
        df_projetos = pd.DataFrame(db.obter_projetos())
        if not df_projetos.empty:
            df_projetos.to_excel(writer, index=False, sheet_name="Projetos")
        
        # Rotas detalhadas
        df_rotas = pd.DataFrame(db.obter_todas_rotas())
        if not df_rotas.empty:
            df_rotas.to_excel(writer, index=False, sheet_name="Rotas")
        
        # Simulações pendentes
        df_sims = pd.DataFrame(db.obter_simulacoes_pendentes())
        if not df_sims.empty:
            df_sims.to_excel(writer, index=False, sheet_name="Simulações")
        
        # Capacidades
        df_caps = pd.DataFrame(db.obter_capacidades())
        if not df_caps.empty:
            df_caps.to_excel(writer, index=False, sheet_name="Capacidades")
        
        # Formatar colunas no Excel
        workbook = writer.book
        format_float = workbook.add_format({'num_format': '0.00'})
        format_percent = workbook.add_format({'num_format': '0.0"%"'})
        format_header = workbook.add_format({'bold': True, 'bg_color': '#2c3e50', 'font_color': 'white', 'align': 'center'})
        format_status_ok = workbook.add_format({'font_color': '#28a745', 'bold': True})
        format_status_acima = workbook.add_format({'font_color': '#dc3545', 'bold': True})
        
        for sheet_name, worksheet in writer.sheets.items():
            worksheet.set_column('A:A', 10)   # Ano
            worksheet.set_column('B:B', 10)   # Mês
            worksheet.set_column('C:D', 22)   # Consumido, Capacidade
            worksheet.set_column('E:F', 22, format_float)  # Disponível, outros
            worksheet.set_column('G:H', 14, format_percent)  # Uso

        # Formatação especial para as novas abas
        for sheet_name in ["Detalhes por Recipiente", "Projeto Mês Completo"]:
            if sheet_name in writer.sheets:
                ws = writer.sheets[sheet_name]
                ws.set_column('A:A', 8)    # Ano
                ws.set_column('B:B', 6)    # Mês
                ws.set_column('C:C', 12)   # Estufa / Projeto
                ws.set_column('D:D', 14)   # Recipiente
                ws.set_column('E:E', 28)   # Projeto / Estufa
                ws.set_column('F:F', 14, format_float)   # Demanda un.
                ws.set_column('G:G', 18, format_float)   # Demanda m²
                ws.set_column('H:H', 18, format_float)   # Demanda Total / Consumido
                ws.set_column('I:I', 16, format_float)   # Capacidade
                ws.set_column('J:J', 16, format_float)   # Disponível
                ws.set_column('K:K', 14, format_float)   # Excesso
                ws.set_column('L:L', 10, format_percent) # Uso
                ws.set_column('M:M', 10)   # Status

    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="capacidade_estufas_completo.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# =====================================================
# PDF - RELATÓRIO COM DADOS EM m²
# =====================================================
@app.route("/pdf")
def export_pdf():
    """
    Exporta relatório em PDF com resumo de ocupação por estufa em m².
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "title",
        parent=styles["Title"],
        alignment=TA_CENTER
    )

    elements = [
        Paragraph("Relatório de Gerenciamento de Ocupação das Estufas (m²)", title_style),
        Spacer(1, 16)
    ]

    # Resumo por estufa
    data = [["Estufa", "Demanda (m²)", "Capacidade (m²)", "Disponível (m²)", "Uso (%)"]]
    for e in ["CDV1", "CDV9"]:
        g_pdf = df[df["Estufa"] == e].drop_duplicates(subset=["Ano", "Mes", "Recipiente", "Estufa"])
        if g_pdf.empty:
            continue
        cap_pdf = capacidade_total_estufa.get(e, 0)
        # Demanda sem duplicar mesas
        dm_pdf = 0
        db_pdf = 0
        for _, r_pdf in g_pdf.iterrows():
            if r_pdf["Tipo_infra"] == "Mesa":
                dm_pdf = max(dm_pdf, r_pdf["Demanda_grupo_m2"])
            elif r_pdf["Tipo_infra"] == "Bloco":
                db_pdf = max(db_pdf, r_pdf["Demanda_grupo_m2"])
        demanda_pdf = dm_pdf + db_pdf
        disp_pdf = max(0, cap_pdf - demanda_pdf)
        uso_pdf = round((demanda_pdf / cap_pdf * 100), 1) if cap_pdf > 0 else 0
        
        data.append([
            e,
            f"{demanda_pdf:.2f}",
            f"{cap_pdf:.2f}",
            f"{disp_pdf:.2f}",
            f"{uso_pdf}%"
        ])

    table = Table(data, hAlign="CENTER")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 16))
    
    # Nota sobre os dados
    note = Paragraph(
        "<b>Nota:</b> Todos os valores de capacidade e consumo são expressos em metros quadrados (m²). "
        "Esta refatoração permite análise mais precisa da ocupação física considerando o tamanho real de cada recipiente.",
        styles["Normal"]
    )
    elements.append(note)
    
    doc.build(elements)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="relatorio_estufas.pdf"
    )


# =====================================================
# ROTA DE CONFIGURAÇÃO DE ROTAS POR PROJETO
# =====================================================
@app.route("/rotas", methods=["GET", "POST"])
def rotas_config():
    """
    Página para gerenciar projetos e rotas.
    Permite criar projetos, visualizar rotas e editar duração de cada fase.
    """
    estufas_lista = sorted(capacidade["Estufa"].unique())
    
    # Processar criação de novo projeto
    if request.method == "POST":
        try:
            # Debug: log all form keys
            print(f"[DEBUG] Form keys: {list(request.form.keys())}")
            print(f"[DEBUG] Form data: {dict(request.form)}")
            
            nome_projeto = request.form.get("nome_projeto", "").strip()
            tipo_projeto = request.form.get("tipo_projeto", "").strip()
            estufa = request.form.get("estufa", "").strip()
            data_inicio = request.form.get("data_inicio", "").strip()
            
            # tipo_projeto é opcional – "Customizado" ou vazio = sem rota padrão
            if not tipo_projeto:
                tipo_projeto = "Customizado"
            
            if nome_projeto and estufa and data_inicio:
                # Verificar se projeto já existe
                proj_existe = db.obter_projeto_por_nome(nome_projeto)
                if not proj_existe:
                    # Inserir projeto
                    db.inserir_projeto(
                        nome=nome_projeto,
                        tipo=tipo_projeto,
                        data_inicio=data_inicio,
                        estufa=estufa
                    )
                    
                    # Buscar as fases (customizadas ou padrão)
                    proj = db.obter_projeto_por_nome(nome_projeto)
                    fases_para_inserir = []
                    
                    # Verificar se há fases customizadas no formulário
                    fase_indices = set()
                    for key in request.form.keys():
                        if key.startswith("fase_") and "_recipiente" in key:
                            idx = key.split("_")[1]
                            fase_indices.add(int(idx))
                    
                    if fase_indices:
                        # Usar as fases customizadas
                        for idx in sorted(fase_indices):
                            recipiente = request.form.get(f"fase_{idx}_recipiente", "").strip()
                            meses_str = request.form.get(f"fase_{idx}_meses", "").strip()
                            quantidade_str = request.form.get(f"fase_{idx}_quantidade", "").strip()
                            concomitante_str = request.form.get(f"fase_{idx}_concomitante", "0").strip()
                            fase_estufa = request.form.get(f"fase_{idx}_estufa", "").strip()
                            
                            if recipiente and meses_str and quantidade_str:
                                try:
                                    fases_para_inserir.append({
                                        "recipiente": recipiente,
                                        "meses": int(meses_str),
                                        "quantidade": int(quantidade_str),
                                        "concomitante": int(concomitante_str) if concomitante_str else 0,
                                        "estufa": fase_estufa if fase_estufa else None
                                    })
                                except ValueError:
                                    pass
                    
                    # Se nenhuma fase customizada válida foi encontrada, usar as padrão do tipo
                    if not fases_para_inserir:
                        # Buscar rota padrão (com fallback strip para ' PoT' vs 'PoT' etc.)
                        rota_encontrada = None
                        if tipo_projeto in rotas_padrao:
                            rota_encontrada = rotas_padrao[tipo_projeto]
                        else:
                            tipo_strip = tipo_projeto.strip()
                            for chave in rotas_padrao:
                                if chave.strip() == tipo_strip:
                                    rota_encontrada = rotas_padrao[chave]
                                    break
                        
                        if rota_encontrada:
                            for recipiente, meses, quantidade, concomitante in rota_encontrada:
                                fases_para_inserir.append({
                                    "recipiente": recipiente,
                                    "meses": meses,
                                    "quantidade": quantidade,
                                    "concomitante": concomitante
                                })
                    
                    # Inserir as fases no banco
                    for i, fase in enumerate(fases_para_inserir, 1):
                        db.inserir_rota(
                            projeto_id=proj["id"],
                            fase=i,
                            recipiente=fase["recipiente"],
                            meses=fase["meses"],
                            quantidade=fase["quantidade"],
                            concomitante=fase.get("concomitante", 0),
                            estufa=fase.get("estufa", None)
                        )
                    
                    flash(f"Projeto '{nome_projeto}' criado com sucesso em {estufa}! ({len(fases_para_inserir)} fases)", "success")
                    
                    # ✅ RECALCULAR DEMANDA E ALOCAÇÃO AUTOMATICAMENTE
                    global df_demanda, df_fases, df
                    df_demanda, df_fases, df = calcular_demanda_e_alocacao()
                else:
                    flash(f"Projeto '{nome_projeto}' já existe.", "warning")
            
        except Exception as e:
            flash(f"Erro ao criar projeto: {str(e)}", "danger")
        
        return redirect(url_for("rotas_config"))
    
    # Obter projetos ativos do banco
    projetos_banco = db.obter_projetos()
    projetos_ativos = []
    projetos_fases = {}  # Dicionário para armazenar as fases de cada projeto
    
    for proj in projetos_banco:
        projetos_ativos.append({
            "id": proj["id"],
            "nome": proj["nome"],
            "tipo": proj["tipo"],
            "data_inicio": proj["data_inicio"],
            "estufa": proj["estufa"]
        })
        
        # Buscar fases do projeto do banco
        rotas = db.obter_rotas_projeto(proj["id"])
        projetos_fases[proj["id"]] = {
            rota["fase"]: {
                "recipiente": rota["recipiente"],
                "meses": rota["meses"],
                "quantidade": rota["quantidade"],
                "concomitante": rota.get("concomitante", 0) if isinstance(rota, dict) else 0,
                "estufa": rota.get("estufa", None) if isinstance(rota, dict) else None
            }
            for rota in rotas
        }
    
    # Ordenar por data de início (mais recentes primeiro)
    projetos_ativos.sort(key=lambda x: x["data_inicio"] if x["data_inicio"] else "", reverse=True)
    
    return render_template(
        "rotas.html",
        projetos_ativos=projetos_ativos,
        projetos_fases=projetos_fases,
        estufas=estufas_lista,
        rotas_padrao=rotas_padrao
    )


@app.route("/rotas/editar/<int:proj_id>", methods=["POST"])
def editar_projeto_rota(proj_id):
    """Edita um projeto (estufa, data de início e fases) e recalcula a demanda automaticamente."""
    try:
        estufa = request.form.get("estufa", "").strip()
        data_inicio = request.form.get("data_inicio", "").strip()
        
        if not estufa or not data_inicio:
            flash("Estufa e data são obrigatórios.", "danger")
            return redirect(url_for("rotas_config"))
        
        # Atualizar no banco
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE projetos SET estufa=?, data_inicio=? WHERE id=?', 
                      (estufa, data_inicio, proj_id))
        conn.commit()
        conn.close()
        
        # Coletar e salvar fases editadas
        # Os campos vêm como: fase_0_recipiente, fase_0_meses, fase_0_quantidade, etc.
        fases_novas = []
        fase_indices = set()
        
        # Encontrar todos os índices de fase presentes
        for key in request.form.keys():
            if key.startswith("fase_") and "_recipiente" in key:
                idx = key.split("_")[1]
                fase_indices.add(int(idx))
        
        # Coletar dados de cada fase
        for idx in sorted(fase_indices):
            recipiente = request.form.get(f"fase_{idx}_recipiente", "").strip()
            meses = request.form.get(f"fase_{idx}_meses", "").strip()
            quantidade = request.form.get(f"fase_{idx}_quantidade", "").strip()
            concomitante = request.form.get(f"fase_{idx}_concomitante", "0").strip()
            fase_estufa = request.form.get(f"fase_{idx}_estufa", "").strip()
            
            if recipiente and meses and quantidade:
                try:
                    fases_novas.append({
                        "recipiente": recipiente,
                        "meses": int(meses),
                        "quantidade": int(quantidade),
                        "concomitante": int(concomitante) if concomitante else 0,
                        "estufa": fase_estufa if fase_estufa else None
                    })
                except ValueError:
                    pass  # Ignorar valores inválidos
        
        # Se há fases novas, atualizar
        if fases_novas:
            db.atualizar_rotas_projeto(proj_id, fases_novas)
        
        # ✅ RECALCULAR DEMANDA E ALOCAÇÃO AUTOMATICAMENTE
        global df_demanda, df_fases, df
        df_demanda, df_fases, df = calcular_demanda_e_alocacao()
        
        flash("Projeto atualizado com sucesso! Capacidade recalculada.", "success")
    except Exception as e:
        flash(f"Erro ao editar projeto: {str(e)}", "danger")
    
    return redirect(url_for("rotas_config"))


@app.route("/rotas/remover/<int:proj_id>", methods=["GET"])
def remover_projeto_rota(proj_id):
    """Remove um projeto permanentemente do banco de dados."""
    try:
        db.remover_projeto(proj_id, excluir_permanente=True)
        # ✅ RECALCULAR DEMANDA APÓS REMOÇÃO
        global df_demanda, df_fases, df
        df_demanda, df_fases, df = calcular_demanda_e_alocacao()
        flash("Projeto e suas fases removidos permanentemente. Capacidade recalculada.", "info")
    except Exception as e:
        flash(f"Erro ao remover projeto: {str(e)}", "danger")
    
    return redirect(url_for("rotas_config"))


@app.route("/rotas/salvar", methods=["POST"])
def salvar_rotas():
    """
    Salva alterações nas rotas e recalcula toda a demanda.
    """
    global df_demanda, df_fases, df
    
    config = carregar_rotas_config()
    
    # Processar dados do formulário
    for key in request.form:
        # Formato: projeto_NOMEPROJETO_fase_N_campo
        if key.startswith("projeto_"):
            parts = key.split("_")
            # Encontrar onde começa "fase"
            fase_idx = None
            for i, part in enumerate(parts):
                if part == "fase":
                    fase_idx = i
                    break
            
            if fase_idx is None:
                continue
            
            # Reconstruir nome do projeto (pode ter underscores)
            # Os underscores vieram de replace(' ', '_') no HTML, então converter de volta
            nome_projeto = "_".join(parts[1:fase_idx]).replace("_", " ")
            fase_num = int(parts[fase_idx + 1])
            campo = parts[fase_idx + 2]
            valor = request.form[key]
            
            # Inicializar projeto na config se não existe
            if nome_projeto not in config:
                # Buscar tipo do projeto no banco de dados
                proj_db = db.obter_projeto_por_nome(nome_projeto)
                tipo = proj_db["tipo"] if proj_db and proj_db.get("tipo") else ""
                if tipo in rotas_padrao:
                    config[nome_projeto] = {
                        "tipo": tipo,
                        "fases": [
                            {"recipiente": r, "meses": m, "quantidade": q, "concomitante": c, "fase": i+1}
                            for i, (r, m, q, c) in enumerate(rotas_padrao[tipo])
                        ]
                    }
            
            # Atualizar valor
            if nome_projeto in config:
                for fase in config[nome_projeto]["fases"]:
                    if fase["fase"] == fase_num:
                        if campo == "meses":
                            fase["meses"] = int(valor)
                        elif campo == "quantidade":
                            fase["quantidade"] = int(valor)
                        elif campo == "recipiente":
                            fase["recipiente"] = valor
                        break
    
    # Salvar configuração
    salvar_rotas_config(config)
    
    # Recalcular demanda e alocação
    df_demanda, df_fases, df = calcular_demanda_e_alocacao()
    
    flash("Rotas atualizadas com sucesso! Os cálculos de capacidade foram recalculados.", "success")
    return redirect(url_for("rotas_config"))


@app.route("/rotas/resetar/<projeto>")
def resetar_rota(projeto):
    """
    Reseta a rota de um projeto para os valores padrão.
    """
    global df_demanda, df_fases, df
    
    config = carregar_rotas_config()
    
    if projeto in config:
        # Buscar tipo do projeto no banco de dados
        proj_db = db.obter_projeto_por_nome(projeto)
        tipo = proj_db["tipo"] if proj_db and proj_db.get("tipo") else ""
        if tipo in rotas_padrao:
            config[projeto] = {
                "tipo": tipo,
                "fases": [
                    {"recipiente": r, "meses": m, "quantidade": q, "concomitante": c, "fase": i+1}
                    for i, (r, m, q, c) in enumerate(rotas_padrao[tipo])
                ]
            }
            salvar_rotas_config(config)
            
            # Recalcular demanda e alocação
            df_demanda, df_fases, df = calcular_demanda_e_alocacao()
            
            flash(f"Rota do projeto '{projeto}' resetada para valores padrão.", "info")
    
    return redirect(url_for("rotas_config"))


# =====================================================
# 🧪 SIMULAÇÃO DE CAPACIDADE (WHAT-IF)
# =====================================================
# Permite simular demandas adicionais sem impactar dados reais
# Usa variável em memória para armazenar simulações temporárias
# =====================================================

# Armazenamento temporário de simulações (em memória + banco)
simulacoes_temp = []

def carregar_simulacoes_do_banco():
    """Carrega simulações pendentes do banco para a memória."""
    global simulacoes_temp
    sims_banco = db.obter_simulacoes_pendentes()
    simulacoes_temp = []
    for s in sims_banco:
        simulacoes_temp.append({
            "id": s["id"],
            "nome": s["nome"],
            "estufa": s["estufa"],
            "recipiente": s["recipiente"],
            "quantidade": s["quantidade"],
            "tempo_meses": s["tempo_meses"],
            "data_inicio": s.get("data_inicio"),
            "demanda_m2": quantidade_para_m2(s["quantidade"], s["recipiente"])
        })
    return simulacoes_temp

# Carregar simulações ao iniciar
carregar_simulacoes_do_banco()


@app.route("/simulacao")
def simulacao():
    """
    Exibe a tela de simulação de capacidade.
    Mostra formulário para adicionar simulações e visualização do impacto.
    """
    global simulacoes_temp, df_demanda, df_fases, df
    df_demanda, df_fases, df = calcular_demanda_e_alocacao()
    
    # =====================================================
    # CAPACIDADE MENSAL POR ESTUFA (análise correta)
    # =====================================================
    # Agrupa por Ano, Mes, Estufa, Recipiente para ter dados mensais
    df_mensal = df.groupby(["Ano", "Mes", "Estufa", "Recipiente"]).agg({
        "Consumido_total_m2": "first",  # Já é o total do grupo
        "Capacidade": "first"
    }).reset_index()
    
    df_mensal["Disponivel"] = (df_mensal["Capacidade"] - df_mensal["Consumido_total_m2"]).clip(lower=0)
    df_mensal["Uso_pct"] = (df_mensal["Consumido_total_m2"] / df_mensal["Capacidade"] * 100).round(1)
    df_mensal["Uso_pct"] = df_mensal["Uso_pct"].clip(lower=0)
    
    # Encontrar o mês atual ou próximo com dados
    from datetime import datetime
    hoje = datetime.now()
    ano_atual, mes_atual = hoje.year, hoje.month
    
    # Filtrar apenas meses futuros ou atual
    df_futuro = df_mensal[(df_mensal["Ano"] > ano_atual) | 
                          ((df_mensal["Ano"] == ano_atual) & (df_mensal["Mes"] >= mes_atual))]
    
    if df_futuro.empty:
        df_futuro = df_mensal  # Usar todos se não houver futuros
    
    # Resumo do MÊS ATUAL/PRÓXIMO por estufa/recipiente
    primeiro_mes = df_futuro.sort_values(["Ano", "Mes"]).head(1)
    if not primeiro_mes.empty:
        ano_ref = primeiro_mes.iloc[0]["Ano"]
        mes_ref = primeiro_mes.iloc[0]["Mes"]
    else:
        ano_ref, mes_ref = ano_atual, mes_atual
    
    capacidade_mes_atual = df_mensal[
        (df_mensal["Ano"] == ano_ref) & (df_mensal["Mes"] == mes_ref)
    ][["Estufa", "Recipiente", "Consumido_total_m2", "Capacidade", "Disponivel", "Uso_pct"]].copy()
    
    # Calcular pico de ocupação por estufa/recipiente (mês com maior uso)
    pico_ocupacao = df_mensal.loc[
        df_mensal.groupby(["Estufa", "Recipiente"])["Uso_pct"].idxmax()
    ][["Ano", "Mes", "Estufa", "Recipiente", "Uso_pct"]].copy()
    pico_ocupacao = pico_ocupacao.rename(columns={"Uso_pct": "Pico_pct"})
    pico_ocupacao["Pico_mes"] = pico_ocupacao.apply(
        lambda r: f"{int(r['Mes']):02d}/{int(r['Ano'])}", axis=1
    )
    
    # Juntar capacidade atual com pico
    capacidade_atual = capacidade_mes_atual.merge(
        pico_ocupacao[["Estufa", "Recipiente", "Pico_pct", "Pico_mes"]], 
        on=["Estufa", "Recipiente"], 
        how="left"
    )
    
    # Dados para timeline mensal (para gráfico/tabela detalhada)
    capacidade_mensal = df_mensal.sort_values(["Ano", "Mes", "Estufa", "Recipiente"]).to_dict('records')
    
    # Calcular impacto das simulações
    impacto_mensal, impacto_resumo = calcular_impacto_simulacoes(simulacoes_temp)
    
    # Dados para os dropdowns
    estufas_lista = sorted(capacidade["Estufa"].unique())
    recipientes_lista = sorted(capacidade["Recipiente"].unique())
    
    # Construir lista de rotas disponíveis para cada tipo de projeto
    # Formato: {tipo_projeto: {fase_nome: {recipiente, meses, quantidade, concomitante}}}
    rotas_lista = {}
    for tipo, rota in rotas_padrao.items():
        rotas_lista[tipo] = {
            f"Fase {i+1}": {
                "recipiente": r,
                "meses": m,
                "quantidade": q,
                "concomitante": c,
                "demanda_m2": quantidade_para_m2(q, r),
                "desc": f"{q} {r}(s) por {m} mês(es)" + (f" (+{c}m conc.)" if c else "")
            }
            for i, (r, m, q, c) in enumerate(rota)
        }
    
    # Dados dos projetos (para referência de tipo) — agora do banco de dados
    projetos_info = []
    projetos_banco = db.obter_projetos()
    for p_db in projetos_banco:
        proj_tipo = (p_db.get("tipo") or "").strip()
        if proj_tipo in rotas_lista:
            projetos_info.append({
                "nome": p_db["nome"],
                "tipo": proj_tipo,
                "estufa": p_db["estufa"],
                "rotas": rotas_lista[proj_tipo]
            })
    
    return render_template(
        "simulacao.html",
        estufas=estufas_lista,
        recipientes=recipientes_lista,
        tamanhos=tamanho_recipientes,
        rotas_padrao=rotas_padrao,
        rotas_lista=rotas_lista,
        projetos_info=projetos_info,
        simulacoes=simulacoes_temp,
        impacto=impacto_resumo,
        impacto_mensal=impacto_mensal,
        capacidade_atual=capacidade_atual.to_dict('records'),
        capacidade_mensal=capacidade_mensal,
        mes_referencia=f"{int(mes_ref):02d}/{int(ano_ref)}"
    )


def calcular_impacto_simulacoes(simulacoes):
    """
    Calcula o impacto das simulações na capacidade MÊS A MÊS.
    Cada simulação tem data_inicio e tempo_meses, então mostra
    quais meses são impactados por cada fase.
    Retorna:
      - impacto_mensal: lista de dicts por mês/estufa/recipiente com antes vs depois
      - impacto_resumo: agrupamento global (para visão geral)
    """
    if not simulacoes:
        return [], []
    
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    
    # Descobrir todos os meses impactados pelas simulações
    meses_sim = set()
    for s in simulacoes:
        try:
            dt = datetime.strptime(s.get("data_inicio", ""), "%Y-%m-%d")
        except (ValueError, TypeError):
            dt = datetime.now().replace(day=1)
        meses_dur = s.get("tempo_meses", 1) or 1
        for i in range(meses_dur):
            m_dt = dt + relativedelta(months=i)
            meses_sim.add((m_dt.year, m_dt.month))
    
    # Ordenar meses
    meses_ordenados = sorted(meses_sim)
    
    # Preparar dados de consumo ANTES (do DataFrame df existente) 
    # e capacidade por estufa/recipiente
    impacto_mensal = []
    
    for (ano, mes) in meses_ordenados:
        for estufa in capacidade["Estufa"].unique():
            for recipiente in capacidade["Recipiente"].unique():
                # Capacidade disponível para este par
                cap_info = capacidade[
                    (capacidade["Estufa"] == estufa) & 
                    (capacidade["Recipiente"] == recipiente)
                ]
                if cap_info.empty:
                    continue
                    
                cap_m2 = cap_info.iloc[0]["Capacidade"]
                
                # Consumo ANTES (dados reais deste mês, se existem)
                df_mes = df[
                    (df["Estufa"] == estufa) & 
                    (df["Recipiente"] == recipiente) &
                    (df["Ano"] == ano) &
                    (df["Mes"] == mes)
                ]
                if not df_mes.empty:
                    consumo_antes = df_mes.drop_duplicates(
                        subset=["Ano", "Mes"]
                    )["Consumido_total_m2"].iloc[0]
                else:
                    consumo_antes = 0
                
                # Adicional das simulações QUE COBREM este mês
                sim_adicional = 0
                sims_neste_mes = []
                for s in simulacoes:
                    if s["estufa"] != estufa or s["recipiente"] != recipiente:
                        continue
                    try:
                        dt_s = datetime.strptime(s.get("data_inicio", ""), "%Y-%m-%d")
                    except (ValueError, TypeError):
                        dt_s = datetime.now().replace(day=1)
                    meses_dur = s.get("tempo_meses", 1) or 1
                    dt_fim = dt_s + relativedelta(months=meses_dur)
                    
                    # Checar se este mês está dentro do período da simulação
                    dt_mes = datetime(ano, mes, 1)
                    if dt_s <= dt_mes < dt_fim:
                        sim_adicional += s["demanda_m2"]
                        sims_neste_mes.append(s["nome"])
                
                # Só incluir se houver consumo ou simulação neste mês
                if consumo_antes > 0 or sim_adicional > 0:
                    consumo_depois = consumo_antes + sim_adicional
                    uso_antes = round(consumo_antes / cap_m2 * 100, 1) if cap_m2 > 0 else 0
                    uso_depois = round(consumo_depois / cap_m2 * 100, 1) if cap_m2 > 0 else 0
                    
                    impacto_mensal.append({
                        "ano": ano,
                        "mes": mes,
                        "periodo": f"{mes:02d}/{ano}",
                        "estufa": estufa,
                        "recipiente": recipiente,
                        "capacidade_m2": round(cap_m2, 2),
                        "consumo_antes": round(consumo_antes, 2),
                        "consumo_depois": round(consumo_depois, 2),
                        "disponivel_antes": round(max(0, cap_m2 - consumo_antes), 2),
                        "disponivel_depois": round(max(0, cap_m2 - consumo_depois), 2),
                        "uso_antes": uso_antes,
                        "uso_depois": uso_depois,
                        "simulacao_m2": round(sim_adicional, 2),
                        "ultrapassou": consumo_depois > cap_m2,
                        "simulacoes_nomes": sims_neste_mes
                    })
    
    # Resumo global (agrupado por estufa/recipiente — pega o pior mês)
    impacto_resumo = []
    combos = set((i["estufa"], i["recipiente"]) for i in impacto_mensal)
    for (estufa, recipiente) in sorted(combos):
        itens = [i for i in impacto_mensal if i["estufa"] == estufa and i["recipiente"] == recipiente]
        pior = max(itens, key=lambda x: x["uso_depois"])
        impacto_resumo.append({
            "estufa": estufa,
            "recipiente": recipiente,
            "capacidade_m2": pior["capacidade_m2"],
            "consumo_antes": pior["consumo_antes"],
            "consumo_depois": pior["consumo_depois"],
            "disponivel_antes": pior["disponivel_antes"],
            "disponivel_depois": pior["disponivel_depois"],
            "uso_antes": pior["uso_antes"],
            "uso_depois": pior["uso_depois"],
            "simulacao_m2": pior["simulacao_m2"],
            "ultrapassou": pior["ultrapassou"],
            "pior_mes": pior["periodo"],
            "meses_impactados": len(itens)
        })
    
    return impacto_mensal, impacto_resumo


@app.route("/simulacao/adicionar", methods=["POST"])
def adicionar_simulacao():
    """
    Adiciona uma nova simulação à lista temporária.
    NÃO altera os dados reais do sistema.
    
    Suporta dois modos:
    1. Manual: estufa, recipiente, quantidade, tempo_meses, nome_simulacao
    2. Rota: tipo_projeto, rota_nome, rota_estufa (busca dados da rota pré-definida)
    """
    global simulacoes_temp
    
    try:
        # Verificar se é modo rota ou modo manual
        tipo_projeto = request.form.get("tipo_projeto", "").strip()
        rota_nome = request.form.get("rota_nome", "").strip()
        rota_estufa = request.form.get("rota_estufa", "").strip()
        
        if tipo_projeto and rota_nome and rota_estufa:
            # MODO ROTA
            if tipo_projeto not in rotas_padrao:
                flash(f"Tipo de projeto '{tipo_projeto}' não encontrado.", "danger")
                return redirect(url_for("simulacao"))
            
            rota_data = rotas_padrao[tipo_projeto]
            
            # Cada rota é uma tupla (recipiente, meses, quantidade, concomitante)
            # Precisamos encontrar qual índice é a "Fase X" desejada
            rota_index = int(rota_nome.split()[-1]) - 1  # Extrai número de "Fase 1", "Fase 2", etc
            
            if rota_index < 0 or rota_index >= len(rota_data):
                flash(f"Fase '{rota_nome}' não encontrada para '{tipo_projeto}'.", "danger")
                return redirect(url_for("simulacao"))
            
            recipiente, tempo_meses, quantidade, _conc = rota_data[rota_index]
            estufa = rota_estufa
            nome_simulacao = f"{tipo_projeto} - {rota_nome} em {estufa}"
            
        else:
            # MODO MANUAL
            estufa = request.form.get("estufa", "").strip()
            recipiente = request.form.get("recipiente", "").strip()
            quantidade = int(request.form.get("quantidade", 0))
            tempo_meses = int(request.form.get("tempo_meses", 1))
            nome_simulacao = request.form.get("nome_simulacao", "").strip()
            
            if not nome_simulacao:
                nome_simulacao = f"Simulação {len(simulacoes_temp) + 1}"
        
        # Validar campos obrigatórios
        if not estufa or not recipiente:
            flash("Estufa e Recipiente são obrigatórios.", "danger")
            return redirect(url_for("simulacao"))
        
        # Converter quantidade para m²
        demanda_m2 = quantidade_para_m2(quantidade, recipiente)
        
        # Obter data_inicio
        data_inicio = request.form.get("data_inicio", "").strip()
        if not data_inicio:
            data_inicio = None
        
        # Salvar no banco de dados
        sim_id = db.inserir_simulacao(
            nome=nome_simulacao,
            tipo_projeto=tipo_projeto if tipo_projeto else None,
            recipiente=recipiente,
            quantidade=quantidade,
            tempo_meses=tempo_meses,
            estufa=estufa,
            data_inicio=data_inicio
        )
        
        # Atualizar lista em memória
        simulacao = {
            "id": sim_id,
            "nome": nome_simulacao,
            "estufa": estufa,
            "recipiente": recipiente,
            "quantidade": quantidade,
            "tempo_meses": tempo_meses,
            "data_inicio": data_inicio,
            "tempo_meses": tempo_meses,
            "demanda_m2": demanda_m2
        }
        
        simulacoes_temp.append(simulacao)
        flash(f"Simulação '{nome_simulacao}' adicionada e salva no banco!", "success")
        
    except Exception as e:
        flash(f"Erro ao adicionar simulação: {str(e)}", "danger")
    
    return redirect(url_for("simulacao"))


@app.route("/simulacao/adicionar_projeto", methods=["POST"])
def adicionar_simulacao_projeto():
    """
    Adiciona um projeto simulado com múltiplas fases (novo formulário).
    Processa dados do formulário com fases dinâmicas.
    """
    global simulacoes_temp
    
    try:
        nome_projeto = request.form.get("nome_projeto", "").strip()
        tipo_projeto = request.form.get("tipo_projeto", "").strip()
        estufa_padrao = request.form.get("estufa", "").strip()
        data_inicio_str = request.form.get("data_inicio", "").strip()
        
        if not nome_projeto:
            flash("Nome do projeto é obrigatório.", "danger")
            return redirect(url_for("simulacao"))
        
        if not estufa_padrao:
            flash("Estufa padrão é obrigatória.", "danger")
            return redirect(url_for("simulacao"))
        
        # Coletar fases do formulário
        fases = []
        fase_idx = 0
        while True:
            recipiente = request.form.get(f"fase_{fase_idx}_recipiente", "").strip()
            quantidade_str = request.form.get(f"fase_{fase_idx}_quantidade", "").strip()
            meses_str = request.form.get(f"fase_{fase_idx}_meses", "").strip()
            concomitante_str = request.form.get(f"fase_{fase_idx}_concomitante", "").strip()
            estufa_fase = request.form.get(f"fase_{fase_idx}_estufa", "").strip()
            
            if not recipiente:
                break  # Não há mais fases
            
            quantidade = int(quantidade_str) if quantidade_str else 0
            meses = int(meses_str) if meses_str else 1
            concomitante = int(concomitante_str) if concomitante_str else 0
            estufa = estufa_fase if estufa_fase else estufa_padrao
            
            if quantidade > 0:
                fases.append({
                    "numero": fase_idx + 1,
                    "recipiente": recipiente,
                    "quantidade": quantidade,
                    "meses": meses,
                    "concomitante": concomitante,
                    "estufa": estufa
                })
            
            fase_idx += 1
        
        if not fases:
            flash("Adicione pelo menos uma fase ao projeto.", "danger")
            return redirect(url_for("simulacao"))
        
        # Calcular datas das fases considerando concomitância
        from datetime import datetime
        data_inicio_atual = datetime.strptime(data_inicio_str, "%Y-%m-%d") if data_inicio_str else datetime.now()
        
        adicionadas = 0
        for fase in fases:
            nome_sim = f"{nome_projeto} - Fase {fase['numero']} ({fase['recipiente']})"
            demanda_m2 = quantidade_para_m2(fase['quantidade'], fase['recipiente'])
            data_inicio_fase = data_inicio_atual.strftime("%Y-%m-%d")
            
            # Duração total da fase = meses + concomitante
            # (concomitante = meses extras que a fase perdura junto com a próxima)
            duracao_total = fase['meses'] + fase['concomitante']
            
            # Salvar no banco de dados
            sim_id = db.inserir_simulacao(
                nome=nome_sim,
                tipo_projeto=tipo_projeto if tipo_projeto != "Customizado" else nome_projeto,
                recipiente=fase['recipiente'],
                quantidade=fase['quantidade'],
                tempo_meses=duracao_total,
                estufa=fase['estufa'],
                data_inicio=data_inicio_fase
            )
            
            # Atualizar lista em memória
            simulacoes_temp.append({
                "id": sim_id,
                "nome": nome_sim,
                "estufa": fase['estufa'],
                "recipiente": fase['recipiente'],
                "quantidade": fase['quantidade'],
                "tempo_meses": duracao_total,
                "data_inicio": data_inicio_fase,
                "demanda_m2": demanda_m2
            })
            
            adicionadas += 1
            
            # Próxima fase começa após 'meses' (não inclui concomitante)
            # Concomitante apenas estende a duração da fase atual
            data_inicio_atual = data_inicio_atual + relativedelta(months=fase['meses'])
        
        flash(f"Projeto '{nome_projeto}' simulado com {adicionadas} fase(s)!", "success")
        
    except Exception as e:
        flash(f"Erro ao simular projeto: {str(e)}", "danger")
    
    return redirect(url_for("simulacao"))


@app.route("/simulacao/adicionar_rota", methods=["POST"])
def adicionar_simulacao_rota():
    """
    Adiciona todas as fases de uma rota como simulações de uma vez.
    Recebe JSON com: nome, estufa, data_inicio, fases (lista de {recipiente, quantidade, duracao})
    """
    global simulacoes_temp
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "erro": "Dados inválidos"}), 400
        
        nome_base = data.get("nome", "").strip()
        estufa = data.get("estufa", "").strip()
        data_inicio_str = data.get("data_inicio", "").strip()
        fases = data.get("fases", [])
        
        if not nome_base or not estufa or not fases:
            return jsonify({"ok": False, "erro": "Nome, estufa e fases são obrigatórios"}), 400
        
        from datetime import datetime
        data_inicio_atual = datetime.strptime(data_inicio_str, "%Y-%m-%d") if data_inicio_str else datetime.now()
        
        adicionadas = 0
        for i, fase in enumerate(fases):
            recipiente = fase.get("recipiente", "")
            quantidade = int(fase.get("quantidade", 0))
            duracao = int(fase.get("duracao", 1))
            
            if not recipiente or quantidade <= 0:
                continue
            
            nome_sim = f"{nome_base} - Fase {i+1} ({recipiente})"
            demanda_m2 = quantidade_para_m2(quantidade, recipiente)
            data_inicio_fase = data_inicio_atual.strftime("%Y-%m-%d")
            
            # Salvar no banco de dados
            sim_id = db.inserir_simulacao(
                nome=nome_sim,
                tipo_projeto=nome_base,
                recipiente=recipiente,
                quantidade=quantidade,
                tempo_meses=duracao,
                estufa=estufa,
                data_inicio=data_inicio_fase
            )
            
            # Atualizar lista em memória
            simulacoes_temp.append({
                "id": sim_id,
                "nome": nome_sim,
                "estufa": estufa,
                "recipiente": recipiente,
                "quantidade": quantidade,
                "tempo_meses": duracao,
                "data_inicio": data_inicio_fase,
                "demanda_m2": demanda_m2
            })
            
            adicionadas += 1
            
            # Próxima fase começa após esta terminar
            data_inicio_atual = data_inicio_atual + relativedelta(months=duracao)
        
        if adicionadas > 0:
            flash(f"Rota '{nome_base}' adicionada com {adicionadas} fase(s)!", "success")
            return jsonify({"ok": True, "adicionadas": adicionadas})
        else:
            return jsonify({"ok": False, "erro": "Nenhuma fase válida encontrada"}), 400
    
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500


@app.route("/simulacao/remover/<int:sim_id>")
def remover_simulacao(sim_id):
    """
    Remove uma simulação específica da lista temporária e do banco.
    """
    global simulacoes_temp
    
    # Remover do banco
    db.remover_simulacao(sim_id)
    
    # Remover da memória
    simulacoes_temp = [s for s in simulacoes_temp if s["id"] != sim_id]
    flash("Simulação removida.", "info")
    
    return redirect(url_for("simulacao"))


@app.route("/simulacao/cancelar")
def cancelar_simulacao():
    """
    Cancela todas as simulações, limpando a lista temporária e o banco.
    """
    global simulacoes_temp
    
    # Limpar banco
    db.limpar_simulacoes_pendentes()
    
    # Limpar memória
    simulacoes_temp = []
    flash("Todas as simulações foram canceladas.", "warning")
    
    return redirect(url_for("simulacao"))


@app.route("/simulacao/aceitar", methods=["POST"])
def aceitar_simulacao():
    """
    Aceita as simulações e as transforma em projetos reais no banco de dados.
    Cria projetos + rotas no banco e recalcula toda a demanda.
    ATENÇÃO: Esta ação modifica os dados reais do sistema!
    """
    global simulacoes_temp, df_demanda, df_fases, df
    
    if not simulacoes_temp:
        flash("Não há simulações para aceitar.", "warning")
        return redirect(url_for("simulacao"))
    
    try:
        import re
        from datetime import datetime
        
        # =====================================================
        # AGRUPAR SIMULAÇÕES POR PROJETO
        # Simulações criadas por "adicionar_projeto" têm nome no formato:
        #   "NomeProjeto - Fase X (Recipiente)"
        # Simulações manuais têm nomes simples.
        # Agrupamos pelo nome-base para criar um único projeto com múltiplas fases.
        # =====================================================
        projetos_agrupados = {}  # nome_projeto -> {estufa, data_inicio, fases: [{recipiente, meses, quantidade, concomitante, estufa}]}
        
        for sim in simulacoes_temp:
            nome_sim = sim["nome"]
            
            # Tentar extrair nome-base: "NomeProjeto - Fase X (Recipiente)"
            match = re.match(r'^(.+?)\s*-\s*Fase\s+\d+', nome_sim)
            if match:
                nome_projeto = match.group(1).strip()
            else:
                # Simulação manual — cada uma vira seu próprio projeto
                nome_projeto = nome_sim
            
            if nome_projeto not in projetos_agrupados:
                # Usar data_inicio da primeira fase (ou hoje)
                data_inicio_str = sim.get("data_inicio")
                if not data_inicio_str:
                    data_inicio_str = datetime.now().strftime("%Y-%m-%d")
                
                projetos_agrupados[nome_projeto] = {
                    "estufa": sim["estufa"],
                    "data_inicio": data_inicio_str,
                    "tipo": "Simulação Aceita",
                    "fases": []
                }
            
            projetos_agrupados[nome_projeto]["fases"].append({
                "recipiente": sim["recipiente"],
                "meses": sim["tempo_meses"],
                "quantidade": sim["quantidade"],
                "concomitante": 0,
                "estufa": sim["estufa"] if sim["estufa"] != projetos_agrupados[nome_projeto]["estufa"] else None
            })
        
        # =====================================================
        # CRIAR PROJETOS E ROTAS NO BANCO DE DADOS
        # =====================================================
        projetos_criados = 0
        fases_criadas = 0
        
        for nome_projeto, dados in projetos_agrupados.items():
            # Verificar se o projeto já existe
            proj_existe = db.obter_projeto_por_nome(nome_projeto)
            if proj_existe:
                # Projeto já existe — pular para não duplicar
                flash(f"Projeto '{nome_projeto}' já existe no sistema, pulando.", "warning")
                continue
            
            # Inserir o projeto
            projeto_id = db.inserir_projeto(
                nome=nome_projeto,
                tipo=dados["tipo"],
                data_inicio=dados["data_inicio"],
                estufa=dados["estufa"]
            )
            
            # Inserir as rotas/fases
            for i, fase in enumerate(dados["fases"], 1):
                db.inserir_rota(
                    projeto_id=projeto_id,
                    fase=i,
                    recipiente=fase["recipiente"],
                    meses=fase["meses"],
                    quantidade=fase["quantidade"],
                    concomitante=fase.get("concomitante", 0),
                    estufa=fase.get("estufa", None)
                )
                fases_criadas += 1
            
            projetos_criados += 1
        
        # =====================================================
        # MARCAR SIMULAÇÕES COMO ACEITAS NO BANCO
        # =====================================================
        for sim in simulacoes_temp:
            db.aceitar_simulacao(sim["id"])
        
        # =====================================================
        # RECALCULAR TODA A DEMANDA A PARTIR DO BANCO
        # (agora inclui os novos projetos recém-criados)
        # =====================================================
        df_demanda, df_fases, df = calcular_demanda_e_alocacao()
        
        # Limpar simulações da memória
        qtd_sims = len(simulacoes_temp)
        simulacoes_temp = []
        
        flash(f"{qtd_sims} simulação(ões) aceita(s)! {projetos_criados} projeto(s) criado(s) com {fases_criadas} fase(s) no sistema.", "success")
        
    except Exception as e:
        flash(f"Erro ao aceitar simulações: {str(e)}", "danger")
    
    return redirect(url_for("index"))


def calcular_demanda_e_alocacao_com_extras(df_extras):
    """
    Recalcula demanda e alocação incluindo demandas extras (das simulações).
    """
    global inicio_global, fim_global
    
    demanda = []
    fases = []
    
    # Buscar TODOS os projetos do banco de dados
    projetos_banco = db.obter_projetos()
    
    # Calcular inicio_global e fim_global
    datas_inicio = []
    for proj_db in projetos_banco:
        try:
            dt = pd.to_datetime(proj_db["data_inicio"])
            datas_inicio.append(dt)
        except:
            continue
    
    if datas_inicio:
        inicio_global = min(datas_inicio)
        fim_global = max(datas_inicio) + relativedelta(years=5)
    else:
        from datetime import datetime
        inicio_global = pd.to_datetime(datetime.now())
        fim_global = inicio_global + relativedelta(years=5)
    
    for proj_db in projetos_banco:
        nome = proj_db["nome"]
        try:
            data_inicio_db = pd.to_datetime(proj_db["data_inicio"])
        except:
            continue
        _processar_projeto_demanda(
            nome_projeto=nome,
            tipo_projeto=proj_db.get("tipo", ""),
            data_inicio=data_inicio_db,
            estufa=proj_db["estufa"],
            demanda=demanda,
            fases=fases
        )
    
    df_demanda = pd.DataFrame(demanda)
    
    # ADICIONAR DEMANDAS EXTRAS (das simulações aceitas)
    if df_extras is not None and not df_extras.empty:
        df_demanda = pd.concat([df_demanda, df_extras], ignore_index=True)
    
    df_fases = pd.DataFrame(fases)
    
    # Se não há demanda, retornar DataFrames vazios com colunas esperadas
    if df_demanda.empty:
        colunas_alocado = ["Ano","Mes","Projeto","Recipiente","Estufa","Quantidade",
                          "Capacidade_m2","Demanda_projeto_m2","Consumido_projeto_m2",
                          "Consumido_total_m2","Demanda_total_m2","Demanda_efetiva_m2",
                          "Demanda_grupo_m2","Disponivel_grupo_m2","Uso_grupo_pct",
                          "Excesso_m2","Acima_Capacidade","Tipo_infra",
                          "Demanda_unidades","Consumido","Capacidade","Disponivel","Uso","Excesso"]
        return df_demanda, df_fases, pd.DataFrame(columns=colunas_alocado)
    
    # =====================================================
    # ALOCAÇÃO COM COMPARTILHAMENTO DE MESAS (mesma lógica da função principal)
    # =====================================================
    consumo_por_grupo = df_demanda.groupby(
        ["Ano", "Mes", "Recipiente", "Estufa"]
    )["Quantidade"].sum().reset_index()
    consumo_por_grupo.rename(columns={"Quantidade": "Demanda_total_unidades"}, inplace=True)
    
    consumo_por_grupo["Demanda_total_m2"] = consumo_por_grupo.apply(
        lambda row: quantidade_para_m2(row["Demanda_total_unidades"], row["Recipiente"]),
        axis=1
    )
    
    # Calcular demanda de MESAS por mês/estufa (Bandeja + Citropote juntos)
    demanda_mesas = consumo_por_grupo[
        consumo_por_grupo["Recipiente"].isin(["Bandeja", "Citropote"])
    ].groupby(["Ano", "Mes", "Estufa"])["Demanda_total_m2"].sum().reset_index()
    demanda_mesas.rename(columns={"Demanda_total_m2": "Demanda_mesas_m2"}, inplace=True)
    
    # Adicionar capacidade por tipo de infraestrutura
    consumo_por_grupo["Capacidade_m2"] = consumo_por_grupo.apply(
        lambda row: capacidade_mesas_estufa.get(row["Estufa"], 0) 
                    if row["Recipiente"] in ["Bandeja", "Citropote"]
                    else capacidade_blocos_estufa.get(row["Estufa"], 0),
        axis=1
    )
    consumo_por_grupo["Tipo_infra"] = consumo_por_grupo["Recipiente"].apply(
        lambda r: "Mesa" if r in ["Bandeja", "Citropote"] else "Bloco"
    )
    
    # Juntar demanda de mesas
    consumo_por_grupo = consumo_por_grupo.merge(
        demanda_mesas,
        on=["Ano", "Mes", "Estufa"],
        how="left"
    )
    consumo_por_grupo["Demanda_mesas_m2"] = consumo_por_grupo["Demanda_mesas_m2"].fillna(0)
    
    # Demanda do grupo (mesas ou blocos)
    consumo_por_grupo["Demanda_grupo_m2"] = consumo_por_grupo.apply(
        lambda row: row["Demanda_mesas_m2"] if row["Tipo_infra"] == "Mesa" else row["Demanda_total_m2"],
        axis=1
    )
    consumo_por_grupo["Demanda_efetiva_m2"] = consumo_por_grupo["Demanda_grupo_m2"]
    
    consumo_por_grupo["Consumido_total_m2"] = consumo_por_grupo.apply(
        lambda row: min(row["Demanda_grupo_m2"], row["Capacidade_m2"]) if row["Capacidade_m2"] > 0 else 0,
        axis=1
    )
    
    consumo_por_grupo["Fator_alocacao"] = consumo_por_grupo.apply(
        lambda row: row["Consumido_total_m2"] / row["Demanda_grupo_m2"]
        if row["Demanda_grupo_m2"] > 0 else 1.0,
        axis=1
    )
    
    alocado = df_demanda.merge(
        consumo_por_grupo[["Ano", "Mes", "Recipiente", "Estufa", "Capacidade_m2", 
                            "Fator_alocacao", "Demanda_total_m2", "Demanda_efetiva_m2", 
                            "Consumido_total_m2", "Tipo_infra", "Demanda_grupo_m2"]],
        on=["Ano", "Mes", "Recipiente", "Estufa"],
        how="left"
    )
    
    alocado["Demanda_projeto_m2"] = alocado.apply(
        lambda row: quantidade_para_m2(row["Quantidade"], row["Recipiente"]),
        axis=1
    )
    
    alocado["Consumido_projeto_m2"] = alocado["Demanda_projeto_m2"] * alocado["Fator_alocacao"]
    
    alocado["Disponivel_grupo_m2"] = (alocado["Capacidade_m2"] - alocado["Demanda_grupo_m2"]).clip(lower=0)
    alocado["Uso_grupo_pct"] = alocado.apply(
        lambda row: round(row["Demanda_grupo_m2"] / row["Capacidade_m2"] * 100, 1) 
            if row["Capacidade_m2"] > 0 else 0,
        axis=1
    )
    
    alocado["Excesso_m2"] = (alocado["Demanda_grupo_m2"] - alocado["Capacidade_m2"]).clip(lower=0)
    alocado["Acima_Capacidade"] = alocado["Demanda_grupo_m2"] > alocado["Capacidade_m2"]
    
    # Calcular consumido proporcional por RECIPIENTE
    alocado["Consumido_recipiente_m2"] = alocado["Demanda_total_m2"] * alocado["Fator_alocacao"]
    
    alocado_final = alocado.groupby(["Ano", "Mes", "Projeto", "Recipiente", "Estufa"]).agg({
        "Quantidade": "sum",
        "Capacidade_m2": "max",
        "Demanda_projeto_m2": "sum",
        "Consumido_projeto_m2": "sum",
        "Consumido_total_m2": "first",
        "Consumido_recipiente_m2": "first",
        "Demanda_total_m2": "first",
        "Demanda_efetiva_m2": "first",
        "Demanda_grupo_m2": "first",
        "Disponivel_grupo_m2": "first",
        "Uso_grupo_pct": "first",
        "Excesso_m2": "first",
        "Acima_Capacidade": "first",
        "Tipo_infra": "first"
    }).reset_index()
    
    df_alocado = alocado_final.copy()
    df_alocado["Demanda_unidades"] = df_alocado["Quantidade"]
    df_alocado["Consumido"] = df_alocado["Consumido_projeto_m2"].round(2)
    df_alocado["Capacidade"] = df_alocado["Capacidade_m2"].round(2)
    df_alocado["Disponivel"] = df_alocado["Disponivel_grupo_m2"].round(2)
    df_alocado["Uso"] = df_alocado["Uso_grupo_pct"]
    df_alocado["Excesso"] = df_alocado["Excesso_m2"].round(2)
    
    # Consumido_total_m2 agora mostra o consumo proporcional do recipiente específico
    df_alocado["Consumido_total_m2"] = df_alocado["Consumido_recipiente_m2"]
    
    return df_demanda, df_fases, df_alocado


# =====================================================
# 🤖 AGENTE DE IA - OTIMIZAÇÃO DE ALOCAÇÃO
# =====================================================

@app.route("/simulacao/agente_ia", methods=["POST"])
def simulacao_agente_ia():
    """
    Endpoint do Agente de IA para sugestão de alocação otimizada.
    
    Analisa a capacidade MÊS A MÊS para cada estufa e recipiente,
    identificando picos de ocupação e sugerindo otimizações.
    """
    global simulacoes_temp, df_demanda, df_fases, df
    
    try:
        # Obter parâmetros opcionais
        data = request.get_json() or {}
        usar_llm = data.get("usar_llm", False)
        api_key = data.get("api_key", None)
        
        # Recalcular dados de demanda e capacidade
        df_demanda, df_fases, df = calcular_demanda_e_alocacao()
        
        # =====================================================
        # ANÁLISE MENSAL - Dados corretos por mês
        # =====================================================
        from datetime import datetime
        hoje = datetime.now()
        ano_atual, mes_atual = hoje.year, hoje.month
        
        # Agrupa por Ano, Mes, Estufa, Recipiente
        df_mensal = df.groupby(["Ano", "Mes", "Estufa", "Recipiente"]).agg({
            "Consumido_total_m2": "first",
            "Capacidade": "first"
        }).reset_index()
        
        df_mensal["Disponivel"] = (df_mensal["Capacidade"] - df_mensal["Consumido_total_m2"]).clip(lower=0)
        df_mensal["Uso_pct"] = (df_mensal["Consumido_total_m2"] / df_mensal["Capacidade"] * 100).round(1)
        df_mensal["Uso_pct"] = df_mensal["Uso_pct"].clip(lower=0, upper=100)
        
        # Filtrar meses futuros ou atual
        df_futuro = df_mensal[(df_mensal["Ano"] > ano_atual) | 
                              ((df_mensal["Ano"] == ano_atual) & (df_mensal["Mes"] >= mes_atual))]
        
        if df_futuro.empty:
            df_futuro = df_mensal
        
        # Calcular métricas por estufa (agregando todos os recipientes)
        capacidade_por_estufa_mes = df_futuro.groupby(["Ano", "Mes", "Estufa"]).agg({
            "Consumido_total_m2": "sum",
            "Capacidade": "sum"
        }).reset_index()
        capacidade_por_estufa_mes["Uso_pct"] = (
            capacidade_por_estufa_mes["Consumido_total_m2"] / 
            capacidade_por_estufa_mes["Capacidade"] * 100
        ).round(1).clip(lower=0, upper=100)
        
        # Encontrar mês de pico para cada estufa
        picos = {}
        for estufa in ["CDV1", "CDV9"]:
            df_estufa = capacidade_por_estufa_mes[capacidade_por_estufa_mes["Estufa"] == estufa]
            if not df_estufa.empty:
                idx_max = df_estufa["Uso_pct"].idxmax()
                pico = df_estufa.loc[idx_max]
                picos[estufa] = {
                    "mes": f"{int(pico['Mes']):02d}/{int(pico['Ano'])}",
                    "uso_pct": round(pico["Uso_pct"], 1),
                    "consumido_m2": round(pico["Consumido_total_m2"], 1),
                    "capacidade_m2": round(pico["Capacidade"], 1)
                }
        
        # Capacidade atual (primeiro mês futuro)
        primeiro_mes = df_futuro.sort_values(["Ano", "Mes"]).head(1)
        if not primeiro_mes.empty:
            ano_ref = int(primeiro_mes.iloc[0]["Ano"])
            mes_ref = int(primeiro_mes.iloc[0]["Mes"])
        else:
            ano_ref, mes_ref = ano_atual, mes_atual
        
        # Dados do mês de referência por estufa/recipiente
        capacidade_mes_ref = df_mensal[
            (df_mensal["Ano"] == ano_ref) & (df_mensal["Mes"] == mes_ref)
        ].copy()
        
        capacidade_lista = capacidade_mes_ref.to_dict('records')
        
        # Preparar lista de simulações pendentes
        simulacoes_para_analise = [
            {
                "id": s.get("id", 0),
                "nome": s.get("nome", ""),
                "estufa": s.get("estufa", ""),
                "recipiente": s.get("recipiente", ""),
                "quantidade": s.get("quantidade", 0),
                "demanda_m2": s.get("demanda_m2", 0),
                "tempo_meses": s.get("tempo_meses", 0),
                "data_inicio": s.get("data_inicio", ""),
                "concomitante": s.get("concomitante", 0)
            }
            for s in simulacoes_temp
        ]
        
        # Executar análise do agente com dados mensais
        resultado = agente_ia.analisar_e_recomendar(
            capacidade_atual=capacidade_lista,
            simulacoes_pendentes=simulacoes_para_analise,
            usar_llm=usar_llm,
            api_key=api_key
        )
        
        # Adicionar informações de pico ao resultado
        resultado["picos_ocupacao"] = picos
        resultado["mes_referencia"] = f"{mes_ref:02d}/{ano_ref}"
        
        # Timeline mensal (próximos 12 meses)
        timeline = []
        for _, row in capacidade_por_estufa_mes.sort_values(["Ano", "Mes"]).head(24).iterrows():
            timeline.append({
                "mes": f"{int(row['Mes']):02d}/{int(row['Ano'])}",
                "estufa": row["Estufa"],
                "uso_pct": round(row["Uso_pct"], 1),
                "consumido_m2": round(row["Consumido_total_m2"], 1)
            })
        resultado["timeline_mensal"] = timeline
        
        # =====================================================
        # DADOS DETALHADOS DE DISPONIBILIDADE POR MÊS
        # =====================================================
        
        # Disponibilidade mensal por estufa/recipiente (próximos 12 meses)
        disponibilidade = []
        df_futuro_sorted = df_futuro.sort_values(["Ano", "Mes"])
        for _, row in df_futuro_sorted.iterrows():
            disponibilidade.append({
                "mes": f"{int(row['Mes']):02d}/{int(row['Ano'])}",
                "ano": int(row["Ano"]),
                "mes_num": int(row["Mes"]),
                "estufa": row["Estufa"],
                "recipiente": row["Recipiente"],
                "capacidade_m2": round(float(row["Capacidade"]), 1),
                "consumido_m2": round(float(row["Consumido_total_m2"]), 1),
                "disponivel_m2": round(float(row["Disponivel"]), 1),
                "uso_pct": round(float(row["Uso_pct"]), 1)
            })
        resultado["disponibilidade_mensal"] = disponibilidade
        
        # Melhores meses por recipiente/estufa (top 3 com mais disponibilidade)
        melhores_meses = {}
        for estufa in ["CDV1", "CDV9"]:
            melhores_meses[estufa] = {}
            for recipiente in ["Bandeja", "Citropote", "Vaso"]:
                df_filtro = df_futuro[
                    (df_futuro["Estufa"] == estufa) & 
                    (df_futuro["Recipiente"] == recipiente)
                ].copy()
                if not df_filtro.empty:
                    top = df_filtro.nlargest(3, "Disponivel")
                    melhores_meses[estufa][recipiente] = [
                        {
                            "mes": f"{int(r['Mes']):02d}/{int(r['Ano'])}",
                            "disponivel_m2": round(float(r["Disponivel"]), 1),
                            "uso_pct": round(float(r["Uso_pct"]), 1)
                        }
                        for _, r in top.iterrows()
                    ]
        resultado["melhores_meses"] = melhores_meses
        
        # Comparativo CDV1 vs CDV9 por recipiente (mês de referência)
        comparativo = {}
        for recipiente in ["Bandeja", "Citropote", "Vaso"]:
            cdv1_d = capacidade_mes_ref[
                (capacidade_mes_ref["Estufa"] == "CDV1") & 
                (capacidade_mes_ref["Recipiente"] == recipiente)
            ]
            cdv9_d = capacidade_mes_ref[
                (capacidade_mes_ref["Estufa"] == "CDV9") & 
                (capacidade_mes_ref["Recipiente"] == recipiente)
            ]
            disp_cdv1 = round(float(cdv1_d.iloc[0]["Disponivel"]), 1) if len(cdv1_d) > 0 else 0
            disp_cdv9 = round(float(cdv9_d.iloc[0]["Disponivel"]), 1) if len(cdv9_d) > 0 else 0
            uso_cdv1 = round(float(cdv1_d.iloc[0]["Uso_pct"]), 1) if len(cdv1_d) > 0 else 0
            uso_cdv9 = round(float(cdv9_d.iloc[0]["Uso_pct"]), 1) if len(cdv9_d) > 0 else 0
            cap_cdv1 = round(float(cdv1_d.iloc[0]["Capacidade"]), 1) if len(cdv1_d) > 0 else 0
            cap_cdv9 = round(float(cdv9_d.iloc[0]["Capacidade"]), 1) if len(cdv9_d) > 0 else 0
            
            comparativo[recipiente] = {
                "CDV1": {
                    "capacidade_m2": cap_cdv1,
                    "disponivel_m2": disp_cdv1,
                    "uso_pct": uso_cdv1
                },
                "CDV9": {
                    "capacidade_m2": cap_cdv9,
                    "disponivel_m2": disp_cdv9,
                    "uso_pct": uso_cdv9
                },
                "melhor": "CDV1" if disp_cdv1 > disp_cdv9 else "CDV9"
            }
        resultado["comparativo_estufas"] = comparativo
        
        # Janelas de oportunidade - períodos com menor ocupação geral
        janelas = []
        for _, row in capacidade_por_estufa_mes.sort_values(["Uso_pct"]).head(6).iterrows():
            janelas.append({
                "mes": f"{int(row['Mes']):02d}/{int(row['Ano'])}",
                "estufa": row["Estufa"],
                "uso_pct": round(float(row["Uso_pct"]), 1),
                "disponivel_m2": round(float(row["Capacidade"] - row["Consumido_total_m2"]), 1)
            })
        resultado["janelas_oportunidade"] = janelas
        
        return jsonify({
            "ok": True,
            "recomendacao": resultado
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            "ok": False,
            "erro": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route("/simulacao/aplicar_sugestao", methods=["POST"])
def aplicar_sugestao_ia():
    """
    Aplica uma sugestão específica do agente de IA.
    Atualiza a simulação conforme a sugestão.
    """
    global simulacoes_temp
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "erro": "Dados inválidos"}), 400
        
        fase_id = data.get("fase_id")
        tipo = data.get("tipo")
        sugerido = data.get("sugerido", {})
        
        # Encontrar a simulação
        simulacao = next((s for s in simulacoes_temp if s.get("id") == fase_id), None)
        if not simulacao:
            return jsonify({"ok": False, "erro": f"Simulação ID {fase_id} não encontrada"}), 404
        
        alteracoes = []
        
        if tipo == "troca_estufa" and "estufa" in sugerido:
            simulacao["estufa"] = sugerido["estufa"]
            alteracoes.append(f"Estufa alterada para {sugerido['estufa']}")
            
        if tipo == "troca_recipiente" and "recipiente" in sugerido:
            simulacao["recipiente"] = sugerido["recipiente"]
            simulacao["demanda_m2"] = quantidade_para_m2(
                simulacao["quantidade"], 
                sugerido["recipiente"]
            )
            alteracoes.append(f"Recipiente alterado para {sugerido['recipiente']}")
            
        if tipo == "ajuste_concomitancia" and "concomitante" in sugerido:
            simulacao["concomitante"] = sugerido["concomitante"]
            alteracoes.append(f"Concomitância ajustada para {sugerido['concomitante']} meses")
        
        # Atualizar no banco de dados
        db.atualizar_simulacao(
            simulacao_id=fase_id,
            estufa=simulacao.get("estufa"),
            recipiente=simulacao.get("recipiente"),
            quantidade=simulacao.get("quantidade"),
            tempo_meses=simulacao.get("tempo_meses")
        )
        
        return jsonify({
            "ok": True,
            "mensagem": "Sugestão aplicada com sucesso",
            "alteracoes": alteracoes,
            "simulacao_atualizada": simulacao
        })
        
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500


# =====================================================
# 🔍 AUDITORIA - MESES ACIMA DA CAPACIDADE
# =====================================================
@app.route("/auditoria")
def auditoria():
    """
    Exibe auditoria: meses/recipientes/estufas acima da capacidade,
    detalhando quais projetos contribuem para o excesso.
    """
    global df_demanda, df_fases, df
    df_demanda, df_fases, df = calcular_demanda_e_alocacao()

    filtro_ano = request.args.get("ano", type=int)
    filtro_estufa = request.args.get("estufa")
    filtro_recipiente = request.args.get("recipiente")

    if df.empty:
        return render_template(
            "auditoria.html",
            alertas=[],
            total_alertas=0,
            total_excesso_m2=0,
            meses_criticos=0,
            anos=[], estufas=[], recipientes=[]
        )

    alertas = []
    
    # Agrupar por tipo de infraestrutura para detectar excesso compartilhado
    # Mesas: Bandeja + Citropote compartilham → verificar demanda do GRUPO
    # Blocos: Vaso usa independente → verificar demanda individual
    df_audit = df.drop_duplicates(subset=["Ano", "Mes", "Recipiente", "Estufa"])
    
    # Primeiro: detectar meses/estufas com excesso no GRUPO (mesas ou blocos)
    alertas_gerados = set()  # Para evitar duplicatas
    
    for (ano_g, mes_g, est_g), grupo_estufa in df_audit.groupby(["Ano", "Mes", "Estufa"]):
        # Verificar cada tipo de infraestrutura
        for tipo_infra in ["Mesa", "Bloco"]:
            recs_tipo = grupo_estufa[grupo_estufa["Tipo_infra"] == tipo_infra]
            if recs_tipo.empty:
                continue
            
            # Demanda e capacidade do grupo (já calculados corretamente)
            demanda_grupo = recs_tipo["Demanda_grupo_m2"].iloc[0]
            cap_grupo = recs_tipo["Capacidade"].iloc[0]
            excesso_grupo = recs_tipo["Excesso"].iloc[0]
            
            if excesso_grupo <= 0:
                continue  # Sem excesso neste grupo
            
            uso_pct = round((demanda_grupo / cap_grupo) * 100, 1) if cap_grupo > 0 else 0
            
            # Para cada recipiente neste grupo com excesso, gerar alerta
            for _, rec_row in recs_tipo.iterrows():
                rec_g = rec_row["Recipiente"]
                chave = (ano_g, mes_g, est_g, rec_g)
                if chave in alertas_gerados:
                    continue
                alertas_gerados.add(chave)
                
                # Buscar projetos deste recipiente neste mês/estufa
                df_projetos = df[
                    (df["Ano"] == ano_g) & (df["Mes"] == mes_g) & 
                    (df["Estufa"] == est_g) & (df["Recipiente"] == rec_g)
                ]
                
                projetos_lista = []
                for _, row in df_projetos.iterrows():
                    dem_m2 = row["Demanda_projeto_m2"] if "Demanda_projeto_m2" in row else row["Demanda_unidades"] * tamanho_recipientes.get(rec_g, 1)
                    projetos_lista.append({
                        "nome": row["Projeto"],
                        "demanda_un": int(row["Demanda_unidades"]),
                        "demanda_m2": round(dem_m2, 2)
                    })
                projetos_lista = sorted(projetos_lista, key=lambda x: x["demanda_m2"], reverse=True)
                
                # Recipientes que compartilham este grupo
                outros_recs = [r for r in recs_tipo["Recipiente"].unique() if r != rec_g]
                compartilhado_com = ", ".join(outros_recs) if outros_recs else None
                
                alertas.append({
                    "ano": int(ano_g),
                    "mes": int(mes_g),
                    "periodo": f"{int(mes_g):02d}/{int(ano_g)}",
                    "estufa": est_g,
                    "recipiente": rec_g,
                    "tipo_infra": tipo_infra,
                    "capacidade": round(cap_grupo, 2),
                    "demanda": round(rec_row["Demanda_total_m2"], 2),
                    "demanda_grupo": round(demanda_grupo, 2),
                    "excesso": round(excesso_grupo, 2),
                    "uso": uso_pct,
                    "compartilhado_com": compartilhado_com,
                    "projetos": projetos_lista
                })

    # Aplicar filtros
    if filtro_ano:
        alertas = [a for a in alertas if a["ano"] == filtro_ano]
    if filtro_estufa:
        alertas = [a for a in alertas if a["estufa"] == filtro_estufa]
    if filtro_recipiente:
        alertas = [a for a in alertas if a["recipiente"] == filtro_recipiente]

    alertas = sorted(alertas, key=lambda x: (-x["excesso"], x["ano"], x["mes"]))

    # Total de excesso sem duplicar (mesas compartilhadas geram 2 alertas com mesmo excesso)
    excesso_visto = set()
    total_excesso = 0
    for a in alertas:
        chave_excesso = (a["ano"], a["mes"], a["estufa"], a.get("tipo_infra", ""))
        if chave_excesso not in excesso_visto:
            excesso_visto.add(chave_excesso)
            total_excesso += a["excesso"]
    total_excesso = round(total_excesso, 2)
    meses_criticos = len(set((a["ano"], a["mes"]) for a in alertas))

    return render_template(
        "auditoria.html",
        alertas=alertas,
        total_alertas=len(alertas),
        total_excesso_m2=total_excesso,
        meses_criticos=meses_criticos,
        anos=sorted(df["Ano"].unique()),
        estufas=sorted(df["Estufa"].unique()),
        recipientes=sorted(df["Recipiente"].unique())
    )


# =====================================================
# INICIALIZAÇÃO DO BANCO DE DADOS
# =====================================================
# Garantir que o banco está inicializado e com o schema correto
db.init_database()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
