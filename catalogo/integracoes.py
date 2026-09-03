"""Descoberta automática de ativos técnicos (seção 8 da proposta).

A coleta cria ou atualiza itens em rascunho com origem 'automatica' e deixa a
semântica (domínio, capacidade, criticidade) para validação humana.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import servicos


def _achar_por_nome(con, tipo_item: str, nome: str):
    return con.execute(
        "SELECT id_item FROM item_catalogo WHERE tipo_item = ? AND lower(nome) = lower(?)",
        (tipo_item, nome)).fetchone()


def importar_openapi(con, caminho: str | Path, id_aplicacao: int,
                     usuario: str = "integracao") -> dict:
    """Cria a API e seus endpoints a partir de um contrato OpenAPI (JSON)."""
    spec = json.loads(Path(caminho).read_text(encoding="utf-8"))
    info = spec.get("info", {})
    nome = info.get("title") or Path(caminho).stem
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
                       "url_contrato": str(caminho)}, usuario=usuario)
        servicos.anexar_evidencia(con, id_api, "openapi",
                                  f"Contrato OpenAPI {versao}", str(caminho),
                                  origem="openapi", usuario=usuario)

    criados = 0
    for rota, operacoes in (spec.get("paths") or {}).items():
        for metodo, corpo in operacoes.items():
            if metodo.upper() not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                continue
            nome_ep = f"{metodo.upper()} {rota}"
            if _achar_por_nome(con, "endpoint", nome_ep):
                continue
            servicos.criar_item(
                con, tipo_item="endpoint", nome=nome_ep,
                descricao=(corpo or {}).get("summary", "Descoberto via OpenAPI"),
                id_pai=id_api,
                atributos={"metodo": metodo.upper(), "rota": rota}, usuario=usuario)
            criados += 1
    servicos.auditar(con, id_api, "sincronizar_openapi", usuario,
                     depois={"endpoints": criados}, origem="openapi")
    con.commit()
    return {"id_api": id_api, "endpoints_criados": criados}


def importar_repositorios(con, caminho: str | Path, id_aplicacao: int,
                          usuario: str = "integracao") -> dict:
    """Importa um inventário Git em JSON: [{nome, url, branch, linguagem, ...}]."""
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
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
                id_pai=id_aplicacao, atributos=atributos, usuario=usuario)
            servicos.anexar_evidencia(con, id_repo, "repositorio", "URL do repositório",
                                      atributos["url"], origem="git", usuario=usuario)
            criados += 1
    con.commit()
    return {"criados": criados, "atualizados": atualizados}
