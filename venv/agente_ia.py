# -*- coding: utf-8 -*-
"""
================================================================================
AGENTE DE IA PARA OTIMIZAÇÃO DE ALOCAÇÃO DE CAPACIDADE EM ESTUFAS
================================================================================

Este módulo implementa um sistema inteligente de recomendação para otimização
da alocação de recipientes (Bandeja, Citropote, Vaso) nas estufas CDV1 e CDV9.

Funcionalidades:
- Análise de capacidade atual e projetada
- Geração de cenários alternativos (baseline, otimizado, agressivo)
- Recomendações de troca de estufa, recipiente, data ou concomitância
- Integração opcional com LLM (OpenAI) para explicações detalhadas

Autor: Sistema de Capacidade Estufa
Data: 2026
================================================================================
"""

import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import os

# ================================================================================
# CONSTANTES E CONFIGURAÇÕES
# ================================================================================

# Tamanhos dos recipientes em m²
TAMANHO_RECIPIENTES = {
    "Bandeja": 0.16,
    "Citropote": 0.02,
    "Vaso": 0.3
}

# Capacidades totais das estufas em m²
CAPACIDADE_ESTUFAS = {
    "CDV1": 2936.4,
    "CDV9": 2375.2
}

# Limites de ocupação (%)
LIMITE_SEGURO = 70       # Verde - OK
LIMITE_ATENCAO = 85      # Amarelo - Atenção
LIMITE_CRITICO = 100     # Vermelho - Crítico

# Pesos para cálculo de score de otimização
PESO_OCUPACAO = 0.4           # Priorizar menor ocupação
PESO_BALANCEAMENTO = 0.3      # Priorizar equilíbrio entre estufas
PESO_RISCO_GARGALO = 0.3      # Evitar gargalos futuros


# ================================================================================
# CLASSES DE DADOS
# ================================================================================

class TipoSugestao(Enum):
    """Tipos de sugestões que o agente pode fazer."""
    TROCA_ESTUFA = "troca_estufa"
    TROCA_RECIPIENTE = "troca_recipiente"
    AJUSTE_DATA = "ajuste_data"
    AJUSTE_CONCOMITANCIA = "ajuste_concomitancia"
    MANTER_ORIGINAL = "manter_original"


class NivelRisco(Enum):
    """Níveis de risco da alocação."""
    BAIXO = "baixo"
    MEDIO = "medio"
    ALTO = "alto"
    CRITICO = "critico"


@dataclass
class CapacidadeEstufa:
    """Representa a capacidade de uma estufa."""
    estufa: str
    recipiente: str
    capacidade_m2: float
    consumido_m2: float
    disponivel_m2: float
    ocupacao_pct: float
    nivel_risco: str


@dataclass
class FaseSimulacao:
    """Representa uma fase de simulação."""
    id: int
    nome: str
    estufa: str
    recipiente: str
    quantidade: int
    demanda_m2: float
    tempo_meses: int
    concomitante: int
    data_inicio: str


@dataclass
class Sugestao:
    """Representa uma sugestão de otimização."""
    tipo: str
    fase_id: int
    fase_nome: str
    original: Dict[str, Any]
    sugerido: Dict[str, Any]
    motivo: str
    impacto_m2: float
    economia_ocupacao_pct: float
    prioridade: int  # 1 = alta, 2 = média, 3 = baixa


@dataclass
class Cenario:
    """Representa um cenário de alocação."""
    nome: str
    descricao: str
    ocupacao_cdv1_pct: float
    ocupacao_cdv9_pct: float
    ocupacao_media_pct: float
    balanceamento_pct: float  # Diferença entre estufas
    risco_gargalo: str
    sugestoes: List[Dict]
    score: float


@dataclass
class RecomendacaoIA:
    """Recomendação completa do agente de IA."""
    timestamp: str
    contexto: Dict[str, Any]
    cenario_baseline: Dict
    cenario_otimizado: Dict
    cenario_agressivo: Dict
    cenario_recomendado: str
    sugestoes_prioritarias: List[Dict]
    explicacao_tecnica: str
    alertas: List[str]
    metricas: Dict[str, Any]


# ================================================================================
# FUNÇÕES AUXILIARES
# ================================================================================

def quantidade_para_m2(quantidade: int, recipiente: str) -> float:
    """Converte quantidade de recipientes para m²."""
    return quantidade * TAMANHO_RECIPIENTES.get(recipiente, 0)


def m2_para_quantidade(area_m2: float, recipiente: str) -> int:
    """Converte m² para quantidade de recipientes."""
    tamanho = TAMANHO_RECIPIENTES.get(recipiente, 1)
    return int(area_m2 / tamanho) if tamanho > 0 else 0


