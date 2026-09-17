"""Políticas, pré-check automático, ciclo de vida e fila de validação."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from . import qualidade, tipos

TRANSICOES = {
    "rascunho": {"em_validacao", "arquivado"},
    "em_validacao": {"rascunho", "publicado"},
    "publicado": {"em_revisao", "descontinuado"},
    "em_revisao": {"publicado", "descontinuado"},
    "descontinuado": {"arquivado"},
    "arquivado": set(),
}

# Matriz mínima de aprovação (seção 4.1 da proposta).
MATRIZ_MUDANCA = {
    "texto": {"negocial": "opcional", "tecnica": "opcional", "arquitetural": "nao"},
    "escopo": {"negocial": "obrigatoria", "tecnica": "obrigatoria", "arquitetural": "condicional"},
    "contrato": {"negocial": "condicional", "tecnica": "obrigatoria", "arquitetural": "obrigatoria"},
    "dependencia": {"negocial": "condicional", "tecnica": "obrigatoria", "arquitetural": "obrigatoria"},
    "descontinuacao": {"negocial": "obrigatoria", "tecnica": "obrigatoria", "arquitetural": "condicional"},
}

POLITICAS_PADRAO = [
    # tipo, criticidade, etapas, evidência mínima, score mínimo, SLA h, revisão dias
    ("dominio", "*", ["negocial", "arquitetural"], 1, 70, 72, 365),
    ("subdominio", "*", ["negocial"], 0, 65, 72, 365),
    ("contexto", "*", ["negocial", "tecnica", "arquitetural"], 1, 75, 48, 180),
    ("capacidade", "*", ["negocial", "tecnica"], 1, 70, 48, 180),
    ("capacidade", "critica", ["negocial", "tecnica", "arquitetural"], 2, 80, 24, 90),
    ("sistema", "*", ["tecnica"], 0, 60, 72, 365),
    ("aplicacao", "*", ["tecnica"], 1, 65, 48, 180),
    ("repositorio", "*", ["tecnica"], 1, 60, 72, 180),
    ("api", "*", ["tecnica", "arquitetural"], 1, 70, 48, 120),
    ("api", "critica", ["negocial", "tecnica", "arquitetural"], 2, 80, 24, 90),
    ("endpoint", "*", ["tecnica"], 0, 55, 72, 180),
    ("base_dados", "*", ["tecnica"], 0, 60, 72, 365),
    ("objeto_dado", "*", ["tecnica"], 0, 55, 72, 365),
    ("evento", "*", ["tecnica", "arquitetural"], 1, 70, 48, 120),
]


def semear_politicas(con) -> None:
    for tipo_item, crit, etapas, ev, score, sla, revisao in POLITICAS_PADRAO:
        con.execute(
            "INSERT OR IGNORE INTO politica_governanca "
            "(tipo_item, criticidade, etapas, evidencia_minima, score_minimo,"
            " sla_horas, periodicidade_revisao_dias) VALUES (?,?,?,?,?,?,?)",
            (tipo_item, crit, json.dumps(etapas), ev, score, sla, revisao),
        )
    con.commit()


def politica(con, tipo_item: str, criticidade: str) -> dict:
    linha = con.execute(
        "SELECT * FROM politica_governanca WHERE tipo_item = ? AND criticidade = ?",
        (tipo_item, criticidade),
    ).fetchone()
    if linha is None:
        linha = con.execute(
            "SELECT * FROM politica_governanca WHERE tipo_item = ? AND criticidade = '*'",
            (tipo_item,),
        ).fetchone()
    if linha is None:
        return {"etapas": ["tecnica"], "evidencia_minima": 0,
                "score_minimo": 60, "sla_horas": 48,
                "periodicidade_revisao_dias": 180}
    d = dict(linha)
    d["etapas"] = json.loads(d["etapas"])
    return d


def pre_check(con, id_item: int) -> dict:
    """Roda o pré-check da seção 4.2 e devolve bloqueios e alertas."""
    item = con.execute(
        "SELECT * FROM item_catalogo WHERE id_item = ?", (id_item,)
    ).fetchone()
    if item is None:
        raise LookupError("item não encontrado")

    pol = politica(con, item["tipo_item"], item["criticidade"])
    q = qualidade.avaliar(con, id_item)
    t = tipos.tipo(item["tipo_item"])
    bloqueios: list[str] = []
    alertas: list[str] = []

    # campos obrigatórios e hierarquia
    atributos = json.loads(item["atributos"] or "{}")
    for campo in t.campos:
        if campo.obrigatorio and not str(atributos.get(campo.nome, "")).strip():
            bloqueios.append(f"Campo obrigatório vazio: {campo.rotulo}")
    if not (item["descricao"] or "").strip():
        bloqueios.append("Descrição é obrigatória para publicar")
    if t.pai and not item["id_pai"]:
        bloqueios.append(f"Hierarquia incompleta: informe o {tipos.tipo(t.pai).rotulo}")

    # ownership (reaproveita a mesma query de "papéis ativos" de qualidade.py
    # para não dessincronizar a regra do pré-check da pontuação de qualidade)
    papeis = qualidade._papeis(con, id_item)
    if t.exige_owner_negocial and "owner_negocial" not in papeis:
        bloqueios.append("Owner negocial não definido")
    if t.exige_owner_tecnico and "owner_tecnico" not in papeis:
        bloqueios.append("Owner técnico não definido")

    # duplicidade
    dup = con.execute(
        "SELECT COUNT(*) c FROM item_catalogo "
        "WHERE tipo_item = ? AND lower(nome) = lower(?) AND id_item <> ?",
        (item["tipo_item"], item["nome"], id_item),
    ).fetchone()["c"]
    if dup:
        bloqueios.append("Já existe ativo do mesmo tipo com esse nome")

    # ciclo em depende_de
    if _tem_ciclo(con, id_item):
        bloqueios.append("Relação circular de dependência detectada")

    # evidências mínimas
    total_ev = con.execute(
        "SELECT COUNT(*) c FROM evidencia WHERE id_item = ?", (id_item,)
    ).fetchone()["c"]
    if total_ev < pol["evidencia_minima"]:
        bloqueios.append(
            f"Evidência mínima não atendida ({total_ev}/{pol['evidencia_minima']})")

    # relações para itens fora de vigência
    fora = con.execute(
        "SELECT d.nome FROM relacionamento_ativo r "
        "JOIN item_catalogo d ON d.id_item = r.id_destino "
        "WHERE r.id_origem = ? AND r.fim_vigencia IS NULL "
        "AND d.status_ciclo_vida IN ('descontinuado','arquivado')",
        (id_item,),
    ).fetchall()
    for linha in fora:
        alertas.append(f"Relação com ativo fora de vigência: {linha['nome']}")

    # score mínimo
    if q["score_total"] < pol["score_minimo"]:
        bloqueios.append(
            f"Score de qualidade abaixo do mínimo ({q['score_total']}% < {pol['score_minimo']}%)")

    return {
        "aprovado": not bloqueios,
        "bloqueios": bloqueios,
        "alertas": alertas + [p for p in q["pendencias"]],
        "score": q["score_total"],
        "politica": pol,
    }


def _tem_ciclo(con, id_item: int) -> bool:
    visitados: set[int] = set()
    pilha = [id_item]
    while pilha:
        atual = pilha.pop()
        for linha in con.execute(
            "SELECT id_destino FROM relacionamento_ativo "
            "WHERE id_origem = ? AND tipo_relacao = 'depende_de' AND fim_vigencia IS NULL",
            (atual,),
        ):
            destino = linha["id_destino"]
            if destino == id_item:
                return True
            if destino not in visitados:
                visitados.add(destino)
                pilha.append(destino)
    return False


def impacto_descontinuacao(con, id_item: int) -> list[dict]:
    """Consumidores ativos que seriam afetados pela descontinuação."""
    linhas = con.execute(
        "SELECT o.id_item, o.codigo, o.nome, o.tipo_item, r.tipo_relacao, r.criticidade "
        "FROM relacionamento_ativo r "
        "JOIN item_catalogo o ON o.id_item = r.id_origem "
        "WHERE r.id_destino = ? AND r.fim_vigencia IS NULL "
        "AND o.status_ciclo_vida IN ('publicado','em_revisao')",
        (id_item,),
    ).fetchall()
    return [dict(l) for l in linhas]


def abrir_validacoes(con, id_item: int, id_revisao: int, usuario: str) -> list[int]:
    item = con.execute(
        "SELECT tipo_item, criticidade FROM item_catalogo WHERE id_item = ?", (id_item,)
    ).fetchone()
    pol = politica(con, item["tipo_item"], item["criticidade"])
    prazo = (datetime.now() + timedelta(hours=pol["sla_horas"])).isoformat(" ", "seconds")
    ids = []
    for etapa in pol["etapas"]:
        cur = con.execute(
            "INSERT INTO validacao (id_item, id_revisao, etapa, prazo, responsavel) "
            "VALUES (?,?,?,?,?)",
            (id_item, id_revisao, etapa, prazo, None),
        )
        ids.append(cur.lastrowid)
    return ids


def fila_validacao(con, etapa: str | None = None) -> list[dict]:
    sql = (
        "SELECT v.*, i.codigo, i.nome, i.tipo_item, i.criticidade, s.nome AS squad "
        "FROM validacao v JOIN item_catalogo i ON i.id_item = v.id_item "
        "LEFT JOIN squad s ON s.id_squad = i.id_squad "
        "WHERE v.situacao = 'pendente'"
    )
    params: tuple = ()
    if etapa:
        sql += " AND v.etapa = ?"
        params = (etapa,)
    ordem = ("ORDER BY CASE i.criticidade WHEN 'critica' THEN 0 WHEN 'alta' THEN 1 "
             "WHEN 'media' THEN 2 ELSE 3 END, v.prazo")
    return [dict(l) for l in con.execute(f"{sql} {ordem}", params)]


def sla_restante(prazo: str | None) -> str:
    if not prazo:
        return "—"
    try:
        alvo = datetime.fromisoformat(prazo)
    except ValueError:
        return "—"
    delta = alvo - datetime.now()
    if delta.total_seconds() < 0:
        return "vencido"
    horas = int(delta.total_seconds() // 3600)
    return f"{horas}h" if horas < 48 else f"{horas // 24}d"
