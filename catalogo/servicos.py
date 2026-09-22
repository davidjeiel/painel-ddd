"""Casos de uso do catálogo: cadastro, revisão, validação e publicação."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime

from .db import ErroIntegridade
from . import governanca, qualidade, tipos


class RegraDeNegocio(Exception):
    """Violação de regra de governança."""


# --------------------------------------------------------------- auditoria
def auditar(con, id_item: int | None, acao: str, usuario: str,
            antes=None, depois=None, origem: str = "ui") -> None:
    con.execute(
        "INSERT INTO auditoria_evento (id_item, acao, usuario, origem, antes, depois) "
        "VALUES (?,?,?,?,?,?)",
        (id_item, acao, usuario, origem,
         json.dumps(antes, ensure_ascii=False, default=str) if antes else None,
         json.dumps(depois, ensure_ascii=False, default=str) if depois else None),
    )


# ------------------------------------------------------------------ código
def gerar_codigo(con, tipo_item: str) -> str:
    prefixo = tipos.tipo(tipo_item).prefixo
    linha = con.execute(
        "SELECT TOP 1 codigo FROM item_catalogo WHERE codigo LIKE ? "
        "ORDER BY id_item DESC", (f"{prefixo}-%",)
    ).fetchone()
    proximo = 1
    if linha:
        try:
            proximo = int(linha["codigo"].split("-")[1]) + 1
        except (IndexError, ValueError):
            proximo = con.execute("SELECT COUNT(*) c FROM item_catalogo").fetchone()["c"] + 1
    return f"{prefixo}-{proximo:05d}"


# -------------------------------------------------------------------- CRUD
def criar_item(con, *, tipo_item: str, nome: str, descricao: str = "",
               id_pai: int | None = None, id_squad: int | None = None,
               criticidade: str = "media", atributos: dict | None = None,
               usuario: str = "sistema", origem: str = "manual") -> int:
    t = tipos.tipo(tipo_item)
    if criticidade not in tipos.CRITICIDADES:
        raise RegraDeNegocio(f"criticidade inválida: {criticidade}")
    if t.pai and id_pai:
        pai = con.execute(
            "SELECT tipo_item FROM item_catalogo WHERE id_item = ?", (id_pai,)
        ).fetchone()
        if pai is None:
            raise RegraDeNegocio("item pai inexistente")
        if pai["tipo_item"] != t.pai:
            raise RegraDeNegocio(
                f"{t.rotulo} deve ser filho de {tipos.tipo(t.pai).rotulo}")
    dup = con.execute(
        "SELECT 1 FROM item_catalogo WHERE tipo_item = ? AND lower(nome) = lower(?)",
        (tipo_item, nome),
    ).fetchone()
    if dup:
        raise RegraDeNegocio(f"já existe {t.rotulo} com o nome '{nome}'")

    codigo = gerar_codigo(con, tipo_item)
    id_item = con.execute(
        "INSERT INTO item_catalogo (tipo_item, codigo, nome, descricao, id_pai,"
        " id_squad, criticidade, atributos, criado_por, origem)"
        " OUTPUT INSERTED.id_item VALUES (?,?,?,?,?,?,?,?,?,?)",
        (tipo_item, codigo, nome.strip(), descricao.strip(), id_pai, id_squad,
         criticidade, json.dumps(atributos or {}, ensure_ascii=False), usuario, origem),
    ).fetchone()[0]
    auditar(con, id_item, "criar", usuario, depois={"codigo": codigo, "nome": nome})
    qualidade.registrar(con, id_item)
    con.commit()
    return id_item


def atualizar_item(con, id_item: int, campos: dict, usuario: str = "sistema") -> None:
    antes = dict(con.execute(
        "SELECT * FROM item_catalogo WHERE id_item = ?", (id_item,)).fetchone())
    if antes["status_ciclo_vida"] == "publicado":
        raise RegraDeNegocio(
            "versão publicada é imutável; abra uma revisão antes de alterar")
    if antes["status_ciclo_vida"] in ("descontinuado", "arquivado"):
        raise RegraDeNegocio("item fora de uso não pode ser alterado")

    permitidos = {"nome", "descricao", "id_pai", "id_squad", "criticidade"}
    sets, valores = [], []
    for chave, valor in campos.items():
        if chave in permitidos:
            sets.append(f"{chave} = ?")
            valores.append(valor)
    if "atributos" in campos:
        atuais = json.loads(antes["atributos"] or "{}")
        atuais.update(campos["atributos"])
        sets.append("atributos = ?")
        valores.append(json.dumps(atuais, ensure_ascii=False))
    if not sets:
        return
    sets.append("atualizado_em = CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120)")
    con.execute(f"UPDATE item_catalogo SET {', '.join(sets)} WHERE id_item = ?",
                (*valores, id_item))
    auditar(con, id_item, "alterar", usuario, antes=antes, depois=campos)
    qualidade.registrar(con, id_item)
    con.commit()


def definir_responsavel(con, id_item: int, id_pessoa: int, papel: str,
                        usuario: str = "sistema") -> None:
    con.execute(
        "UPDATE responsabilidade SET fim_vigencia = CONVERT(NVARCHAR(10), SYSUTCDATETIME(), 23) "
        "WHERE id_item = ? AND papel = ? AND fim_vigencia IS NULL",
        (id_item, papel),
    )
    con.execute(
        "INSERT INTO responsabilidade (id_item, id_pessoa, papel) VALUES (?,?,?)",
        (id_item, id_pessoa, papel),
    )
    auditar(con, id_item, "definir_responsavel", usuario,
            depois={"papel": papel, "id_pessoa": id_pessoa})
    qualidade.registrar(con, id_item)
    con.commit()


def relacionar(con, id_origem: int, id_destino: int, tipo_relacao: str,
               criticidade: str = "media", mecanismo: str | None = None,
               origem_evidencia: str = "manual", usuario: str = "sistema") -> int:
    if tipo_relacao not in tipos.RELACOES:
        raise RegraDeNegocio(f"tipo de relação inválido: {tipo_relacao}")
    if id_origem == id_destino:
        raise RegraDeNegocio("um ativo não se relaciona consigo mesmo")
    nova = con.execute(
        "INSERT INTO relacionamento_ativo "
        "(id_origem, id_destino, tipo_relacao, criticidade, mecanismo, origem_evidencia) "
        "OUTPUT INSERTED.id_relacao "
        "SELECT ?,?,?,?,?,? WHERE NOT EXISTS ("
        "  SELECT 1 FROM relacionamento_ativo WHERE id_origem = ? AND id_destino = ?"
        "   AND tipo_relacao = ?)",
        (id_origem, id_destino, tipo_relacao, criticidade, mecanismo, origem_evidencia,
         id_origem, id_destino, tipo_relacao),
    ).fetchone()
    inserida = nova is not None
    id_relacao = nova[0] if inserida else con.execute(
        "SELECT id_relacao FROM relacionamento_ativo WHERE id_origem = ? "
        "AND id_destino = ? AND tipo_relacao = ?",
        (id_origem, id_destino, tipo_relacao)).fetchone()[0]
    if tipo_relacao == "depende_de" and governanca._tem_ciclo(con, id_origem):
        # só apaga se este INSERT realmente criou a linha; se foi ignorado por
        # duplicidade, o id devolvido é o da relação que já existia
        if inserida:
            con.execute("DELETE FROM relacionamento_ativo WHERE id_relacao = ?",
                        (id_relacao,))
        con.commit()
        raise RegraDeNegocio("relação criaria dependência circular entre contextos")
    auditar(con, id_origem, "relacionar", usuario,
            depois={"destino": id_destino, "tipo": tipo_relacao})
    qualidade.registrar(con, id_origem)
    con.commit()
    return id_relacao


def anexar_evidencia(con, id_item: int, tipo_ev: str, titulo: str,
                     url: str | None = None, origem: str = "manual",
                     usuario: str = "sistema") -> int:
    id_evidencia = con.execute(
        "INSERT INTO evidencia (id_item, tipo, titulo, url, origem) "
        "OUTPUT INSERTED.id_evidencia VALUES (?,?,?,?,?)",
        (id_item, tipo_ev, titulo, url, origem),
    ).fetchone()[0]
    auditar(con, id_item, "anexar_evidencia", usuario, depois={"titulo": titulo})
    qualidade.registrar(con, id_item)
    con.commit()
    return id_evidencia


# ------------------------------------------------------- revisão e publicação
def _snapshot(con, id_item: int) -> dict:
    item = dict(con.execute(
        "SELECT * FROM item_catalogo WHERE id_item = ?", (id_item,)).fetchone())
    item["responsaveis"] = [dict(r) for r in con.execute(
        "SELECT papel, id_pessoa FROM responsabilidade "
        "WHERE id_item = ? AND fim_vigencia IS NULL", (id_item,))]
    item["relacoes"] = [dict(r) for r in con.execute(
        "SELECT id_destino, tipo_relacao, criticidade FROM relacionamento_ativo "
        "WHERE id_origem = ? AND fim_vigencia IS NULL", (id_item,))]
    item["evidencias"] = [dict(r) for r in con.execute(
        "SELECT tipo, titulo, url FROM evidencia WHERE id_item = ?", (id_item,))]
    return item


def submeter(con, id_item: int, motivo: str = "", usuario: str = "sistema") -> dict:
    """Roda o pré-check, cria a revisão e abre as validações da política."""
    item = con.execute(
        "SELECT status_ciclo_vida FROM item_catalogo WHERE id_item = ?", (id_item,)
    ).fetchone()
    if item is None:
        raise RegraDeNegocio("item não encontrado")
    origem = item["status_ciclo_vida"]
    if origem not in ("rascunho", "em_revisao"):
        raise RegraDeNegocio(f"não é possível submeter item em '{origem}'")

    resultado = governanca.pre_check(con, id_item)
    if not resultado["aprovado"]:
        return resultado

    payload = _snapshot(con, id_item)
    bruto = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    # numero_revisao é calculado dentro do próprio INSERT (não em um SELECT
    # separado) para que a leitura do MAX e a escrita sejam uma única
    # operação atômica sob a trava de escrita do SQLite, evitando a corrida
    # entre submissões concorrentes do mesmo item.
    try:
        cur = con.execute(
            "INSERT INTO revisao_catalogo "
            "(id_item, numero_revisao, payload, payload_hash, motivo, criado_por) "
            "OUTPUT INSERTED.id_revisao "
            "SELECT ?, COALESCE(MAX(numero_revisao), 0) + 1, ?, ?, ?, ? "
            "FROM revisao_catalogo WHERE id_item = ?",
            (id_item, bruto, hashlib.sha256(bruto.encode("utf-8")).hexdigest(),
             motivo, usuario, id_item),
        )
    except ErroIntegridade:
        con.rollback()
        raise RegraDeNegocio(
            "conflito ao gerar número de revisão; tente submeter novamente")
    id_revisao = cur.fetchone()[0]
    numero_revisao = con.execute(
        "SELECT numero_revisao FROM revisao_catalogo WHERE id_revisao = ?",
        (id_revisao,),
    ).fetchone()["numero_revisao"]
    if origem == "rascunho":
        con.execute(
            "UPDATE item_catalogo SET status_ciclo_vida = 'em_validacao',"
            " atualizado_em = CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120) WHERE id_item = ?", (id_item,))
    ids_validacao = governanca.abrir_validacoes(con, id_item, id_revisao, usuario)
    auditar(con, id_item, "submeter", usuario,
            depois={"revisao": numero_revisao, "motivo": motivo})
    _avisar_validadores(con, id_item, ids_validacao, usuario)
    con.commit()
    resultado["id_revisao"] = id_revisao
    resultado["numero_revisao"] = numero_revisao
    return resultado


def _avisar_validadores(con, id_item: int, ids_validacao: list[int],
                        autor: str) -> None:
    """Enfileira o aviso na mesma transação da submissão (padrão outbox)."""
    from . import acesso, notificacoes

    item = con.execute("SELECT nome, codigo FROM item_catalogo WHERE id_item = ?",
                       (id_item,)).fetchone()
    for id_validacao in ids_validacao:
        etapa = con.execute("SELECT etapa FROM validacao WHERE id_validacao = ?",
                            (id_validacao,)).fetchone()["etapa"]
        aptos = acesso.quem_pode_decidir(con, id_validacao)
        notificacoes.para_muitos(
            con, aptos, "revisao_submetida",
            f"{item['nome']} aguarda validação {etapa}",
            f"{item['codigo']} entrou na fila da etapa {etapa}.",
            url=f"/validacoes?id_validacao={id_validacao}",
            id_item=id_item, id_validacao=id_validacao,
            sufixo_chave=f"revisao_submetida:{id_validacao}")


def decidir_validacao(con, id_validacao: int, aprovar: bool, parecer: str,
                      usuario: str = "sistema", id_pessoa: int | None = None) -> dict:
    """Decide uma etapa de validação.

    Quando `id_pessoa` é informado — sempre, vindo da interface — a decisão
    passa pela autorização: o papel tem de bater com a etapa e quem submeteu a
    revisão não decide sobre ela. Chamadas internas (CLI, carga) omitem a
    pessoa e seguem sem essa verificação, porque não há sessão a verificar.
    """
    val = con.execute(
        "SELECT * FROM validacao WHERE id_validacao = ?", (id_validacao,)).fetchone()
    if val is None:
        raise RegraDeNegocio("validação não encontrada")
    if val["situacao"] != "pendente":
        raise RegraDeNegocio("validação já concluída")
    if id_pessoa is not None:
        from . import acesso
        autorizado, motivo = acesso.pode_decidir(con, id_pessoa, id_validacao)
        if not autorizado:
            raise acesso.SemPermissao(motivo)

    con.execute(
        "UPDATE validacao SET situacao = ?, parecer = ?, responsavel = ?,"
        " concluido_em = CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120) WHERE id_validacao = ?",
        ("aprovada" if aprovar else "rejeitada", parecer, usuario, id_validacao),
    )
    id_item = val["id_item"]
    auditar(con, id_item, "validar", usuario,
            depois={"etapa": val["etapa"], "aprovada": aprovar, "parecer": parecer})

    if not aprovar:
        con.execute(
            "UPDATE validacao SET situacao = 'rejeitada', concluido_em = CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120),"
            " parecer = 'Cancelada por rejeição em outra etapa' "
            "WHERE id_item = ? AND id_revisao = ? AND situacao = 'pendente'",
            (id_item, val["id_revisao"]),
        )
        con.execute(
            "UPDATE item_catalogo SET status_ciclo_vida = 'rascunho',"
            " atualizado_em = CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120) WHERE id_item = ? "
            "AND status_ciclo_vida = 'em_validacao'", (id_item,))
        _avisar_autor_da_rejeicao(con, id_item, val, parecer, usuario)
        con.commit()
        return {"situacao": "rejeitada", "publicado": False}

    pendentes = con.execute(
        "SELECT COUNT(*) c FROM validacao WHERE id_item = ? AND id_revisao = ?"
        " AND situacao = 'pendente'", (id_item, val["id_revisao"])
    ).fetchone()["c"]
    if pendentes:
        con.commit()
        return {"situacao": "aprovada", "publicado": False, "pendentes": pendentes}

    publicar(con, id_item, val["id_revisao"], usuario)
    return {"situacao": "aprovada", "publicado": True}


def _avisar_autor_da_rejeicao(con, id_item: int, val, parecer: str,
                              usuario: str) -> None:
    from . import acesso, notificacoes

    revisao = con.execute("SELECT criado_por FROM revisao_catalogo WHERE id_revisao = ?",
                          (val["id_revisao"],)).fetchone()
    if revisao is None or not revisao["criado_por"]:
        return
    autor = acesso.pessoa_por_login(con, revisao["criado_por"])
    if autor is None:
        return
    item = con.execute("SELECT nome, codigo FROM item_catalogo WHERE id_item = ?",
                       (id_item,)).fetchone()
    notificacoes.registrar(
        con, autor["id_pessoa"], "revisao_rejeitada",
        f"Revisão de {item['nome']} rejeitada na etapa {val['etapa']}",
        parecer or "Sem parecer registrado.",
        url=f"/ativo/{id_item}", id_item=id_item,
        id_validacao=val["id_validacao"],
        chave_unica=f"revisao_rejeitada:{val['id_validacao']}")


def _avisar_consumidores(con, id_item: int, usuario: str) -> None:
    """Avisa quem responde pelos ativos que consomem o que acabou de publicar."""
    from . import notificacoes

    item = con.execute("SELECT nome, codigo FROM item_catalogo WHERE id_item = ?",
                       (id_item,)).fetchone()
    vistos: set[int] = set()
    destinatarios = []
    for consumidor in governanca.impacto_descontinuacao(con, id_item):
        for linha in con.execute(
                "SELECT DISTINCT p.id_pessoa FROM responsabilidade r "
                "JOIN pessoa p ON p.id_pessoa = r.id_pessoa "
                "WHERE r.id_item = ? AND r.fim_vigencia IS NULL AND p.ativo = 1",
                (consumidor["id_item"],)):
            if linha["id_pessoa"] not in vistos:
                vistos.add(linha["id_pessoa"])
                destinatarios.append({"id_pessoa": linha["id_pessoa"]})
    if destinatarios:
        notificacoes.para_muitos(
            con, destinatarios, "ativo_publicado",
            f"{item['nome']} publicou uma nova revisão",
            f"{item['codigo']} é consumido por um ativo sob sua responsabilidade.",
            url=f"/ativo/{id_item}", id_item=id_item,
            sufixo_chave=f"ativo_publicado:{id_item}:{date.today().isoformat()}")


def publicar(con, id_item: int, id_revisao: int, usuario: str = "sistema") -> None:
    con.execute(
        "UPDATE revisao_catalogo SET publicada_em = CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120) WHERE id_revisao = ?",
        (id_revisao,))
    con.execute(
        "UPDATE item_catalogo SET status_ciclo_vida = 'publicado', revisao_atual = ?,"
        " inicio_vigencia = COALESCE(inicio_vigencia, CONVERT(NVARCHAR(10), SYSUTCDATETIME(), 23)),"
        " atualizado_em = CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120) WHERE id_item = ?",
        (id_revisao, id_item))
    auditar(con, id_item, "publicar", usuario, depois={"id_revisao": id_revisao})
    qualidade.registrar(con, id_item)
    _avisar_consumidores(con, id_item, usuario)
    con.commit()


def abrir_revisao(con, id_item: int, usuario: str = "sistema") -> None:
    item = con.execute(
        "SELECT status_ciclo_vida FROM item_catalogo WHERE id_item = ?", (id_item,)
    ).fetchone()
    if item["status_ciclo_vida"] != "publicado":
        raise RegraDeNegocio("só é possível revisar item publicado")
    con.execute(
        "UPDATE item_catalogo SET status_ciclo_vida = 'em_revisao',"
        " atualizado_em = CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120) WHERE id_item = ?", (id_item,))
    auditar(con, id_item, "abrir_revisao", usuario)
    con.commit()


def descontinuar(con, id_item: int, motivo: str, usuario: str = "sistema",
                 forcar: bool = False) -> dict:
    item = con.execute(
        "SELECT status_ciclo_vida FROM item_catalogo WHERE id_item = ?", (id_item,)
    ).fetchone()
    if item is None:
        raise RegraDeNegocio("item não encontrado")
    atual = item["status_ciclo_vida"]
    if "descontinuado" not in governanca.TRANSICOES.get(atual, set()):
        raise RegraDeNegocio(f"transição inválida: {atual} → descontinuado")
    impacto = governanca.impacto_descontinuacao(con, id_item)
    criticos = [i for i in impacto if i["criticidade"] in ("alta", "critica")]
    if criticos and not forcar:
        return {"bloqueado": True, "impacto": impacto,
                "motivo": "Existem consumidores ativos de alta criticidade não tratados"}
    con.execute(
        "UPDATE item_catalogo SET status_ciclo_vida = 'descontinuado',"
        " fim_vigencia = CONVERT(NVARCHAR(10), SYSUTCDATETIME(), 23), atualizado_em = CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120) WHERE id_item = ?",
        (id_item,))
    con.execute(
        "UPDATE relacionamento_ativo SET fim_vigencia = CONVERT(NVARCHAR(10), SYSUTCDATETIME(), 23) "
        "WHERE (id_origem = ? OR id_destino = ?) AND fim_vigencia IS NULL",
        (id_item, id_item))
    auditar(con, id_item, "descontinuar", usuario,
            depois={"motivo": motivo, "impactados": len(impacto)})
    con.commit()
    return {"bloqueado": False, "impacto": impacto}


def alterar_status(con, id_item: int, novo: str, usuario: str = "sistema") -> None:
    atual = con.execute(
        "SELECT status_ciclo_vida FROM item_catalogo WHERE id_item = ?", (id_item,)
    ).fetchone()["status_ciclo_vida"]
    if novo not in governanca.TRANSICOES.get(atual, set()):
        raise RegraDeNegocio(f"transição inválida: {atual} → {novo}")
    con.execute(
        "UPDATE item_catalogo SET status_ciclo_vida = ?, atualizado_em = CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120) "
        "WHERE id_item = ?", (novo, id_item))
    auditar(con, id_item, "transicao", usuario, antes={"status": atual}, depois={"status": novo})
    con.commit()


# ------------------------------------------------------------------ consultas
# Colunas por que o catálogo pode ser ordenado. Lista fechada: o parâmetro vem
# da URL e vai direto para o ORDER BY.
ORDENACOES = {
    "nome": "i.nome",
    "tipo": "i.tipo_item, i.nome",
    "status": "i.status_ciclo_vida, i.nome",
    "criticidade": ("CASE i.criticidade WHEN 'critica' THEN 0 WHEN 'alta' THEN 1"
                    " WHEN 'media' THEN 2 ELSE 3 END, i.nome"),
    "score": "score",
    "atualizado": "i.atualizado_em",
}
ORDEM_PADRAO = "tipo"


def _filtro_busca(termo: str = "", tipo_item: str = "", status: str = "",
                  id_squad: str | int = "", criticidade: str = "",
                  sem_owner: str = "", origem: str = "") -> tuple[str, list]:
    """Monta o WHERE compartilhado pela listagem, pela contagem e pela API."""
    sql, params = ["WHERE 1 = 1"], []
    if termo:
        sql.append("AND (i.nome LIKE ? OR i.codigo LIKE ? OR i.descricao LIKE ?)")
        alvo = f"%{termo}%"
        params += [alvo, alvo, alvo]
    if tipo_item:
        sql.append("AND i.tipo_item = ?")
        params.append(tipo_item)
    if status:
        sql.append("AND i.status_ciclo_vida = ?")
        params.append(status)
    if id_squad:
        sql.append("AND i.id_squad = ?")
        params.append(int(id_squad))
    if criticidade:
        sql.append("AND i.criticidade = ?")
        params.append(criticidade)
    if origem:
        sql.append("AND i.origem = ?")
        params.append(origem)
    if sem_owner:
        # recorte do KPI "Sem responsável" do painel executivo
        sql.append("AND NOT EXISTS (SELECT 1 FROM responsabilidade r "
                   "WHERE r.id_item = i.id_item AND r.fim_vigencia IS NULL)")
    return " ".join(sql), params


_SELECT_BUSCA = (
    "SELECT i.*, s.nome AS squad,"
    " (SELECT TOP 1 q.score_total FROM qualidade_catalogo q WHERE q.id_item = i.id_item"
    "   ORDER BY q.id_qualidade DESC) AS score,"
    " p.nome AS pai_nome"
    " FROM item_catalogo i"
    " LEFT JOIN squad s ON s.id_squad = i.id_squad"
    " LEFT JOIN item_catalogo p ON p.id_item = i.id_pai "
)


def buscar(con, limite: int = 200, ordenar: str = ORDEM_PADRAO,
           descendente: bool = False, **filtros) -> list[dict]:
    onde, params = _filtro_busca(**filtros)
    ordem = ORDENACOES.get(ordenar, ORDENACOES[ORDEM_PADRAO])
    direcao = " DESC" if descendente else ""
    return [dict(l) for l in con.execute(
        f"{_SELECT_BUSCA} {onde} ORDER BY {ordem}{direcao} OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY",
        [*params, limite])]


def contar(con, **filtros) -> int:
    onde, params = _filtro_busca(**filtros)
    return con.execute(
        f"SELECT COUNT(*) FROM item_catalogo i {onde}", params).fetchone()[0]


def buscar_pagina(con, pagina: int = 1, por_pagina: int = 50,
                  ordenar: str = ORDEM_PADRAO, descendente: bool = False,
                  **filtros) -> dict:
    """Uma página do catálogo, com o total real — o rodapé parava de dizer a
    verdade a partir do teto fixo de 200 linhas."""
    total = contar(con, **filtros)
    paginas = max(1, -(-total // por_pagina))
    pagina = min(max(1, pagina), paginas)
    onde, params = _filtro_busca(**filtros)
    ordem = ORDENACOES.get(ordenar, ORDENACOES[ORDEM_PADRAO])
    direcao = " DESC" if descendente else ""
    itens = [dict(l) for l in con.execute(
        f"{_SELECT_BUSCA} {onde} ORDER BY {ordem}{direcao} OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
        [*params, (pagina - 1) * por_pagina, por_pagina])]
    return {"itens": itens, "total": total, "pagina": pagina, "paginas": paginas,
            "por_pagina": por_pagina,
            "primeiro": 0 if not total else (pagina - 1) * por_pagina + 1,
            "ultimo": min(pagina * por_pagina, total)}


def trilha(con, id_item: int) -> list[dict]:
    """Ancestrais de um ativo, da raiz até o pai direto.

    Sobe a hierarquia por ``id_pai`` numa única consulta recursiva, para que a
    interface possa mostrar Domínio › Subdomínio › Contexto › Capacidade sem
    uma ida ao banco por nível.
    """
    linhas = con.execute(
        "WITH sobe(id_item, id_pai, nome, tipo_item, nivel) AS ("
        "  SELECT id_item, id_pai, nome, tipo_item, 0"
        "    FROM item_catalogo WHERE id_item = ?"
        "  UNION ALL"
        "  SELECT p.id_item, p.id_pai, p.nome, p.tipo_item, s.nivel + 1"
        "    FROM item_catalogo p JOIN sobe s ON p.id_item = s.id_pai"
        "   WHERE s.nivel < 12"
        ") SELECT id_item, nome, tipo_item FROM sobe WHERE nivel > 0"
        " ORDER BY nivel DESC", (id_item,)).fetchall()
    return [dict(l) for l in linhas]


def visao_360(con, id_item: int) -> dict:
    item = con.execute(
        "SELECT i.*, s.nome AS squad, p.nome AS pai_nome, p.id_item AS pai_id "
        "FROM item_catalogo i LEFT JOIN squad s ON s.id_squad = i.id_squad "
        "LEFT JOIN item_catalogo p ON p.id_item = i.id_pai WHERE i.id_item = ?",
        (id_item,)).fetchone()
    if item is None:
        raise LookupError("item não encontrado")
    item = dict(item)
    item["atributos"] = json.loads(item["atributos"] or "{}")

    saida = [dict(l) for l in con.execute(
        "SELECT r.*, d.nome, d.codigo, d.tipo_item, d.status_ciclo_vida "
        "FROM relacionamento_ativo r JOIN item_catalogo d ON d.id_item = r.id_destino "
        "WHERE r.id_origem = ? AND r.fim_vigencia IS NULL", (id_item,))]
    entrada = [dict(l) for l in con.execute(
        "SELECT r.*, o.nome, o.codigo, o.tipo_item, o.status_ciclo_vida "
        "FROM relacionamento_ativo r JOIN item_catalogo o ON o.id_item = r.id_origem "
        "WHERE r.id_destino = ? AND r.fim_vigencia IS NULL", (id_item,))]
    filhos = [dict(l) for l in con.execute(
        "SELECT id_item, codigo, nome, tipo_item, status_ciclo_vida "
        "FROM item_catalogo WHERE id_pai = ? ORDER BY nome", (id_item,))]
    responsaveis = [dict(l) for l in con.execute(
        "SELECT r.papel, r.inicio_vigencia, p.nome, p.email FROM responsabilidade r "
        "JOIN pessoa p ON p.id_pessoa = r.id_pessoa "
        "WHERE r.id_item = ? AND r.fim_vigencia IS NULL", (id_item,))]
    evidencias = [dict(l) for l in con.execute(
        "SELECT * FROM evidencia WHERE id_item = ? ORDER BY id_evidencia DESC", (id_item,))]
    revisoes = [dict(l) for l in con.execute(
        "SELECT id_revisao, numero_revisao, motivo, criado_por, criado_em, publicada_em, "
        "substr(payload_hash, 1, 12) AS hash FROM revisao_catalogo "
        "WHERE id_item = ? ORDER BY numero_revisao DESC", (id_item,))]
    validacoes = [dict(l) for l in con.execute(
        "SELECT * FROM validacao WHERE id_item = ? ORDER BY id_validacao DESC", (id_item,))]
    auditoria = [dict(l) for l in con.execute(
        "SELECT TOP 30 * FROM auditoria_evento WHERE id_item = ? "
        "ORDER BY id_evento DESC", (id_item,))]

    return {
        "item": item,
        "relacoes_saida": saida,
        "relacoes_entrada": entrada,
        "filhos": filhos,
        "responsaveis": responsaveis,
        "evidencias": evidencias,
        "revisoes": revisoes,
        "validacoes": validacoes,
        "auditoria": auditoria,
        "qualidade": qualidade.avaliar(con, id_item),
        "proxima_revisao": qualidade.proxima_revisao(con, id_item),
        "impacto": governanca.impacto_descontinuacao(con, id_item),
    }


def comparar_revisoes(con, id_item: int, a: int, b: int) -> dict:
    def carregar(numero):
        linha = con.execute(
            "SELECT payload FROM revisao_catalogo WHERE id_item = ? AND numero_revisao = ?",
            (id_item, numero)).fetchone()
        return json.loads(linha["payload"]) if linha else {}

    pa, pb = carregar(a), carregar(b)
    chaves = sorted(set(pa) | set(pb))
    return {k: {"antes": pa.get(k), "depois": pb.get(k)}
            for k in chaves if pa.get(k) != pb.get(k)}


# ------------------------------------------------------------- indicadores
def indicadores(con) -> dict:
    def escalar(sql, params=()):
        return con.execute(sql, params).fetchone()[0] or 0

    publicados = escalar(
        "SELECT COUNT(*) FROM item_catalogo WHERE status_ciclo_vida = 'publicado'")
    capacidades = escalar(
        "SELECT COUNT(*) FROM item_catalogo WHERE tipo_item = 'capacidade'"
        " AND status_ciclo_vida IN ('publicado','em_revisao')")
    cobertas = escalar(
        "SELECT COUNT(*) FROM vw_cobertura_capacidade v "
        "JOIN item_catalogo i ON i.id_item = v.id_item "
        "WHERE v.implementacoes > 0 AND i.status_ciclo_vida IN ('publicado','em_revisao')")
    sem_owner = escalar(
        "SELECT COUNT(*) FROM item_catalogo i WHERE i.status_ciclo_vida = 'publicado' "
        "AND NOT EXISTS (SELECT 1 FROM responsabilidade r WHERE r.id_item = i.id_item "
        "AND r.fim_vigencia IS NULL)")
    apis = escalar("SELECT COUNT(*) FROM item_catalogo WHERE tipo_item = 'api'")
    apis_governadas = escalar(
        "SELECT COUNT(*) FROM item_catalogo i WHERE i.tipo_item = 'api' "
        "AND i.status_ciclo_vida = 'publicado' "
        "AND EXISTS (SELECT 1 FROM relacionamento_ativo r WHERE r.id_origem = i.id_item "
        "AND r.tipo_relacao = 'implementa' AND r.fim_vigencia IS NULL)")
    pendencias = escalar("SELECT COUNT(*) FROM validacao WHERE situacao = 'pendente'")
    vencidas = escalar(
        "SELECT COUNT(*) FROM validacao WHERE situacao = 'pendente' AND prazo < CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120)")
    dominios = escalar(
        "SELECT COUNT(*) FROM item_catalogo WHERE tipo_item = 'dominio' "
        "AND status_ciclo_vida IN ('publicado','em_revisao')")
    dep_criticas = escalar(
        "SELECT COUNT(*) FROM relacionamento_ativo WHERE tipo_relacao = 'depende_de' "
        "AND criticidade IN ('alta','critica') AND fim_vigencia IS NULL")

    return {
        "dominios": dominios,
        "capacidades": capacidades,
        "cobertura": round(100 * cobertas / capacidades) if capacidades else 0,
        "sem_owner": sem_owner,
        "apis": apis,
        "apis_governadas": round(100 * apis_governadas / apis) if apis else 0,
        "pendencias": pendencias,
        "sla_vencido": vencidas,
        "publicados": publicados,
        "qualidade_media": qualidade.media_geral(con),
        "dependencias_criticas": dep_criticas,
    }


def cobertura_por_dominio(con) -> list[dict]:
    linhas = con.execute("""
        WITH cap AS (
          SELECT c.id_item, ctx.id_pai AS id_sub,
                 (SELECT COUNT(*) FROM relacionamento_ativo r
                   WHERE r.id_destino = c.id_item AND r.tipo_relacao = 'implementa'
                     AND r.fim_vigencia IS NULL) AS impl
          FROM item_catalogo c
          JOIN item_catalogo ctx ON ctx.id_item = c.id_pai
          WHERE c.tipo_item = 'capacidade'
        )
        SELECT d.id_item, d.nome,
               COUNT(cap.id_item) AS total,
               SUM(CASE WHEN cap.impl > 0 THEN 1 ELSE 0 END) AS cobertas
        FROM item_catalogo d
        JOIN item_catalogo sub ON sub.id_pai = d.id_item
        LEFT JOIN cap ON cap.id_sub = sub.id_item
        WHERE d.tipo_item = 'dominio'
        GROUP BY d.id_item ORDER BY d.nome
    """).fetchall()
    saida = []
    for l in linhas:
        total = l["total"] or 0
        cobertas = l["cobertas"] or 0
        saida.append({"id_item": l["id_item"], "nome": l["nome"], "total": total,
                      "cobertas": cobertas,
                      "percentual": round(100 * cobertas / total) if total else 0})
    return saida


def pendencias_prioritarias(con) -> list[dict]:
    consultas = [
        ("Capacidade sem owner",
         "SELECT COUNT(*) FROM item_catalogo i WHERE i.tipo_item = 'capacidade' "
         "AND NOT EXISTS (SELECT 1 FROM responsabilidade r WHERE r.id_item = i.id_item "
         "AND r.papel = 'owner_negocial' AND r.fim_vigencia IS NULL)",
         {"tipo_item": "capacidade"}),
        ("API sem capacidade vinculada",
         "SELECT COUNT(*) FROM item_catalogo i WHERE i.tipo_item = 'api' "
         "AND NOT EXISTS (SELECT 1 FROM relacionamento_ativo r WHERE r.id_origem = i.id_item "
         "AND r.tipo_relacao = 'implementa' AND r.fim_vigencia IS NULL)",
         {"tipo_item": "api"}),
        ("Repositório sem mantenedor",
         "SELECT COUNT(*) FROM item_catalogo i WHERE i.tipo_item = 'repositorio' "
         "AND NOT EXISTS (SELECT 1 FROM responsabilidade r WHERE r.id_item = i.id_item "
         "AND r.fim_vigencia IS NULL)",
         {"tipo_item": "repositorio"}),
        ("Validação com SLA vencido",
         "SELECT COUNT(*) FROM validacao WHERE situacao = 'pendente' "
         "AND prazo < CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120)", {"destino": "validacoes"}),
        ("Dependência crítica sem evidência",
         "SELECT COUNT(*) FROM relacionamento_ativo r WHERE r.tipo_relacao = 'depende_de' "
         "AND r.criticidade IN ('alta','critica') AND r.fim_vigencia IS NULL "
         "AND r.origem_evidencia = 'manual'", {}),
    ]
    return [{"titulo": t, "total": con.execute(sql).fetchone()[0], "filtro": f}
            for t, sql, f in consultas]


def gerar_snapshot(con, competencia: str | None = None) -> None:
    """Materializa indicadores do mês para a camada analítica."""
    competencia = competencia or date.today().strftime("%Y-%m")
    for chave, valor in indicadores(con).items():
        # sem upsert de uma instrução: atualiza, e insere se nada foi atualizado
        atualizadas = con.execute(
            "UPDATE snapshot_indicador SET valor = ?,"
            " gerado_em = CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120) "
            "WHERE competencia = ? AND indicador = ? AND recorte = 'geral'",
            (float(valor), competencia, chave)).rowcount
        if not atualizadas:
            con.execute(
                "INSERT INTO snapshot_indicador (competencia, indicador, valor) "
                "VALUES (?,?,?)", (competencia, chave, float(valor)))
    con.commit()


def serie_historica(con, indicador: str) -> list[dict]:
    return [dict(l) for l in con.execute(
        "SELECT competencia, valor FROM snapshot_indicador "
        "WHERE indicador = ? ORDER BY competencia", (indicador,))]


# Campos do snapshot que mudam por mecânica do ciclo de vida, não por decisão
# de quem cadastra: poluem a leitura do validador e ficam fora do resumo.
CAMPOS_MECANICOS = {"id_item", "codigo", "revisao_atual", "criado_em", "atualizado_em",
                    "criado_por", "status_ciclo_vida", "inicio_vigencia", "fim_vigencia"}

ROTULOS_DIFF = {
    "nome": "Nome", "descricao": "Descrição", "criticidade": "Criticidade",
    "tipo_item": "Tipo", "id_pai": "Item pai", "id_squad": "Squad",
    "atributos": "Campos do tipo", "responsaveis": "Responsáveis",
    "relacoes": "Relações", "evidencias": "Evidências",
}


def _resumir_valor(chave: str, valor) -> str:
    """Transforma o pedaço do payload em algo que uma pessoa lê de relance."""
    if valor in (None, "", [], {}):
        return "—"
    if chave == "atributos" and isinstance(valor, dict):
        return " · ".join(f"{k}: {v}" for k, v in sorted(valor.items()) if v) or "—"
    if isinstance(valor, list):
        if chave == "evidencias":
            corpo = ", ".join(e.get("titulo", "") for e in valor)
        elif chave == "responsaveis":
            corpo = ", ".join(e.get("papel", "").replace("_", " ") for e in valor)
        elif chave == "relacoes":
            corpo = ", ".join(f"{e.get('tipo_relacao')} #{e.get('id_destino')}"
                              for e in valor)
        else:
            corpo = ", ".join(str(e) for e in valor)
        return f"{len(valor)}: {corpo}" if corpo else str(len(valor))
    return str(valor)


def diff_da_revisao(con, id_item: int, id_revisao: int | None) -> dict:
    """O que mudou na revisão em análise, contra a revisão anterior.

    O validador decidia sem ver a diferença: o comparador existia e só era
    alcançável por um link no fim do histórico. Aqui ele vem resumido — sem os
    campos que o próprio ciclo de vida mexe.
    """
    vazio = {"numero": None, "anterior": None, "diff": {}, "primeira": True}
    if not id_revisao:
        return vazio
    linha = con.execute(
        "SELECT numero_revisao FROM revisao_catalogo WHERE id_revisao = ?",
        (id_revisao,)).fetchone()
    if linha is None:
        return vazio
    numero = linha["numero_revisao"]
    if numero <= 1:
        return {**vazio, "numero": numero}

    bruto = comparar_revisoes(con, id_item, numero - 1, numero)
    resumo = {}
    for chave, valores in bruto.items():
        if chave in CAMPOS_MECANICOS:
            continue
        resumo[ROTULOS_DIFF.get(chave, chave)] = {
            "antes": _resumir_valor(chave, valores["antes"]),
            "depois": _resumir_valor(chave, valores["depois"]),
        }
    return {"numero": numero, "anterior": numero - 1, "primeira": False,
            "diff": resumo}


def arvore(con, tipo_raiz: str) -> list[dict]:
    """Monta a hierarquia inteira a partir de um tipo de raiz, numa consulta só.

    Serve as duas árvores do catálogo — Domínio → Capacidade e
    Sistema → Endpoint — porque a hierarquia é sempre ``id_pai``.
    """
    linhas = con.execute(
        "SELECT i.id_item, i.id_pai, i.nome, i.codigo, i.tipo_item,"
        " i.status_ciclo_vida,"
        " (SELECT COUNT(*) FROM relacionamento_ativo r WHERE r.id_destino = i.id_item"
        "   AND r.tipo_relacao = 'implementa' AND r.fim_vigencia IS NULL)"
        "   AS implementacoes"
        " FROM item_catalogo i WHERE i.status_ciclo_vida <> 'arquivado'"
        " ORDER BY i.nome").fetchall()
    nos = {l["id_item"]: {**dict(l), "filhos": []} for l in linhas}
    for no in nos.values():
        pai = nos.get(no["id_pai"])
        if pai is not None:
            pai["filhos"].append(no)
    return [n for n in nos.values() if n["tipo_item"] == tipo_raiz]


def vizinhanca(con, id_item: int, saltos: int = 1, tipos_relacao: tuple = (),
               teto: int = 150) -> dict:
    """Vizinhança de N saltos no grafo de relações, com teto explícito.

    As árvores do mapa mostram a hierarquia; isto mostra o que elas não
    alcançam — as relações transversais que cruzam domínios e sistemas. A
    expansão trata as arestas como não direcionadas (quem consome importa tanto
    quanto quem é consumido), mas cada aresta devolvida preserva a direção real.

    `truncado` faz parte do contrato: um recorte silencioso faria a tela mentir
    sobre o alcance da mudança.
    """
    saltos = max(1, min(int(saltos), 3))
    filtro = ""
    params_filtro: list = []
    if tipos_relacao:
        marcas = ",".join("?" * len(tipos_relacao))
        filtro = f" AND r.tipo_relacao IN ({marcas})"
        params_filtro = list(tipos_relacao)

    distancias = {id_item: 0}
    fronteira = [id_item]
    truncado = False
    for salto in range(1, saltos + 1):
        if not fronteira or truncado:
            break
        marcas = ",".join("?" * len(fronteira))
        vizinhos = con.execute(
            "SELECT r.id_origem, r.id_destino FROM relacionamento_ativo r"
            f" WHERE r.fim_vigencia IS NULL{filtro}"
            f" AND (r.id_origem IN ({marcas}) OR r.id_destino IN ({marcas}))",
            [*params_filtro, *fronteira, *fronteira]).fetchall()
        proxima = []
        for linha in vizinhos:
            for lado in (linha["id_origem"], linha["id_destino"]):
                if lado in distancias:
                    continue
                if len(distancias) >= teto:
                    truncado = True
                    break
                distancias[lado] = salto
                proxima.append(lado)
            if truncado:
                break
        fronteira = proxima

    ids = list(distancias)
    marcas = ",".join("?" * len(ids))
    nos = [{**dict(l), "salto": distancias[l["id_item"]]} for l in con.execute(
        "SELECT i.id_item, i.codigo, i.nome, i.tipo_item, i.status_ciclo_vida,"
        " i.criticidade FROM item_catalogo i"
        f" WHERE i.id_item IN ({marcas})", ids)]
    arestas = [dict(l) for l in con.execute(
        "SELECT r.id_origem, r.id_destino, r.tipo_relacao, r.criticidade,"
        " r.mecanismo FROM relacionamento_ativo r"
        f" WHERE r.fim_vigencia IS NULL{filtro}"
        f" AND r.id_origem IN ({marcas}) AND r.id_destino IN ({marcas})",
        [*params_filtro, *ids, *ids])]
    nos.sort(key=lambda n: (n["salto"], n["nome"]))
    return {"centro": id_item, "saltos": saltos, "nos": nos, "arestas": arestas,
            "truncado": truncado, "teto": teto}


def posicionar_vizinhanca(dados: dict, largura: int = 900, altura: int = 560) -> dict:
    """Coloca os nós em anéis concêntricos por distância do centro.

    Layout escrito à mão, sem biblioteca: o anel diz a distância de relação e a
    leitura fica estável entre visitas — o mesmo grafo desenha igual toda vez,
    o que um layout de força não garante.
    """
    cx, cy = largura / 2, altura / 2
    # anéis elípticos: a tela é mais larga que alta, e um raio único deixaria
    # metade do desenho vazia
    rx_max, ry_max = largura / 2 - 160, altura / 2 - 50
    por_salto: dict[int, list] = {}
    for no in dados["nos"]:
        por_salto.setdefault(no["salto"], []).append(no)

    saltos = max(por_salto) if por_salto else 0
    posicoes = {}
    for salto, nos in sorted(por_salto.items()):
        if salto == 0:
            for no in nos:
                posicoes[no["id_item"]] = (cx, cy)
            continue
        fracao = salto / max(saltos, 1)
        rx, ry = rx_max * fracao, ry_max * fracao
        # cada anel gira um pouco para os nós não ficarem alinhados em raios
        giro = math.pi / (len(nos) or 1) * (salto % 2)
        for indice, no in enumerate(nos):
            angulo = 2 * math.pi * indice / len(nos) + giro
            posicoes[no["id_item"]] = (cx + rx * math.cos(angulo),
                                       cy + ry * math.sin(angulo))

    nos = [{**no, "x": round(posicoes[no["id_item"]][0], 1),
            "y": round(posicoes[no["id_item"]][1], 1)} for no in dados["nos"]]
    arestas = []
    for a in dados["arestas"]:
        if a["id_origem"] not in posicoes or a["id_destino"] not in posicoes:
            continue
        x1, y1 = posicoes[a["id_origem"]]
        x2, y2 = posicoes[a["id_destino"]]
        arestas.append({**a, "x1": round(x1, 1), "y1": round(y1, 1),
                        "x2": round(x2, 1), "y2": round(y2, 1)})
    return {**dados, "nos": nos, "arestas": arestas,
            "largura": largura, "altura": altura}


def grafo_catalogo(con, id_dominio: int | None = None,
                   id_subdominio: int | None = None,
                   id_item: int | None = None,
                   largura: int = 900, altura: int = 520) -> dict:
    """Exibe todos os ativos ou apenas os descendentes de um recorte."""
    def descendentes(raiz: int) -> set[int]:
        return {linha["id_item"] for linha in con.execute(
            "WITH descendentes(id_item) AS ("
            "SELECT id_item FROM item_catalogo WHERE id_item = ? "
            "UNION ALL SELECT i.id_item FROM item_catalogo i "
            "JOIN descendentes d ON i.id_pai = d.id_item) "
            "SELECT id_item FROM descendentes", (raiz,))}

    escopos = [descendentes(raiz) for raiz in
               (id_item or id_dominio, id_subdominio) if raiz]
    escopo = set.intersection(*escopos) if escopos else None
    filtrado = any((id_item, id_dominio, id_subdominio))
    if escopo is None:
        escopo = {linha["id_item"] for linha in con.execute(
            "SELECT id_item FROM item_catalogo WHERE status_ciclo_vida != 'arquivado'")}
    marcas = ",".join("?" for _ in escopo)
    nos = [dict(l) for l in con.execute(
        "SELECT id_item, id_pai, tipo_item, nome, codigo, criticidade "
        "FROM item_catalogo WHERE status_ciclo_vida != 'arquivado' "
        f"AND id_item IN ({marcas}) ORDER BY tipo_item, nome", list(escopo))]
    if not nos:
        return {"nos": [], "arestas": [], "largura": largura,
            "altura": altura, "expandido": True, "filtrado": filtrado}

    cx, cy = largura / 2, altura / 2
    rx, ry = largura / 2 - 80, altura / 2 - 75
    posicoes = {}
    for indice, no in enumerate(nos):
        angulo = 2 * math.pi * indice / len(nos) - math.pi / 2
        posicoes[no["id_item"]] = (cx + rx * math.cos(angulo),
                                    cy + ry * math.sin(angulo))
        no["x"], no["y"] = (round(posicoes[no["id_item"]][0], 1),
                              round(posicoes[no["id_item"]][1], 1))
    arestas = [{"id_origem": no["id_pai"], "id_destino": no["id_item"],
                "tipo_relacao": "hierarquia", "criticidade": "",
                "mecanismo": "pai/filho"}
               for no in nos if no["id_pai"] in posicoes]
    if not filtrado:
        arestas.extend(dict(l) for l in con.execute(
            "SELECT r.id_origem, r.id_destino, r.tipo_relacao, r.criticidade, "
            "r.mecanismo FROM relacionamento_ativo r "
            f"WHERE r.fim_vigencia IS NULL AND r.id_origem IN ({marcas}) "
            f"AND r.id_destino IN ({marcas}) ORDER BY r.tipo_relacao", [*escopo, *escopo]))
    for aresta in arestas:
        x1, y1 = posicoes[aresta["id_origem"]]
        x2, y2 = posicoes[aresta["id_destino"]]
        aresta.update(x1=round(x1, 1), y1=round(y1, 1),
                      x2=round(x2, 1), y2=round(y2, 1))
    return {"nos": nos, "arestas": arestas, "largura": largura,
            "altura": altura, "expandido": True, "filtrado": filtrado}


def analise_impacto(con, id_item: int) -> dict:
    """Quem depende deste ativo, agrupado — não só a contagem do cartão final."""
    consumidores = governanca.impacto_descontinuacao(con, id_item)
    por_criticidade: dict[str, int] = {}
    por_tipo: dict[str, int] = {}
    for c in consumidores:
        por_criticidade[c["criticidade"]] = por_criticidade.get(c["criticidade"], 0) + 1
        por_tipo[c["tipo_item"]] = por_tipo.get(c["tipo_item"], 0) + 1
    criticos = [c for c in consumidores if c["criticidade"] in ("alta", "critica")]
    return {"consumidores": consumidores, "total": len(consumidores),
            "criticos": criticos, "por_criticidade": por_criticidade,
            "por_tipo": por_tipo}


# ------------------------------------------------------- bandeja de descobertas
def descobertas(con, limite: int = 200) -> list[dict]:
    """Itens que a máquina trouxe e ninguém validou ainda."""
    return buscar(con, origem="automatica", status="rascunho",
                  ordenar="atualizado", descendente=True, limite=limite)


def triar(con, ids: list[int], acao: str, usuario: str = "sistema") -> dict:
    """Aceita ou descarta itens descobertos, em lote.

    Aceitar não altera o cadastro: apenas marca que uma pessoa olhou, tirando o
    item da bandeja. Descartar arquiva, preservando a trilha.
    """
    if acao not in ("aceitar", "descartar"):
        raise RegraDeNegocio(f"ação de triagem inválida: {acao}")
    tratados = 0
    for id_item in ids:
        linha = con.execute(
            "SELECT status_ciclo_vida, origem FROM item_catalogo WHERE id_item = ?",
            (id_item,)).fetchone()
        if linha is None or linha["origem"] != "automatica":
            continue
        if acao == "aceitar":
            con.execute("UPDATE item_catalogo SET origem = 'manual',"
                        " atualizado_em = CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120) WHERE id_item = ?", (id_item,))
        else:
            if linha["status_ciclo_vida"] not in ("rascunho", "em_validacao"):
                continue
            con.execute("UPDATE item_catalogo SET status_ciclo_vida = 'arquivado',"
                        " atualizado_em = CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120) WHERE id_item = ?", (id_item,))
        auditar(con, id_item, f"triagem_{acao}", usuario, origem="descobertas")
        tratados += 1
    con.commit()
    return {"acao": acao, "tratados": tratados}


def relacionar_em_lote(con, id_origem: int, destinos: list[int], tipo_relacao: str,
                       criticidade: str = "media", mecanismo: str | None = None,
                       usuario: str = "sistema") -> dict:
    """Registra várias relações do mesmo tipo de uma vez.

    Mapear as dependências de uma aplicação custava um POST e uma recarga por
    relação; aqui o gesto é um só.
    """
    criadas, ignoradas, erros = 0, 0, []
    for destino in destinos:
        if destino == id_origem:
            ignoradas += 1
            continue
        ja_existe = con.execute(
            "SELECT 1 FROM relacionamento_ativo WHERE id_origem = ? AND id_destino = ?"
            " AND tipo_relacao = ?", (id_origem, destino, tipo_relacao)).fetchone()
        if ja_existe:
            ignoradas += 1
            continue
        try:
            relacionar(con, id_origem, destino, tipo_relacao, criticidade,
                       mecanismo, usuario=usuario)
            criadas += 1
        except RegraDeNegocio as erro:
            erros.append(str(erro))
    return {"criadas": criadas, "ignoradas": ignoradas, "erros": erros}


def minha_mesa(con, usuario: str) -> dict:
    """O trabalho que é meu: o que assumi, o que posso assumir e o que cadastrei."""
    def itens(status: tuple) -> list[dict]:
        marcas = ",".join("?" * len(status))
        return [dict(l) for l in con.execute(
            "SELECT i.id_item, i.codigo, i.nome, i.tipo_item, i.status_ciclo_vida,"
            " i.criticidade, i.atualizado_em,"
            " (SELECT TOP 1 q.score_total FROM qualidade_catalogo q WHERE q.id_item = i.id_item"
            "   ORDER BY q.id_qualidade DESC) AS score"
            " FROM item_catalogo i WHERE i.criado_por = ?"
            f" AND i.status_ciclo_vida IN ({marcas})"
            " ORDER BY i.atualizado_em DESC", (usuario, *status))]

    return {
        "minhas_validacoes": governanca.fila_validacao(con, atribuido_a=usuario),
        "fila_livre": governanca.fila_validacao(con, apenas_livres=True),
        "meus_rascunhos": itens(("rascunho", "em_revisao")),
        "aguardando_decisao": itens(("em_validacao",)),
    }


def variacao_indicadores(con) -> dict[str, float]:
    """Diferença de cada indicador entre as duas últimas competências.

    Um número sozinho não diz se a situação melhorou; a série mensal já está
    materializada em ``snapshot_indicador`` e só faltava chegar ao painel.
    """
    series: dict[str, list[float]] = {}
    for linha in con.execute(
            "SELECT indicador, valor FROM snapshot_indicador "
            "ORDER BY indicador, competencia"):
        series.setdefault(linha["indicador"], []).append(linha["valor"])
    return {chave: round(valores[-1] - valores[-2], 1)
            for chave, valores in series.items() if len(valores) >= 2}