def calcular_nivel_risco(ocupacao_pct: float) -> str:
    """Determina o nível de risco baseado na ocupação."""
    if ocupacao_pct >= LIMITE_CRITICO:
        return NivelRisco.CRITICO.value
    elif ocupacao_pct >= LIMITE_ATENCAO:
        return NivelRisco.ALTO.value
    elif ocupacao_pct >= LIMITE_SEGURO:
        return NivelRisco.MEDIO.value
    else:
        return NivelRisco.BAIXO.value


def calcular_score_cenario(
    ocupacao_cdv1: float,
    ocupacao_cdv9: float,
    tem_ultrapassagem: bool
) -> float:
    """
    Calcula o score de qualidade de um cenário.
    Quanto MENOR o score, MELHOR o cenário.
    """
    # Ocupação média (queremos minimizar)
    ocupacao_media = (ocupacao_cdv1 + ocupacao_cdv9) / 2
    
    # Desbalanceamento (diferença entre estufas - queremos minimizar)
    desbalanceamento = abs(ocupacao_cdv1 - ocupacao_cdv9)
    
    # Penalidade por ultrapassagem
    penalidade_ultrapassagem = 100 if tem_ultrapassagem else 0
    
    # Score composto
    score = (
        ocupacao_media * PESO_OCUPACAO +
        desbalanceamento * PESO_BALANCEAMENTO +
        penalidade_ultrapassagem * PESO_RISCO_GARGALO
    )
    
    return round(score, 2)


# ================================================================================
# GERADOR DE CONTEXTO
# ================================================================================

def gerar_contexto_simulacao(
    capacidade_atual: List[Dict],
    simulacoes_pendentes: List[Dict],
    df_demanda: any = None
) -> Dict[str, Any]:
    """
    Gera o contexto completo para análise do agente de IA.
    
    Args:
        capacidade_atual: Lista de dicts com capacidade por estufa/recipiente
        simulacoes_pendentes: Lista de simulações pendentes
        df_demanda: DataFrame opcional com demanda futura
    
    Returns:
        Contexto estruturado para análise
    """
    contexto = {
        "timestamp": datetime.now().isoformat(),
        "estufas": {},
        "simulacoes": [],
        "totais": {}
    }
    
    # Processar capacidade por estufa
    for estufa in ["CDV1", "CDV9"]:
        estufa_data = [c for c in capacidade_atual if c.get("Estufa") == estufa]
        
        total_capacidade = sum(c.get("Capacidade", 0) for c in estufa_data)
        total_consumido = sum(c.get("Consumido_total_m2", 0) for c in estufa_data)
        total_disponivel = total_capacidade - total_consumido
        ocupacao_pct = (total_consumido / total_capacidade * 100) if total_capacidade > 0 else 0
        
        contexto["estufas"][estufa] = {
            "capacidade_total_m2": round(total_capacidade, 2),
            "consumido_m2": round(total_consumido, 2),
            "disponivel_m2": round(total_disponivel, 2),
            "ocupacao_pct": round(ocupacao_pct, 1),
            "nivel_risco": calcular_nivel_risco(ocupacao_pct),
            "recipientes": {}
        }
        
        # Detalhar por recipiente
        for item in estufa_data:
            recipiente = item.get("Recipiente", "Desconhecido")
            contexto["estufas"][estufa]["recipientes"][recipiente] = {
                "capacidade_m2": round(item.get("Capacidade", 0), 2),
                "consumido_m2": round(item.get("Consumido_total_m2", 0), 2),
                "disponivel_m2": round(item.get("Disponivel", 0), 2),
                "ocupacao_pct": round(item.get("Uso_pct", 0), 1)
            }
    
    # Processar simulações pendentes
    total_simulacao_m2 = 0
    for sim in simulacoes_pendentes:
        demanda_m2 = sim.get("demanda_m2", 0)
        total_simulacao_m2 += demanda_m2
        
        contexto["simulacoes"].append({
            "id": sim.get("id", 0),
            "nome": sim.get("nome", ""),
            "estufa": sim.get("estufa", ""),
            "recipiente": sim.get("recipiente", ""),
            "quantidade": sim.get("quantidade", 0),
            "demanda_m2": round(demanda_m2, 2),
            "tempo_meses": sim.get("tempo_meses", 0),
            "data_inicio": sim.get("data_inicio", ""),
            "concomitante": sim.get("concomitante", 0)
        })
    
    # Totais
    contexto["totais"] = {
        "capacidade_sistema_m2": round(
            sum(e["capacidade_total_m2"] for e in contexto["estufas"].values()), 2
        ),
        "consumido_atual_m2": round(
            sum(e["consumido_m2"] for e in contexto["estufas"].values()), 2
        ),
        "disponivel_atual_m2": round(
            sum(e["disponivel_m2"] for e in contexto["estufas"].values()), 2
        ),
        "simulacao_pendente_m2": round(total_simulacao_m2, 2),
        "ocupacao_atual_pct": round(
            sum(e["consumido_m2"] for e in contexto["estufas"].values()) /
            sum(e["capacidade_total_m2"] for e in contexto["estufas"].values()) * 100
            if sum(e["capacidade_total_m2"] for e in contexto["estufas"].values()) > 0 else 0, 1
        ),
        "num_simulacoes": len(simulacoes_pendentes)
    }
    
    return contexto


