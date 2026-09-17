"""Score de qualidade cadastral e pendências acionáveis.

Cinco dimensões, cada uma de 0 a 100, combinadas por peso:
completude, consistência, ownership, evidência e temporalidade.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from . import tipos

PESOS = {
    "completude": 0.30,
    "consistencia": 0.20,
    "ownership": 0.20,
    "evidencia": 0.15,
    "temporalidade": 0.15,
}


def _papeis(con, id_item: int) -> set[str]:
    linhas = con.execute(
        "SELECT papel FROM responsabilidade "
        "WHERE id_item = ? AND (fim_vigencia IS NULL OR fim_vigencia >= date('now'))",
        (id_item,),
    ).fetchall()
    return {l["papel"] for l in linhas}


def avaliar(con, id_item: int) -> dict:
    item = con.execute(
        "SELECT * FROM item_catalogo WHERE id_item = ?", (id_item,)
    ).fetchone()
    if item is None:
        raise LookupError(f"item {id_item} não encontrado")

    t = tipos.tipo(item["tipo_item"])
    atributos = json.loads(item["atributos"] or "{}")
    pendencias: list[str] = []

    # ---------------------------------------------------------- completude
    exigidos = ["descricao"] + [c.nome for c in t.campos if c.obrigatorio]
    preenchidos = 0
    for campo in exigidos:
        valor = item["descricao"] if campo == "descricao" else atributos.get(campo)
        if valor and str(valor).strip():
            preenchidos += 1
        else:
            rotulo = "Descrição" if campo == "descricao" else campo
            pendencias.append(f"Preencher {rotulo}")
    completude = round(100 * preenchidos / len(exigidos)) if exigidos else 100

    # -------------------------------------------------------- consistência
    consistencia = 100
    if t.pai:
        pai = None
        if item["id_pai"]:
            pai = con.execute(
                "SELECT tipo_item, status_ciclo_vida FROM item_catalogo WHERE id_item = ?",
                (item["id_pai"],),
            ).fetchone()
        if pai is None:
            consistencia -= 50
            pendencias.append(f"Vincular a um item do tipo {tipos.tipo(t.pai).rotulo}")
        elif pai["status_ciclo_vida"] in ("descontinuado", "arquivado"):
            consistencia -= 30
            pendencias.append("Item pai está fora de vigência")

    orfas = con.execute(
        "SELECT COUNT(*) c FROM relacionamento_ativo r "
        "JOIN item_catalogo d ON d.id_item = r.id_destino "
        "WHERE r.id_origem = ? AND r.fim_vigencia IS NULL "
        "AND d.status_ciclo_vida IN ('descontinuado','arquivado')",
        (id_item,),
    ).fetchone()["c"]
    if orfas:
        consistencia -= min(40, 10 * orfas)
        pendencias.append(f"{orfas} relação(ões) apontam para ativo descontinuado")

    if item["tipo_item"] == "capacidade":
        impl = con.execute(
            "SELECT COUNT(*) c FROM relacionamento_ativo "
            "WHERE id_destino = ? AND tipo_relacao = 'implementa' AND fim_vigencia IS NULL",
            (id_item,),
        ).fetchone()["c"]
        if not impl:
            consistencia -= 20
            pendencias.append("Capacidade sem implementação identificada")
    consistencia = max(0, consistencia)

    # ----------------------------------------------------------- ownership
    papeis = _papeis(con, id_item)
    exigidos_papel = []
    if t.exige_owner_negocial:
        exigidos_papel.append("owner_negocial")
    if t.exige_owner_tecnico:
        exigidos_papel.append("owner_tecnico")
    if exigidos_papel:
        ok = [p for p in exigidos_papel if p in papeis]
        ownership = round(100 * len(ok) / len(exigidos_papel))
        for p in exigidos_papel:
            if p not in papeis:
                pendencias.append(f"Definir {p.replace('_', ' ')}")
    else:
        ownership = 100 if papeis else 70

    # ------------------------------------------------------------ evidência
    minima = con.execute(
        "SELECT evidencia_minima FROM politica_governanca "
        "WHERE tipo_item = ? AND criticidade IN (?, '*') "
        "ORDER BY criticidade DESC LIMIT 1",
        (item["tipo_item"], item["criticidade"]),
    ).fetchone()
    minima = minima["evidencia_minima"] if minima else 0
    total_ev = con.execute(
        "SELECT COUNT(*) c FROM evidencia WHERE id_item = ?", (id_item,)
    ).fetchone()["c"]
    if minima == 0:
        evidencia = 100 if total_ev else 80
    else:
        evidencia = min(100, round(100 * total_ev / minima))
        if total_ev < minima:
            pendencias.append(f"Anexar evidência mínima ({total_ev}/{minima})")

    # -------------------------------------------------------- temporalidade
    politica_dias = con.execute(
        "SELECT periodicidade_revisao_dias FROM politica_governanca "
        "WHERE tipo_item = ? AND criticidade IN (?, '*') "
        "ORDER BY criticidade DESC LIMIT 1",
        (item["tipo_item"], item["criticidade"]),
    ).fetchone()
    dias = politica_dias["periodicidade_revisao_dias"] if politica_dias else 180
    referencia = item["atualizado_em"] or item["criado_em"]
    try:
        base = datetime.fromisoformat(referencia).date()
    except (TypeError, ValueError):
        base = date.today()
    idade = (date.today() - base).days
    if idade <= dias:
        temporalidade = 100
    elif idade <= dias * 2:
        temporalidade = 60
        pendencias.append(f"Revisar cadastro: {idade} dias sem atualização")
    else:
        temporalidade = 20
        pendencias.append(f"Cadastro desatualizado há {idade} dias")
    if item["fim_vigencia"]:
        fim = item["fim_vigencia"]
        if fim < date.today().isoformat() and item["status_ciclo_vida"] == "publicado":
            temporalidade = min(temporalidade, 40)
            pendencias.append("Vigência encerrada mas item continua publicado")

    dimensoes = {
        "completude": completude,
        "consistencia": consistencia,
        "ownership": ownership,
        "evidencia": evidencia,
        "temporalidade": temporalidade,
    }
    score = round(sum(v * PESOS[k] for k, v in dimensoes.items()))
    return {**dimensoes, "score_total": score, "pendencias": pendencias}


def registrar(con, id_item: int) -> dict:
    """Calcula e materializa o score em QUALIDADE_CATALOGO."""
    r = avaliar(con, id_item)
    con.execute(
        "INSERT INTO qualidade_catalogo "
        "(id_item, completude, consistencia, ownership, evidencia, temporalidade,"
        " score_total, pendencias) VALUES (?,?,?,?,?,?,?,?)",
        (id_item, r["completude"], r["consistencia"], r["ownership"],
         r["evidencia"], r["temporalidade"], r["score_total"],
         json.dumps(r["pendencias"], ensure_ascii=False)),
    )
    return r


def media_geral(con) -> int:
    linha = con.execute(
        "SELECT AVG(score) s FROM vw_item_qualidade WHERE score IS NOT NULL"
    ).fetchone()
    return round(linha["s"] or 0)


def proxima_revisao(con, id_item: int) -> str | None:
    item = con.execute(
        "SELECT tipo_item, criticidade, atualizado_em FROM item_catalogo WHERE id_item = ?",
        (id_item,),
    ).fetchone()
    if item is None:
        return None
    # mesmo padrão de filtro usado em avaliar(): a política específica da
    # criticidade do item vence a política '*' (curinga), nunca o contrário
    pol = con.execute(
        "SELECT periodicidade_revisao_dias d FROM politica_governanca "
        "WHERE tipo_item = ? AND criticidade IN (?, '*') "
        "ORDER BY criticidade DESC LIMIT 1",
        (item["tipo_item"], item["criticidade"]),
    ).fetchone()
    if not pol:
        return None
    try:
        base = datetime.fromisoformat(item["atualizado_em"]).date()
    except (TypeError, ValueError):
        return None
    return (base + timedelta(days=pol["d"])).isoformat()
