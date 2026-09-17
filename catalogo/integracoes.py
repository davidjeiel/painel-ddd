"""Descoberta automática de ativos técnicos (seção 8 da proposta).

A coleta cria ou atualiza itens em rascunho com origem 'automatica' e deixa a
semântica (domínio, capacidade, criticidade) para validação humana.

Cada importador tem um par: ``plano_*`` diz o que aconteceria, sem escrever
nada, e ``importar_*`` executa. É o que permite a tela de descobertas mostrar a
prévia antes de a pessoa confirmar.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import servicos

METODOS = ("GET", "POST", "PUT", "PATCH", "DELETE")


def _conteudo(caminho: str | Path | None, conteudo=None):
    """Aceita caminho de arquivo ou o JSON já carregado/como texto."""
    if conteudo is not None:
        return json.loads(conteudo) if isinstance(conteudo, str) else conteudo
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def _achar_por_nome(con, tipo_item: str, nome: str):
    return con.execute(
        "SELECT id_item FROM item_catalogo WHERE tipo_item = ? AND lower(nome) = lower(?)",
        (tipo_item, nome)).fetchone()


def _endpoints(spec: dict):
    for rota, operacoes in (spec.get("paths") or {}).items():
        for metodo, corpo in (operacoes or {}).items():
            if metodo.upper() in METODOS:
                yield metodo.upper(), rota, (corpo or {}).get("summary", "")


# ------------------------------------------------------------------- OpenAPI
def plano_openapi(con, caminho=None, id_aplicacao: int | None = None,
                  conteudo=None) -> dict:
    """O que a importação faria, sem tocar no banco."""
    spec = _conteudo(caminho, conteudo)
    info = spec.get("info", {})
    nome = info.get("title") or (Path(caminho).stem if caminho else "API sem título")
    versao = str(info.get("version", "1.0"))
    existente = _achar_por_nome(con, "api", nome)

    acoes = [{"acao": "manter" if existente else "criar", "tipo": "API",
              "nome": nome, "detalhe": f"versão {versao}"}]
    for metodo, rota, resumo in _endpoints(spec):
        nome_ep = f"{metodo} {rota}"
        acoes.append({
            "acao": "manter" if _achar_por_nome(con, "endpoint", nome_ep) else "criar",
            "tipo": "Endpoint", "nome": nome_ep, "detalhe": resumo or "—"})
    return {"titulo": nome, "versao": versao, "acoes": acoes,
            "criar": sum(1 for a in acoes if a["acao"] == "criar"),
            "manter": sum(1 for a in acoes if a["acao"] == "manter"),
            "id_aplicacao": id_aplicacao}


def importar_openapi(con, caminho=None, id_aplicacao: int | None = None,
                     usuario: str = "integracao", conteudo=None) -> dict:
    """Cria a API e seus endpoints a partir de um contrato OpenAPI (JSON)."""
    spec = _conteudo(caminho, conteudo)
    info = spec.get("info", {})
    nome = info.get("title") or (Path(caminho).stem if caminho else "API sem título")
    versao = str(info.get("version", "1.0"))

    existente = _achar_por_nome(con, "api", nome)
    if existente:
        id_api = existente["id_item"]
    else:
        id_api = servicos.criar_item(
            con, tipo_item="api", nome=nome,
            descricao=info.get("description", "Descoberta via OpenAPI"),
            id_pai=id_aplicacao, criticidade="media",
            atributos={"versao": versao, "estilo": "REST",
                       "url_contrato": str(caminho or "")},
            usuario=usuario, origem="automatica")
        servicos.anexar_evidencia(con, id_api, "openapi",
                                  f"Contrato OpenAPI {versao}", str(caminho or ""),
                                  origem="openapi", usuario=usuario)

    criados = 0
    for metodo, rota, resumo in _endpoints(spec):
        nome_ep = f"{metodo} {rota}"
        if _achar_por_nome(con, "endpoint", nome_ep):
            continue
        servicos.criar_item(
            con, tipo_item="endpoint", nome=nome_ep,
            descricao=resumo or "Descoberto via OpenAPI", id_pai=id_api,
            atributos={"metodo": metodo, "rota": rota},
            usuario=usuario, origem="automatica")
        criados += 1
    servicos.auditar(con, id_api, "sincronizar_openapi", usuario,
                     depois={"endpoints": criados}, origem="openapi")
    con.commit()
    return {"id_api": id_api, "endpoints_criados": criados}


# ----------------------------------------------------------------- Git / repos
def plano_repositorios(con, caminho=None, id_aplicacao: int | None = None,
                       conteudo=None) -> dict:
    dados = _conteudo(caminho, conteudo)
    acoes = []
    for repo in dados:
        existente = _achar_por_nome(con, "repositorio", repo["nome"])
        acoes.append({"acao": "atualizar" if existente else "criar",
                      "tipo": "Repositório", "nome": repo["nome"],
                      "detalhe": repo.get("linguagem") or repo.get("url") or "—"})
    return {"titulo": f"{len(acoes)} repositório(s)", "versao": "",
            "acoes": acoes,
            "criar": sum(1 for a in acoes if a["acao"] == "criar"),
            "manter": sum(1 for a in acoes if a["acao"] == "atualizar"),
            "id_aplicacao": id_aplicacao}


def importar_repositorios(con, caminho=None, id_aplicacao: int | None = None,
                          usuario: str = "integracao", conteudo=None) -> dict:
    """Importa um inventário Git em JSON: [{nome, url, branch, linguagem, ...}]."""
    dados = _conteudo(caminho, conteudo)
    criados, atualizados = 0, 0
    for repo in dados:
        atributos = {
            "url": repo.get("url", ""),
            "branch_principal": repo.get("branch", "main"),
            "linguagem": repo.get("linguagem", ""),
            "ultima_atividade": repo.get("ultima_atividade", ""),
        }
        existente = _achar_por_nome(con, "repositorio", repo["nome"])
        if existente:
            servicos.atualizar_item(con, existente["id_item"],
                                    {"atributos": atributos}, usuario=usuario)
            atualizados += 1
        else:
            id_repo = servicos.criar_item(
                con, tipo_item="repositorio", nome=repo["nome"],
                descricao=repo.get("descricao", "Descoberto no provedor Git"),
                id_pai=id_aplicacao, atributos=atributos,
                usuario=usuario, origem="automatica")
            servicos.anexar_evidencia(con, id_repo, "repositorio", "URL do repositório",
                                      atributos["url"], origem="git", usuario=usuario)
            criados += 1
    con.commit()
    return {"criados": criados, "atualizados": atualizados}


FONTES = {
    "openapi": {"rotulo": "Contrato OpenAPI", "plano": plano_openapi,
                "importar": importar_openapi,
                "ajuda": "JSON do contrato. Cria a API e um endpoint por operação.",
                "pai": "aplicacao"},
    "git": {"rotulo": "Inventário Git", "plano": plano_repositorios,
            "importar": importar_repositorios,
            "ajuda": 'Lista JSON: [{"nome": "...", "url": "...", "linguagem": "..."}]',
            "pai": "aplicacao"},
}