# ================================================================================
# ALGORITMO HEURÍSTICO DE OTIMIZAÇÃO
# ================================================================================

class AgenteOtimizacao:
    """
    Agente de IA para otimização de alocação de capacidade.
    Implementa algoritmos heurísticos para sugerir a melhor distribuição.
    """
    
    def __init__(self, contexto: Dict[str, Any]):
        self.contexto = contexto
        self.sugestoes: List[Sugestao] = []
        self.alertas: List[str] = []
    
    def analisar(self) -> RecomendacaoIA:
        """
        Executa análise completa e retorna recomendações.
        """
        # Verificar se há simulações para analisar
        if not self.contexto.get("simulacoes"):
            return self._criar_recomendacao_vazia()
        
        # Gerar cenários
        cenario_baseline = self._gerar_cenario_baseline()
        cenario_otimizado = self._gerar_cenario_otimizado()
        cenario_agressivo = self._gerar_cenario_agressivo()
        
        # Determinar melhor cenário
        cenarios = {
            "baseline": cenario_baseline,
            "otimizado": cenario_otimizado,
            "agressivo": cenario_agressivo
        }
        melhor_cenario = min(cenarios.items(), key=lambda x: x[1]["score"])[0]
        
        # Gerar alertas
        self._verificar_alertas()
        
        # Gerar explicação técnica
        explicacao = self._gerar_explicacao_tecnica(cenarios, melhor_cenario)
        
        # Criar recomendação final
        recomendacao = RecomendacaoIA(
            timestamp=datetime.now().isoformat(),
            contexto=self.contexto,
            cenario_baseline=cenario_baseline,
            cenario_otimizado=cenario_otimizado,
            cenario_agressivo=cenario_agressivo,
            cenario_recomendado=melhor_cenario,
            sugestoes_prioritarias=cenarios[melhor_cenario].get("sugestoes", [])[:5],
            explicacao_tecnica=explicacao,
            alertas=self.alertas,
            metricas=self._calcular_metricas(cenarios, melhor_cenario)
        )
        
        return recomendacao
    
    def _criar_recomendacao_vazia(self) -> RecomendacaoIA:
        """Cria recomendação quando não há simulações."""
        return RecomendacaoIA(
            timestamp=datetime.now().isoformat(),
            contexto=self.contexto,
            cenario_baseline={"nome": "baseline", "score": 0, "sugestoes": []},
            cenario_otimizado={"nome": "otimizado", "score": 0, "sugestoes": []},
            cenario_agressivo={"nome": "agressivo", "score": 0, "sugestoes": []},
            cenario_recomendado="baseline",
            sugestoes_prioritarias=[],
            explicacao_tecnica="Nenhuma simulacao pendente para analisar.",
            alertas=["Adicione simulacoes para obter recomendacoes de otimizacao."],
            metricas={}
        )
    
    def _gerar_cenario_baseline(self) -> Dict:
        """
        Cenário baseline: mantém alocação original das simulações.
        """
        ocupacao_cdv1 = self.contexto["estufas"]["CDV1"]["ocupacao_pct"]
        ocupacao_cdv9 = self.contexto["estufas"]["CDV9"]["ocupacao_pct"]
        
        # Calcular impacto das simulações
        for sim in self.contexto["simulacoes"]:
            estufa = sim["estufa"]
            demanda = sim["demanda_m2"]
            capacidade = self.contexto["estufas"][estufa]["capacidade_total_m2"]
            
            if estufa == "CDV1":
                ocupacao_cdv1 += (demanda / capacidade * 100) if capacidade > 0 else 0
            else:
                ocupacao_cdv9 += (demanda / capacidade * 100) if capacidade > 0 else 0
        
        tem_ultrapassagem = ocupacao_cdv1 > 100 or ocupacao_cdv9 > 100
        
        return {
            "nome": "baseline",
            "descricao": "Mantem a alocacao original conforme definido nas simulacoes",
            "ocupacao_cdv1_pct": round(ocupacao_cdv1, 1),
            "ocupacao_cdv9_pct": round(ocupacao_cdv9, 1),
            "ocupacao_media_pct": round((ocupacao_cdv1 + ocupacao_cdv9) / 2, 1),
            "balanceamento_pct": round(abs(ocupacao_cdv1 - ocupacao_cdv9), 1),
            "risco_gargalo": calcular_nivel_risco(max(ocupacao_cdv1, ocupacao_cdv9)),
            "sugestoes": [],
            "score": calcular_score_cenario(ocupacao_cdv1, ocupacao_cdv9, tem_ultrapassagem)
        }
    
    def _gerar_cenario_otimizado(self) -> Dict:
        """
        Cenário otimizado: redistribui para balancear carga e evitar >85%.
        """
        sugestoes = []
        ocupacao_cdv1 = self.contexto["estufas"]["CDV1"]["ocupacao_pct"]
        ocupacao_cdv9 = self.contexto["estufas"]["CDV9"]["ocupacao_pct"]
        
        cap_cdv1 = self.contexto["estufas"]["CDV1"]["capacidade_total_m2"]
        cap_cdv9 = self.contexto["estufas"]["CDV9"]["capacidade_total_m2"]
        
        # Analisar cada simulação
        for sim in self.contexto["simulacoes"]:
            estufa_original = sim["estufa"]
            recipiente = sim["recipiente"]
            demanda = sim["demanda_m2"]
            
            # Calcular ocupação se alocar em cada estufa
            ocupacao_se_cdv1 = ocupacao_cdv1 + (demanda / cap_cdv1 * 100)
            ocupacao_se_cdv9 = ocupacao_cdv9 + (demanda / cap_cdv9 * 100)
            
            # Determinar melhor estufa (menor ocupação resultante)
            if estufa_original == "CDV1":
                ocupacao_atual = ocupacao_se_cdv1
                ocupacao_alternativa = ocupacao_se_cdv9
                estufa_alternativa = "CDV9"
            else:
                ocupacao_atual = ocupacao_se_cdv9
                ocupacao_alternativa = ocupacao_se_cdv1
                estufa_alternativa = "CDV1"
            
            # Verificar se troca melhora o balanceamento
            desbalanceamento_atual = abs(ocupacao_se_cdv1 - ocupacao_se_cdv9)
            
            # Simular troca
            if estufa_original == "CDV1":
                desbalanceamento_troca = abs(ocupacao_cdv1 - (ocupacao_cdv9 + demanda / cap_cdv9 * 100))
            else:
                desbalanceamento_troca = abs((ocupacao_cdv1 + demanda / cap_cdv1 * 100) - ocupacao_cdv9)
            
            # Sugerir troca se melhorar balanceamento E não ultrapassar 85%
            if (desbalanceamento_troca < desbalanceamento_atual and 
                ocupacao_alternativa < LIMITE_ATENCAO and
                ocupacao_atual > ocupacao_alternativa):
                
                economia = ocupacao_atual - ocupacao_alternativa
                
                sugestoes.append({
                    "tipo": TipoSugestao.TROCA_ESTUFA.value,
                    "fase_id": sim["id"],
                    "fase_nome": sim["nome"],
                    "original": {
                        "estufa": estufa_original,
                        "recipiente": recipiente,
                        "quantidade": sim["quantidade"]
                    },
                    "sugerido": {
                        "estufa": estufa_alternativa,
                        "recipiente": recipiente,
                        "quantidade": sim["quantidade"]
                    },
                    "motivo": f"Estufa {estufa_alternativa} tem menor ocupacao ({ocupacao_alternativa:.1f}% vs {ocupacao_atual:.1f}%)",
                    "impacto_m2": demanda,
                    "economia_ocupacao_pct": round(economia, 1),
                    "prioridade": 1 if economia > 10 else 2
                })
                
                # Atualizar ocupações simuladas
                if estufa_original == "CDV1":
                    ocupacao_cdv9 += demanda / cap_cdv9 * 100
                else:
                    ocupacao_cdv1 += demanda / cap_cdv1 * 100
            else:
                # Manter original
                if estufa_original == "CDV1":
                    ocupacao_cdv1 = ocupacao_se_cdv1
                else:
                    ocupacao_cdv9 = ocupacao_se_cdv9
            
            # Verificar se ajuste de concomitância ajuda
            if sim.get("tempo_meses", 0) > 3 and sim.get("concomitante", 0) < 2:
                sugestoes.append({
                    "tipo": TipoSugestao.AJUSTE_CONCOMITANCIA.value,
                    "fase_id": sim["id"],
                    "fase_nome": sim["nome"],
                    "original": {"concomitante": sim.get("concomitante", 0)},
                    "sugerido": {"concomitante": 2},
                    "motivo": "Aumentar concomitancia pode reduzir picos de ocupacao",
                    "impacto_m2": demanda * 0.2,  # Estimativa
                    "economia_ocupacao_pct": 5.0,
                    "prioridade": 3
                })
        
        tem_ultrapassagem = ocupacao_cdv1 > 100 or ocupacao_cdv9 > 100
        
        return {
            "nome": "otimizado",
            "descricao": "Redistribui carga para balancear ocupacao e evitar ultrapassar 85%",
            "ocupacao_cdv1_pct": round(ocupacao_cdv1, 1),
            "ocupacao_cdv9_pct": round(ocupacao_cdv9, 1),
            "ocupacao_media_pct": round((ocupacao_cdv1 + ocupacao_cdv9) / 2, 1),
            "balanceamento_pct": round(abs(ocupacao_cdv1 - ocupacao_cdv9), 1),
            "risco_gargalo": calcular_nivel_risco(max(ocupacao_cdv1, ocupacao_cdv9)),
            "sugestoes": sorted(sugestoes, key=lambda x: x["prioridade"]),
            "score": calcular_score_cenario(ocupacao_cdv1, ocupacao_cdv9, tem_ultrapassagem)
        }
    
    def _gerar_cenario_agressivo(self) -> Dict:
        """
        Cenário agressivo: maximiza uso, permite até 95% de ocupação.
        Sugere trocas de recipiente quando vantajoso.
        """
        sugestoes = []
        ocupacao_cdv1 = self.contexto["estufas"]["CDV1"]["ocupacao_pct"]
        ocupacao_cdv9 = self.contexto["estufas"]["CDV9"]["ocupacao_pct"]
        
        cap_cdv1 = self.contexto["estufas"]["CDV1"]["capacidade_total_m2"]
        cap_cdv9 = self.contexto["estufas"]["CDV9"]["capacidade_total_m2"]
        
        # Mapeamento de recipientes alternativos (menor área)
        recipientes_alternativos = {
            "Vaso": "Bandeja",       # 0.3 -> 0.16 m²
            "Bandeja": "Citropote",  # 0.16 -> 0.02 m²
        }
        
        for sim in self.contexto["simulacoes"]:
            estufa_original = sim["estufa"]
            recipiente = sim["recipiente"]
            demanda = sim["demanda_m2"]
            quantidade = sim["quantidade"]
            
            # Verificar se troca de recipiente é viável
            if recipiente in recipientes_alternativos:
                recip_alt = recipientes_alternativos[recipiente]
                demanda_alt = quantidade_para_m2(quantidade, recip_alt)
                economia_m2 = demanda - demanda_alt
                
                if economia_m2 > 10:  # Só sugerir se economia significativa
                    sugestoes.append({
                        "tipo": TipoSugestao.TROCA_RECIPIENTE.value,
                        "fase_id": sim["id"],
                        "fase_nome": sim["nome"],
                        "original": {
                            "recipiente": recipiente,
                            "demanda_m2": round(demanda, 2)
                        },
                        "sugerido": {
                            "recipiente": recip_alt,
                            "demanda_m2": round(demanda_alt, 2)
                        },
                        "motivo": f"Trocar {recipiente} por {recip_alt} economiza {economia_m2:.1f} m2",
                        "impacto_m2": economia_m2,
                        "economia_ocupacao_pct": round(economia_m2 / cap_cdv1 * 100, 1),
                        "prioridade": 2
                    })
                    demanda = demanda_alt  # Usar demanda reduzida
            
            # Alocar na estufa com mais espaço
            disp_cdv1 = cap_cdv1 * (1 - ocupacao_cdv1/100)
            disp_cdv9 = cap_cdv9 * (1 - ocupacao_cdv9/100)
            
            if disp_cdv1 > disp_cdv9 and estufa_original != "CDV1":
                sugestoes.append({
                    "tipo": TipoSugestao.TROCA_ESTUFA.value,
                    "fase_id": sim["id"],
                    "fase_nome": sim["nome"],
                    "original": {"estufa": estufa_original},
                    "sugerido": {"estufa": "CDV1"},
                    "motivo": f"CDV1 tem mais espaco disponivel ({disp_cdv1:.0f} m2 vs {disp_cdv9:.0f} m2)",
                    "impacto_m2": demanda,
                    "economia_ocupacao_pct": 0,
                    "prioridade": 2
                })
                ocupacao_cdv1 += demanda / cap_cdv1 * 100
            elif disp_cdv9 > disp_cdv1 and estufa_original != "CDV9":
                sugestoes.append({
                    "tipo": TipoSugestao.TROCA_ESTUFA.value,
                    "fase_id": sim["id"],
                    "fase_nome": sim["nome"],
                    "original": {"estufa": estufa_original},
                    "sugerido": {"estufa": "CDV9"},
                    "motivo": f"CDV9 tem mais espaco disponivel ({disp_cdv9:.0f} m2 vs {disp_cdv1:.0f} m2)",
                    "impacto_m2": demanda,
                    "economia_ocupacao_pct": 0,
                    "prioridade": 2
                })
                ocupacao_cdv9 += demanda / cap_cdv9 * 100
            else:
                if estufa_original == "CDV1":
                    ocupacao_cdv1 += demanda / cap_cdv1 * 100
                else:
                    ocupacao_cdv9 += demanda / cap_cdv9 * 100
            
            # Sugerir ajuste de data se ocupação muito alta
            if max(ocupacao_cdv1, ocupacao_cdv9) > 90:
                sugestoes.append({
                    "tipo": TipoSugestao.AJUSTE_DATA.value,
                    "fase_id": sim["id"],
                    "fase_nome": sim["nome"],
                    "original": {"data_inicio": sim.get("data_inicio", "")},
                    "sugerido": {"data_inicio": "Adiar 1-2 meses"},
                    "motivo": "Adiar inicio pode distribuir carga ao longo do tempo",
                    "impacto_m2": demanda,
                    "economia_ocupacao_pct": 10.0,
                    "prioridade": 3
                })
        
        tem_ultrapassagem = ocupacao_cdv1 > 100 or ocupacao_cdv9 > 100
        
        return {
            "nome": "agressivo",
            "descricao": "Maximiza uso das estufas, permite ate 95% de ocupacao, sugere trocas de recipiente",
            "ocupacao_cdv1_pct": round(ocupacao_cdv1, 1),
            "ocupacao_cdv9_pct": round(ocupacao_cdv9, 1),
            "ocupacao_media_pct": round((ocupacao_cdv1 + ocupacao_cdv9) / 2, 1),
            "balanceamento_pct": round(abs(ocupacao_cdv1 - ocupacao_cdv9), 1),
            "risco_gargalo": calcular_nivel_risco(max(ocupacao_cdv1, ocupacao_cdv9)),
            "sugestoes": sorted(sugestoes, key=lambda x: x["prioridade"]),
            "score": calcular_score_cenario(ocupacao_cdv1, ocupacao_cdv9, tem_ultrapassagem)
        }
    
    def _verificar_alertas(self):
        """Gera alertas baseados no contexto."""
        # Alerta de ocupação alta
        for estufa, dados in self.contexto["estufas"].items():
            if dados["ocupacao_pct"] >= LIMITE_ATENCAO:
                self.alertas.append(
                    f"ATENCAO: {estufa} ja esta com {dados['ocupacao_pct']:.1f}% de ocupacao"
                )
            if dados["ocupacao_pct"] >= LIMITE_CRITICO:
                self.alertas.append(
                    f"CRITICO: {estufa} ultrapassou 100% de capacidade!"
                )
        
        # Alerta de desbalanceamento
        ocup_cdv1 = self.contexto["estufas"]["CDV1"]["ocupacao_pct"]
        ocup_cdv9 = self.contexto["estufas"]["CDV9"]["ocupacao_pct"]
        desbalanceamento = abs(ocup_cdv1 - ocup_cdv9)
        
        if desbalanceamento > 20:
            estufa_maior = "CDV1" if ocup_cdv1 > ocup_cdv9 else "CDV9"
            self.alertas.append(
                f"DESBALANCEAMENTO: {estufa_maior} tem {desbalanceamento:.1f}% mais ocupacao"
            )
        
        # Alerta de simulação grande
        total_sim = self.contexto["totais"]["simulacao_pendente_m2"]
        total_disp = self.contexto["totais"]["disponivel_atual_m2"]
        
        if total_sim > total_disp * 0.5:
            self.alertas.append(
                f"ATENCAO: Simulacoes pendentes ({total_sim:.0f} m2) ocupam mais de 50% do espaco disponivel"
            )
    
    def _gerar_explicacao_tecnica(self, cenarios: Dict, melhor: str) -> str:
        """Gera explicação técnica da recomendação."""
        baseline = cenarios["baseline"]
        otimizado = cenarios["otimizado"]
        agressivo = cenarios["agressivo"]
        recomendado = cenarios[melhor]
        
        # Dados de capacidade por estufa/recipiente
        resumo_estufas = ""
        for estufa in ["CDV1", "CDV9"]:
            dados = self.contexto["estufas"].get(estufa, {})
            resumo_estufas += f"\n  {estufa}: {dados.get('ocupacao_pct', 0):.1f}% ocupado ({dados.get('disponivel_m2', 0):.0f} m2 livres)"
            for recip, rd in dados.get("recipientes", {}).items():
                disp = rd.get("disponivel_m2", 0)
                uso = rd.get("ocupacao_pct", 0)
                resumo_estufas += f"\n    - {recip}: {uso:.1f}% ocupado | {disp:.0f} m2 disponiveis"
        
        explicacao = f"""
ANALISE DE OTIMIZACAO DE CAPACIDADE
{'='*50}

SITUACAO ATUAL:{resumo_estufas}

CAPACIDADE TOTAL DO SISTEMA: {self.contexto['totais']['capacidade_sistema_m2']:.0f} m2
OCUPACAO GERAL: {self.contexto['totais']['ocupacao_atual_pct']:.1f}%
SIMULACOES PENDENTES: {self.contexto['totais']['num_simulacoes']} fases ({self.contexto['totais']['simulacao_pendente_m2']:.0f} m2)

COMPARACAO DE CENARIOS:

1) BASELINE (manter original):
   CDV1: {baseline['ocupacao_cdv1_pct']:.1f}% | CDV9: {baseline['ocupacao_cdv9_pct']:.1f}%
   Desbalanceamento: {baseline['balanceamento_pct']:.1f}% | Score: {baseline['score']:.2f}

2) OTIMIZADO (balancear carga):
   CDV1: {otimizado['ocupacao_cdv1_pct']:.1f}% | CDV9: {otimizado['ocupacao_cdv9_pct']:.1f}%
   Desbalanceamento: {otimizado['balanceamento_pct']:.1f}% | Score: {otimizado['score']:.2f}
   Sugestoes: {len(otimizado['sugestoes'])} alteracoes

3) AGRESSIVO (maximizar uso):
   CDV1: {agressivo['ocupacao_cdv1_pct']:.1f}% | CDV9: {agressivo['ocupacao_cdv9_pct']:.1f}%
   Desbalanceamento: {agressivo['balanceamento_pct']:.1f}% | Score: {agressivo['score']:.2f}
   Sugestoes: {len(agressivo['sugestoes'])} alteracoes

RECOMENDACAO: CENARIO {melhor.upper()}
Justificativa: Menor score ({recomendado['score']:.2f}) indica melhor equilibrio 
entre ocupacao, balanceamento e risco de gargalo.
"""
        
        if recomendado["sugestoes"]:
            explicacao += f"\nSUGESTOES PRIORITARIAS:\n"
            for i, sug in enumerate(recomendado["sugestoes"][:5], 1):
                explicacao += f"{i}. [{sug['tipo'].upper()}] {sug['motivo']}\n"
        
        return explicacao.strip()
    
    def _calcular_metricas(self, cenarios: Dict, melhor: str) -> Dict:
        """Calcula métricas de comparação."""
        baseline = cenarios["baseline"]
        recomendado = cenarios[melhor]
        
        return {
            "economia_ocupacao_media_pct": round(
                baseline["ocupacao_media_pct"] - recomendado["ocupacao_media_pct"], 1
            ),
            "reducao_desbalanceamento_pct": round(
                baseline["balanceamento_pct"] - recomendado["balanceamento_pct"], 1
            ),
            "melhoria_score_pct": round(
                (baseline["score"] - recomendado["score"]) / baseline["score"] * 100
                if baseline["score"] > 0 else 0, 1
            ),
            "num_sugestoes_total": sum(
                len(c["sugestoes"]) for c in cenarios.values()
            ),
            "risco_baseline": baseline["risco_gargalo"],
            "risco_recomendado": recomendado["risco_gargalo"]
        }


