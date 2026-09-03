"""Taxonomia dos tipos de ativo governados.

Cada tipo declara o rótulo, o bloco a que pertence, o pai hierárquico
obrigatório e os campos específicos usados pelo wizard dinâmico. Os campos
específicos são gravados em ITEM_CATALOGO.atributos (JSON), preservando a
semântica das entidades da proposta sem espalhar a mecânica de governança
por dezenas de tabelas.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Campo:
    nome: str
    rotulo: str
    tipo: str = "texto"          # texto|area|selecao|url
    obrigatorio: bool = False
    opcoes: tuple = ()


@dataclass(frozen=True)
class TipoAtivo:
    chave: str
    rotulo: str
    bloco: str
    pai: str | None = None            # tipo do item pai exigido
    prefixo: str = "ATV"
    campos: tuple = field(default_factory=tuple)
    exige_owner_negocial: bool = False
    exige_owner_tecnico: bool = False


TIPOS: dict[str, TipoAtivo] = {
    "dominio": TipoAtivo(
        "dominio", "Domínio", "Estrutura DDD", None, "DOM",
        (Campo("visao", "Visão de negócio", "area", True),
         Campo("fórum", "Fórum de governança")),
        exige_owner_negocial=True,
    ),
    "subdominio": TipoAtivo(
        "subdominio", "Subdomínio", "Estrutura DDD", "dominio", "SUB",
        (Campo("classificacao", "Classificação", "selecao", True,
               ("core", "suporte", "genérico")),),
        exige_owner_negocial=True,
    ),
    "contexto": TipoAtivo(
        "contexto", "Bounded Context", "Estrutura DDD", "subdominio", "CTX",
        (Campo("linguagem_ubiqua", "Termos da linguagem ubíqua", "area"),
         Campo("estrategia_integracao", "Estratégia de integração", "selecao", False,
               ("parceria", "cliente-fornecedor", "conformista",
                "camada anticorrupção", "serviço aberto")),),
        exige_owner_negocial=True, exige_owner_tecnico=True,
    ),
    "capacidade": TipoAtivo(
        "capacidade", "Capacidade de negócio", "Estrutura DDD", "contexto", "CAP",
        (Campo("resultado_esperado", "Resultado esperado", "area", True),
         Campo("processo_negocio", "Processo de negócio"),),
        exige_owner_negocial=True, exige_owner_tecnico=True,
    ),
    "sistema": TipoAtivo(
        "sistema", "Sistema", "Ativos técnicos", None, "SIS",
        (Campo("plataforma", "Plataforma", "selecao", True,
               ("mainframe", "distribuído", "nuvem", "híbrido")),
         Campo("situacao", "Situação", "selecao", False,
               ("legado", "em modernização", "estratégico")),),
        exige_owner_tecnico=True,
    ),
    "aplicacao": TipoAtivo(
        "aplicacao", "Aplicação", "Ativos técnicos", "sistema", "APP",
        (Campo("tecnologia", "Tecnologia principal", "texto", True),
         Campo("ambiente", "Ambientes implantados"),),
        exige_owner_tecnico=True,
    ),
    "repositorio": TipoAtivo(
        "repositorio", "Repositório", "Ativos técnicos", "aplicacao", "REP",
        (Campo("url", "URL do repositório", "url", True),
         Campo("branch_principal", "Branch principal"),
         Campo("linguagem", "Linguagem"),
         Campo("ultima_atividade", "Última atividade (AAAA-MM-DD)")),
        exige_owner_tecnico=True,
    ),
    "api": TipoAtivo(
        "api", "API", "Ativos técnicos", "aplicacao", "API",
        (Campo("versao", "Versão", "texto", True),
         Campo("estilo", "Estilo", "selecao", True, ("REST", "SOAP", "gRPC", "evento")),
         Campo("url_contrato", "Contrato OpenAPI", "url")),
        exige_owner_tecnico=True,
    ),
    "endpoint": TipoAtivo(
        "endpoint", "Endpoint", "Ativos técnicos", "api", "END",
        (Campo("metodo", "Método", "selecao", True,
               ("GET", "POST", "PUT", "PATCH", "DELETE")),
         Campo("rota", "Rota", "texto", True)),
    ),
    "base_dados": TipoAtivo(
        "base_dados", "Base de dados", "Ativos técnicos", "sistema", "BDD",
        (Campo("sgbd", "SGBD", "texto", True),
         Campo("classificacao_dado", "Classificação", "selecao", False,
               ("público", "interno", "restrito", "sigiloso")),),
        exige_owner_tecnico=True,
    ),
    "objeto_dado": TipoAtivo(
        "objeto_dado", "Objeto de dado", "Ativos técnicos", "base_dados", "OBJ",
        (Campo("sistema_registro", "É sistema de registro?", "selecao", True, ("sim", "não")),
         Campo("granularidade", "Granularidade")),
    ),
    "evento": TipoAtivo(
        "evento", "Evento de integração", "Ativos técnicos", "contexto", "EVT",
        (Campo("topico", "Tópico/fila", "texto", True),
         Campo("formato", "Formato do payload")),
        exige_owner_tecnico=True,
    ),
}

# Relações permitidas no grafo tipado.
RELACOES = {
    "implementa": "implementa a capacidade",
    "expoe": "expõe",
    "consome": "consome",
    "produz": "produz",
    "depende_de": "depende de",
    "persiste_em": "persiste em",
}

CICLO_VIDA = {
    "rascunho": "Rascunho",
    "em_validacao": "Em validação",
    "publicado": "Publicado",
    "em_revisao": "Em revisão",
    "descontinuado": "Descontinuado",
    "arquivado": "Arquivado",
}

CONSUMIVEL = {"publicado", "em_revisao"}
CRITICIDADES = ("baixa", "media", "alta", "critica")


def tipo(chave: str) -> TipoAtivo:
    if chave not in TIPOS:
        raise KeyError(f"tipo de ativo desconhecido: {chave}")
    return TIPOS[chave]


def blocos() -> dict[str, list[TipoAtivo]]:
    agrupado: dict[str, list[TipoAtivo]] = {}
    for t in TIPOS.values():
        agrupado.setdefault(t.bloco, []).append(t)
    return agrupado
