# 🌱 Sistema de Gestão de Capacidade de Estufas

> Aplicação web para planejamento, monitoramento e otimização da ocupação de estufas agrícolas, com gerenciamento de projetos por fases, simulações e suporte a agente de inteligência artificial.

---

## 📋 Descrição

O **Sistema de Gestão de Capacidade de Estufas** é uma aplicação web desenvolvida em Python/Flask que permite gerenciar a capacidade física de estufas de produção de mudas. O sistema controla a alocação de espaço em metros quadrados (m²) para diferentes tipos de recipientes, distribui projetos ao longo do tempo e emite alertas quando a ocupação ultrapassa os limites de capacidade.

A unidade de medida central é o **metro quadrado (m²)**, que representa a área física real ocupada por cada recipiente dentro da estrutura de mesas e blocos das estufas.

---

## 🎯 Objetivo

- Planejar e visualizar a ocupação de estufas ao longo do tempo  
- Gerenciar projetos com múltiplas fases de cultivo  
- Simular novos projetos antes de confirmar a alocação  
- Identificar gargalos e períodos de sobrecapacidade  
- Otimizar a distribuição de projetos entre estufas com apoio de IA  

---

## ✨ Funcionalidades

### 🏠 Dashboard Principal (`/`)
- Cards de resumo com capacidade total, consumo e disponibilidade por estufa
- Barras de progresso coloridas (verde/amarelo/vermelho) conforme nível de ocupação
- **Gráfico de barras empilhadas**: consumido vs. disponível por mês
- **Heatmap** de ocupação mensal por estufa e recipiente
- **Gráfico de linha** de ocupação ao longo do tempo
- **Diagrama de Gantt** com as fases de cada projeto
- Tabela detalhada com filtros por ano, mês, estufa, projeto e recipiente

### 📁 Gestão de Projetos & Rotas (`/rotas`)
- Cadastro de projetos com nome, tipo, data de início e estufa de destino
- Definição de **rotas**: sequência de fases por recipiente, duração (meses) e quantidade
- Suporte a **fases concomitantes** (sobreposição temporal entre fases consecutivas)
- Edição e exclusão de projetos (exclusão permanente ou desativação com preservação de histórico)
- Resetar rota de um projeto para a configuração padrão do seu tipo

### 🧪 Simulação (`/simulacao`)
- Adicionar itens de simulação avulsos (recipiente, quantidade, tempo, estufa, data)
- Simular projetos completos (com todas as suas fases) antes de confirmar
- Simular uma rota inteira de um tipo de projeto
- Visualizar o impacto da simulação no gráfico de capacidade existente
- **Aceitar simulação**: converte os itens simulados em projeto real no banco de dados
- **Cancelar simulação**: descarta todos os itens sem salvar

### 🤖 Agente de IA (`/simulacao/agente_ia`)
- Análise automática da alocação atual e das simulações pendentes
- Geração de **três cenários**: Baseline, Otimizado e Agressivo
- Cálculo de score por cenário considerando ocupação média, balanceamento entre estufas e risco de gargalo
- Sugestões automáticas de: troca de estufa, ajuste de data, ajuste de concomitância
- Aplicação de sugestões individuais diretamente na simulação

### 🔍 Auditoria (`/auditoria`)
- Lista de todos os meses com capacidade ultrapassada
- Detalhamento por estufa, recipiente e tipo de infraestrutura (mesas ou blocos)
- Identificação dos projetos que contribuem para o excesso
- Filtros por ano, estufa e recipiente
- Indicadores de excesso em m² e percentual de uso

### 📤 Exportação
- **Excel** (`/excel`): exporta toda a demanda calculada em planilha `.xlsx`
- **PDF** (`/pdf`): gera relatório formatado com tabelas e resumo de capacidade usando ReportLab

---

## 🏗️ Modelo Físico

### Tipos de Recipientes

| Recipiente  | Tamanho (m²/unid) | Infraestrutura |
|-------------|-------------------|----------------|
| Bandeja     | 0,16 m²           | Mesa           |
| Citropote   | 0,02 m²           | Mesa           |
| Vaso        | 0,30 m²           | Bloco (4 vasos/bloco) |

### Regras de Compartilhamento

- **Mesas**: Bandejas e Citropotes **compartilham** a mesma área. A ocupação é calculada como a soma das demandas dos dois recipientes.
- **Blocos**: Vasos utilizam capacidade **independente** (não dividem espaço com outros recipientes).

---

## 🔁 Fluxo da Aplicação

```
1. Cadastrar Projeto
      ↓
2. Definir Rota (fases: recipiente + meses + quantidade)
      ↓
3. Dashboard exibe demanda calculada vs. capacidade disponível
      ↓
4. [Opcional] Criar Simulação de novo projeto
      ↓
5. [Opcional] Executar Agente de IA para sugestões de otimização
      ↓
6. Aceitar Simulação → Projeto salvo no banco de dados
      ↓
7. Auditoria monitora meses com sobrecapacidade
      ↓
8. Exportar relatório em Excel ou PDF
```

---

## 📁 Estrutura de Pastas