# ================================================================================
# INTEGRAÇÃO OPCIONAL COM LLM (OpenAI)
# ================================================================================

def gerar_explicacao_llm(recomendacao: Dict, api_key: str = None) -> str:
    """
    Gera explicação detalhada usando LLM (OpenAI GPT).
    
    Args:
        recomendacao: Dicionário com a recomendação do agente
        api_key: Chave da API OpenAI (ou usa variável de ambiente)
    
    Returns:
        Explicação em linguagem natural
    """
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    
    if not api_key:
        return recomendacao.get("explicacao_tecnica", "LLM nao configurado.")
    
    try:
        import openai
        openai.api_key = api_key
        
        prompt = f"""
Voce e um especialista em otimizacao de capacidade de estufas agricolas.
Analise a seguinte recomendacao do sistema e explique de forma clara e objetiva
para um gestor de operacoes:

CONTEXTO:
{json.dumps(recomendacao.get('contexto', {}), indent=2, ensure_ascii=False)}

CENARIO RECOMENDADO: {recomendacao.get('cenario_recomendado', 'N/A')}

SUGESTOES:
{json.dumps(recomendacao.get('sugestoes_prioritarias', []), indent=2, ensure_ascii=False)}

ALERTAS:
{json.dumps(recomendacao.get('alertas', []), indent=2, ensure_ascii=False)}

Forneça:
1. Resumo executivo (2-3 frases)
2. Principais acoes recomendadas
3. Riscos de NAO seguir as recomendacoes
4. Proximos passos sugeridos

Responda em portugues de forma objetiva e profissional.
"""
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Voce e um consultor de operacoes agricolas especializado em gestao de capacidade."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        
        return response.choices[0].message.content
    
    except ImportError:
        return "Biblioteca openai nao instalada. Use: pip install openai"
    except Exception as e:
        return f"Erro ao gerar explicacao com LLM: {str(e)}"


