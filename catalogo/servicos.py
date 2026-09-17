"""Casos de uso do catálogo: cadastro, revisão, validação e publicação."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, datetime

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
        "SELECT codigo FROM item_catalogo WHERE codigo LIKE ? "
        "ORDER BY id_item DESC LIMIT 1", (f"{prefixo}-%",)
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
               usuario: str = "sistema") -> int:
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
    cur = con.execute(
        "INSERT INTO item_catalogo (tipo_item, codigo, nome, descricao, id_pai,"
        " id_squad, criticidade, atributos, criado_por) VALUES (?,?,?,?,?,?,?,?,?)",
        (tipo_item, codigo, nome.strip(), descricao.strip(), id_pai, id_squad,
         criticidade, json.dumps(atributos or {}, ensure_ascii=False), usuario),
    )
    id_item = cur.lastrowid
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
    sets.append("atualizado_em = datetime('now')")
    con.execute(f"UPDATE item_catalogo SET {', '.join(sets)} WHERE id_item = ?",
                (*valores, id_item))
    auditar(con, id_item, "alterar", usuario, antes=antes, depois=campos)
    qualidade.registrar(con, id_item)
    con.commit()


def definir_responsavel(con, id_item: int, id_pessoa: int, papel: str,
                        usuario: str = "sistema") -> None:
    con.execute(
        "UPDATE responsabilidade SET fim_vigencia = date('now') "
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
    cur = con.execute(
        "INSERT OR IGNORE INTO relacionamento_ativo "
        "(id_origem, id_destino, tipo_relacao, criticidade, mecanismo, origem_evidencia) "
        "VALUES (?,?,?,?,?,?)",
        (id_origem, id_destino, tipo_relacao, criticidade, mecanismo, origem_evidencia),
    )
    inserida = cur.rowcount == 1
    if tipo_relacao == "depende_de" and governanca._tem_ciclo(con, id_origem):
        # só apaga se este INSERT realmente criou a linha; se foi ignorado por
        # duplicidade (relação já existente), cur.lastrowid não se refere a ela
        if inserida:
            con.execute("DELETE FROM relacionamento_ativo WHERE id_relacao = ?",
                        (cur.lastrowid,))
        con.commit()
        raise RegraDeNegocio("relação criaria dependência circular entre contextos")
    auditar(con, id_origem, "relacionar", usuario,
            depois={"destino": id_destino, "tipo": tipo_relacao})
    qualidade.registrar(con, id_origem)
    con.commit()
    return cur.lastrowid


def anexar_evidencia(con, id_item: int, tipo_ev: str, titulo: str,
                     url: str | None = None, origem: str = "manual",
                     usuario: str = "sistema") -> int:
    cur = con.execute(
        "INSERT INTO evidencia (id_item, tipo, titulo, url, origem) VALUES (?,?,?,?,?)",
        (id_item, tipo_ev, titulo, url, origem),
    )
    auditar(con, id_item, "anexar_evidencia", usuario, depois={"titulo": titulo})
    qualidade.registrar(con, id_item)
    con.commit()
    return cur.lastrowid


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
            "SELECT ?, COALESCE(MAX(numero_revisao), 0) + 1, ?, ?, ?, ? "
            "FROM revisao_catalogo WHERE id_item = ?",
            (id_item, bruto, hashlib.sha256(bruto.encode("utf-8")).hexdigest(),
             motivo, usuario, id_item),
        )
    except sqlite3.IntegrityError:
        con.rollback()
        raise RegraDeNegocio(
            "conflito ao gerar número de revisão; tente submeter novamente")
    id_revisao = cur.lastrowid
    numero_revisao = con.execute(
        "SELECT numero_revisao FROM revisao_catalogo WHERE id_revisao = ?",
        (id_revisao,),
    ).fetchone()["numero_revisao"]
    if origem == "rascunho":
        con.execute(
            "UPDATE item_catalogo SET status_ciclo_vida = 'em_validacao',"
            " atualizado_em = datetime('now') WHERE id_item = ?", (id_item,))
    governanca.abrir_validacoes(con, id_item, id_revisao, usuario)
    auditar(con, id_item, "submeter", usuario,
            depois={"revisao": numero_revisao, "motivo": motivo})
    con.commit()
    resultado["id_revisao"] = id_revisao
    resultado["numero_revisao"] = numero_revisao
    return resultado


def decidir_validacao(con, id_validacao: int, aprovar: bool, parecer: str,
                      usuario: str = "sistema") -> dict:
    val = con.execute(
        "SELECT * FROM validacao WHERE id_validacao = ?", (id_validacao,)).fetchone()
    if val is None:
        raise RegraDeNegocio("validação não encontrada")
    if val["situacao"] != "pendente":
        raise RegraDeNegocio("validação já concluída")

    con.execute(
        "UPDATE validacao SET situacao = ?, parecer = ?, responsavel = ?,"
        " concluido_em = datetime('now') WHERE id_validacao = ?",
        ("aprovada" if aprovar else "rejeitada", parecer, usuario, id_validacao),
    )
    id_item = val["id_item"]
    auditar(con, id_item, "validar", usuario,
            depois={"etapa": val["etapa"], "aprovada": aprovar, "parecer": parecer})

    if not aprovar:
        con.execute(
            "UPDATE validacao SET situacao = 'rejeitada', concluido_em = datetime('now'),"
            " parecer = 'Cancelada por rejeição em outra etapa' "
            "WHERE id_item = ? AND id_revisao = ? AND situacao = 'pendente'",
            (id_item, val["id_revisao"]),
        )
        con.execute(
            "UPDATE item_catalogo SET status_ciclo_vida = 'rascunho',"
            " atualizado_em = datetime('now') WHERE id_item = ? "
            "AND status_ciclo_vida = 'em_validacao'", (id_item,))
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


def publicar(con, id_item: int, id_revisao: int, usuario: str = "sistema") -> None:
    con.execute(
        "UPDATE revisao_catalogo SET publicada_em = datetime('now') WHERE id_revisao = ?",
        (id_revisao,))
    con.execute(
        "UPDATE item_catalogo SET status_ciclo_vida = 'publicado', revisao_atual = ?,"
        " inicio_vigencia = COALESCE(inicio_vigencia, date('now')),"
        " atualizado_em = datetime('now') WHERE id_item = ?",
        (id_revisao, id_item))
    auditar(con, id_item, "publicar", usuario, depois={"id_revisao": id_revisao})
    qualidade.registrar(con, id_item)
    con.commit()


def abrir_revisao(con, id_item: int, usuario: str = "sistema") -> None:
    item = con.execute(
        "SELECT status_ciclo_vida FROM item_catalogo WHERE id_item = ?", (id_item,)
    ).fetchone()
    if item["status_ciclo_vida"] != "publicado":
        raise RegraDeNegocio("só é possível revisar item publicado")
    con.execute(
        "UPDATE item_catalogo SET status_ciclo_vida = 'em_revisao',"
        " atualizado_em = datetime('now') WHERE id_item = ?", (id_item,))
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
        " fim_vigencia = date('now'), atualizado_em = datetime('now') WHERE id_item = ?",
        (id_item,))
    con.execute(
        "UPDATE relacionamento_ativo SET fim_vigencia = date('now') "
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
        "UPDATE item_catalogo SET status_ciclo_vida = ?, atualizado_em = datetime('now') "
        "WHERE id_item = ?", (novo, id_item))
    auditar(con, id_item, "transicao", usuario, antes={"status": atual}, depois={"status": novo})
    con.commit()


# ------------------------------------------------------------------ consultas
def buscar(con, termo: str = "", tipo_item: str = "", status: str = "",
           id_squad: str | int = "", criticidade: str = "", sem_owner: str = "",
           limite: int = 200) -> list[dict]:
    sql = [
        "SELECT i.*, s.nome AS squad,",
        " (SELECT q.score_total FROM qualidade_catalogo q WHERE q.id_item = i.id_item",
        "   ORDER BY q.id_qualidade DESC LIMIT 1) AS score,",
        " p.nome AS pai_nome",
        "FROM item_catalogo i",
        "LEFT JOIN squad s ON s.id_squad = i.id_squad",
        "LEFT JOIN item_catalogo p ON p.id_item = i.id_pai",
        "WHERE 1 = 1",
    ]
    params: list = []
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
    if sem_owner:
        # recorte do KPI "Sem responsável" do painel executivo
        sql.append("AND NOT EXISTS (SELECT 1 FROM responsabilidade r "
                   "WHERE r.id_item = i.id_item AND r.fim_vigencia IS NULL)")
    sql.append("ORDER BY i.tipo_item, i.nome LIMIT ?")
    params.append(limite)
    return [dict(l) for l in con.execute(" ".join(sql), params)]


def trilha(con, id_item: int) -> list[dict]:
    """Ancestrais de um ativo, da raiz até o pai direto.

    Sobe a hierarquia por ``id_pai`` numa única consulta recursiva, para que a
    interface possa mostrar Domínio › Subdomínio › Contexto › Capacidade sem
    uma ida ao banco por nível.
    """
    linhas = con.execute(
        "WITH RECURSIVE sobe(id_item, id_pai, nome, tipo_item, nivel) AS ("
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
        "SELECT * FROM auditoria_evento WHERE id_item = ? "
        "ORDER BY id_evento DESC LIMIT 30", (id_item,))]

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
        "SELECT COUNT(*) FROM validacao WHERE situacao = 'pendente' AND prazo < datetime('now')")
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
         "AND prazo < datetime('now')", {"destino": "validacoes"}),
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
        con.execute(
            "INSERT INTO snapshot_indicador (competencia, indicador, valor) VALUES (?,?,?) "
            "ON CONFLICT(competencia, indicador, recorte) DO UPDATE SET valor = excluded.valor,"
            " gerado_em = datetime('now')",
            (competencia, chave, float(valor)))
    con.commit()


def serie_historica(con, indicador: str) -> list[dict]:
    return [dict(l) for l in con.execute(
        "SELECT competencia, valor FROM snapshot_indicador "
        "WHERE indicador = ? ORDER BY competencia", (indicador,))]


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