```
capacidade_estufa/
├── venv/
│   ├── app.py                  # Aplicação Flask principal (rotas, lógica de negócio)
│   ├── database.py             # Módulo de acesso ao SQLite (CRUD de projetos, rotas, simulações)
│   ├── agente_ia.py            # Agente de IA para otimização de alocação
│   ├── capacidade_estufa.db    # Banco de dados SQLite
│   ├── rotas_config.json       # Configuração legada de rotas personalizadas (JSON)
│   └── templates/
│       ├── index.html          # Dashboard principal
│       ├── rotas.html          # Gestão de projetos e rotas
│       ├── simulacao.html      # Tela de simulação
│       ├── auditoria.html      # Auditoria de capacidade
│       ├── projetos.html       # Listagem de projetos
│       └── index_backup.html   # Backup do template principal
├── requirements.txt            # Dependências Python
└── README.md                   # Esta documentação
```

---

## 🛠️ Tecnologias Utilizadas

| Tecnologia     | Versão / Uso                                           |
|----------------|--------------------------------------------------------|
| **Python 3**   | Linguagem principal                                    |
| **Flask**      | Framework web (rotas, templates Jinja2, sessões)       |
| **SQLite**     | Banco de dados relacional embutido                     |
| **Pandas**     | Manipulação e análise de dados tabulares               |
| **NumPy**      | Operações numéricas auxiliares                         |
| **Plotly**     | Geração de gráficos interativos (barras, heatmap, Gantt) |
| **ReportLab**  | Geração de relatórios em PDF                           |
| **python-dateutil** | Aritmética de datas com `relativedelta`           |

---

## ⚙️ Instalação e Execução

### Pré-requisitos

- Python 3.9 ou superior
- pip

### 1. Clonar o repositório

```bash
git clone <url-do-repositorio>
cd capacidade_estufa
```

### 2. Criar e ativar ambiente virtual

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python -m venv venv
source venv/bin/activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

> **Nota:** O `requirements.txt` lista as dependências principais. Para gerar PDFs, instale também o ReportLab:
> ```bash
> pip install reportlab
> ```

### 4. Configurar a `SECRET_KEY`

Antes de executar em produção, defina a chave secreta via variável de ambiente:

```bash
# Windows (PowerShell)
$env:FLASK_SECRET_KEY = "sua_chave_secreta_aqui"

# Linux/macOS
export FLASK_SECRET_KEY="sua_chave_secreta_aqui"
```

> ⚠️ Nunca utilize a chave padrão em ambiente de produção.

### 5. Executar a aplicação

```bash
cd venv
python app.py
```

A aplicação estará disponível em: `http://localhost:5000`

O banco de dados SQLite (`capacidade_estufa.db`) será criado automaticamente na primeira execução.

---

## 🗄️ Estrutura do Banco de Dados

```
projetos          → Cadastro de projetos (nome, tipo, data_inicio, estufa)
rotas             → Fases de cada projeto (recipiente, meses, quantidade, concomitante)
simulacoes        → Itens de simulação pendentes (antes de aceitar)
capacidades       → Capacidade por setor/recipiente (m²)
tamanho_recipientes → Tamanho físico de cada tipo de recipiente
historico_demanda → Histórico calculado de demanda por mês/projeto
```

---

## 💡 Exemplos de Uso

### Cadastrar um projeto com rota personalizada

1. Acesse `/rotas`
2. Preencha: **Nome**, **Tipo**, **Data de início**, **Estufa**
3. Defina as fases: recipiente → quantidade → duração (meses) → concomitância
4. Clique em **Salvar**
5. O Dashboard (`/`) exibirá o impacto imediatamente

### Simular um novo projeto antes de confirmar

1. Acesse `/simulacao`
2. Clique em **Adicionar projeto à simulação**
3. Escolha o tipo de projeto e data de início
4. Visualize no gráfico como o projeto afeta a capacidade futura
5. Se adequado, clique em **Aceitar simulação**

### Executar o Agente de IA

1. Adicione itens à simulação
2. Na tela de simulação, clique em **Analisar com IA**
3. O agente apresentará três cenários com scores
4. Aplique sugestões individuais ou aceite o cenário recomendado

---

## 📊 Níveis de Ocupação

| Nível      | Threshold | Cor      |
|------------|-----------|----------|
| Seguro     | < 70%     | 🟢 Verde  |
| Atenção    | 70–85%    | 🟡 Amarelo |
| Crítico    | 85–100%   | 🔴 Vermelho |
| Excesso    | > 100%    | ⚫ Sobrecapacidade |

---

## 🔮 Possíveis Melhorias Futuras

- [ ] **Autenticação de usuários**: controle de acesso por perfil (administrador, visualizador)
- [ ] **Histórico de alterações**: log de auditoria para rastrear mudanças nos projetos
- [ ] **Notificações automáticas**: alertas por e-mail quando ocupação atingir nível crítico
- [ ] **API REST**: endpoints para integração com outros sistemas
- [ ] **Integração com LLM**: habilitar explanações detalhadas do Agente de IA via OpenAI (estrutura já presente no código)
- [ ] **Importação via planilha**: carregar múltiplos projetos via upload de Excel
- [ ] **Multi-unidade**: suporte a mais de dois ambientes de cultivo
- [ ] **Containerização**: Dockerfile para facilitar deploy em ambientes de produção
- [ ] **Testes automatizados**: cobertura de testes unitários e de integração

---

## 📄 Licença

Este projeto é de uso interno. Consulte o responsável pelo repositório para informações sobre licenciamento e distribuição.