# ================================================================================
# FUNÇÃO PRINCIPAL DE ANÁLISE
# ================================================================================

def analisar_e_recomendar(
    capacidade_atual: List[Dict],
    simulacoes_pendentes: List[Dict],
    usar_llm: bool = False,
    api_key: str = None
) -> Dict[str, Any]:
    """
    Função principal que executa análise completa e retorna recomendações.
    
    Args:
        capacidade_atual: Lista de dicts com capacidade por estufa/recipiente
        simulacoes_pendentes: Lista de simulações pendentes
        usar_llm: Se True, usa LLM para explicação adicional
        api_key: Chave da API OpenAI (opcional)
    
    Returns:
        Dicionário com recomendações completas
    """
    # Gerar contexto
    contexto = gerar_contexto_simulacao(capacidade_atual, simulacoes_pendentes)
    
    # Criar agente e analisar
    agente = AgenteOtimizacao(contexto)
    recomendacao = agente.analisar()
    
    # Converter para dicionário
    resultado = {
        "timestamp": recomendacao.timestamp,
        "contexto": recomendacao.contexto,
        "cenarios": {
            "baseline": recomendacao.cenario_baseline,
            "otimizado": recomendacao.cenario_otimizado,
            "agressivo": recomendacao.cenario_agressivo
        },
        "cenario_recomendado": recomendacao.cenario_recomendado,
        "sugestoes_prioritarias": recomendacao.sugestoes_prioritarias,
        "explicacao_tecnica": recomendacao.explicacao_tecnica,
        "alertas": recomendacao.alertas,
        "metricas": recomendacao.metricas
    }
    
    # Adicionar explicação LLM se solicitado
    if usar_llm:
        resultado["explicacao_llm"] = gerar_explicacao_llm(resultado, api_key)
    
    return resultado


# ================================================================================
# EXEMPLO DE USO (para testes)
# ================================================================================

if __name__ == "__main__":
    # Dados de exemplo
    capacidade_exemplo = [
        {"Estufa": "CDV1", "Recipiente": "Bandeja", "Capacidade": 1598.4, "Consumido_total_m2": 800, "Disponivel": 798.4, "Uso_pct": 50.0},
        {"Estufa": "CDV1", "Recipiente": "Citropote", "Capacidade": 272.4, "Consumido_total_m2": 200, "Disponivel": 72.4, "Uso_pct": 73.4},
        {"Estufa": "CDV1", "Recipiente": "Vaso", "Capacidade": 1065.6, "Consumido_total_m2": 600, "Disponivel": 465.6, "Uso_pct": 56.3},
        {"Estufa": "CDV9", "Recipiente": "Bandeja", "Capacidade": 1048.0, "Consumido_total_m2": 400, "Disponivel": 648.0, "Uso_pct": 38.2},
        {"Estufa": "CDV9", "Recipiente": "Citropote", "Capacidade": 770.4, "Consumido_total_m2": 300, "Disponivel": 470.4, "Uso_pct": 38.9},
        {"Estufa": "CDV9", "Recipiente": "Vaso", "Capacidade": 556.8, "Consumido_total_m2": 200, "Disponivel": 356.8, "Uso_pct": 35.9},
    ]
    
    simulacoes_exemplo = [
        {"id": 1, "nome": "Projeto Teste - Fase 1", "estufa": "CDV1", "recipiente": "Bandeja", "quantidade": 1000, "demanda_m2": 160, "tempo_meses": 6, "data_inicio": "2026-03-01", "concomitante": 0},
        {"id": 2, "nome": "Projeto Teste - Fase 2", "estufa": "CDV1", "recipiente": "Citropote", "quantidade": 5000, "demanda_m2": 100, "tempo_meses": 4, "data_inicio": "2026-06-01", "concomitante": 2},
        {"id": 3, "nome": "Projeto Teste - Fase 3", "estufa": "CDV1", "recipiente": "Vaso", "quantidade": 500, "demanda_m2": 150, "tempo_meses": 8, "data_inicio": "2026-08-01", "concomitante": 0},
    ]
    
    # Executar análise
    resultado = analisar_e_recomendar(capacidade_exemplo, simulacoes_exemplo)
    
    # Exibir resultado
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
