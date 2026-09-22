"""Notificações no padrão outbox (F4.3).

O caso de uso grava a notificação na mesma transação do fato que a gerou —
atribuir uma validação e avisar quem vai analisá-la não podem divergir. Um
comando agendado (`flask --app catalogo notificar`) despacha o que ainda não
saiu e marca `enviado_em`. Sem broker, sem serviço auxiliar, testável com o
mesmo banco dos testes; se o volume crescer, o mesmo contrato migra para uma
fila real sem reescrever caso de uso nenhum.

O canal `app` é o sino da interface e não precisa de identidade externa. Os
canais `email` e `teams` ficam declarados e desligados até a decisão 12.1-a
sair: sem fonte de identidade não há endereço confiável para onde mandar.
"""
from __future__ import annotations

from datetime import datetime, timedelta

TIPOS = {
    "revisao_submetida": {
        "rotulo": "Revisão aguardando sua análise",
        "urgente": True,
    },
    "sla_vencendo": {
        "rotulo": "SLA de validação vencendo",
        "urgente": True,
    },
    "sla_vencido": {
        "rotulo": "SLA de validação vencido",
        "urgente": True,
    },
    "revisao_rejeitada": {
        "rotulo": "Sua revisão foi rejeitada",
        "urgente": True,
    },
    "ativo_publicado": {
        "rotulo": "Ativo que você consome foi publicado",
        "urgente": False,
    },
    "acesso_solicitado": {
        "rotulo": "Pleito de acesso aguardando decisão",
        "urgente": True,
    },
    "acesso_decidido": {
        "rotulo": "Resposta ao seu pleito de acesso",
        "urgente": True,
    },
}

CANAIS = {"app": "No catálogo", "email": "E-mail", "teams": "Teams"}
CANAIS_DISPONIVEIS = ("app",)   # os demais dependem da decisão 12.1-a

HORAS_AVISO_SLA = 24


def _quer_receber(con, id_pessoa: int, tipo: str, canal: str) -> bool:
    linha = con.execute(
        "SELECT ativo FROM preferencia_notificacao "
        "WHERE id_pessoa = ? AND tipo = ? AND canal = ?",
        (id_pessoa, tipo, canal)).fetchone()
    return True if linha is None else bool(linha["ativo"])


def registrar(con, id_pessoa: int, tipo: str, titulo: str, corpo: str = "",
              url: str | None = None, id_item: int | None = None,
              id_validacao: int | None = None, chave_unica: str | None = None,
              canal: str = "app") -> int | None:
    """Enfileira uma notificação. NÃO faz commit: entra na transação de quem chamou.

    Devolve None quando a pessoa desligou o tipo ou quando `chave_unica` já foi
    usada — é o que impede o vigia de SLA de repetir o mesmo alerta.
    """
    if tipo not in TIPOS:
        raise ValueError(f"tipo de notificação desconhecido: {tipo}")
    if not _quer_receber(con, id_pessoa, tipo, canal):
        return None
    if chave_unica and con.execute(
            "SELECT 1 FROM notificacao WHERE chave_unica = ?", (chave_unica,)).fetchone():
        return None
    return con.execute(
        "INSERT INTO notificacao (id_pessoa, tipo, id_item, id_validacao, titulo,"
        " corpo, url, chave_unica, canal) OUTPUT INSERTED.id_notificacao "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (id_pessoa, tipo, id_item, id_validacao, titulo, corpo, url, chave_unica,
         canal)).fetchone()[0]


def para_muitos(con, pessoas: list[dict], tipo: str, titulo: str, corpo: str = "",
                url: str | None = None, id_item: int | None = None,
                id_validacao: int | None = None, sufixo_chave: str | None = None,
                excluir: int | None = None) -> int:
    enviadas = 0
    for p in pessoas:
        if excluir and p["id_pessoa"] == excluir:
            continue
        chave = f"{sufixo_chave}:{p['id_pessoa']}" if sufixo_chave else None
        if registrar(con, p["id_pessoa"], tipo, titulo, corpo, url, id_item,
                     id_validacao, chave):
            enviadas += 1
    return enviadas


# ------------------------------------------------------------------- leitura
def caixa(con, id_pessoa: int, apenas_nao_lidas: bool = False,
          limite: int = 50) -> list[dict]:
    sql = ("SELECT n.*, i.nome AS item_nome, i.codigo AS item_codigo "
           "FROM notificacao n LEFT JOIN item_catalogo i ON i.id_item = n.id_item "
           "WHERE n.id_pessoa = ?")
    params: list = [id_pessoa]
    if apenas_nao_lidas:
        sql += " AND n.lido_em IS NULL"
    sql += " ORDER BY n.criado_em DESC, n.id_notificacao DESC OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY"
    params.append(limite)
    return [dict(l) for l in con.execute(sql, params)]


def nao_lidas(con, id_pessoa: int) -> int:
    return con.execute(
        "SELECT COUNT(*) FROM notificacao WHERE id_pessoa = ? AND lido_em IS NULL",
        (id_pessoa,)).fetchone()[0]


def marcar_lida(con, id_notificacao: int, id_pessoa: int) -> None:
    con.execute("UPDATE notificacao SET lido_em = CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120) "
                "WHERE id_notificacao = ? AND id_pessoa = ? AND lido_em IS NULL",
                (id_notificacao, id_pessoa))
    con.commit()


def marcar_todas_lidas(con, id_pessoa: int) -> int:
    cur = con.execute("UPDATE notificacao SET lido_em = CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120) "
                      "WHERE id_pessoa = ? AND lido_em IS NULL", (id_pessoa,))
    con.commit()
    return cur.rowcount


def preferencias(con, id_pessoa: int) -> dict:
    guardadas = {(l["tipo"], l["canal"]): bool(l["ativo"]) for l in con.execute(
        "SELECT tipo, canal, ativo FROM preferencia_notificacao WHERE id_pessoa = ?",
        (id_pessoa,))}
    return {tipo: {canal: guardadas.get((tipo, canal), canal == "app")
                   for canal in CANAIS}
            for tipo in TIPOS}


def salvar_preferencias(con, id_pessoa: int, ativas: set[tuple[str, str]]) -> None:
    con.execute("DELETE FROM preferencia_notificacao WHERE id_pessoa = ?", (id_pessoa,))
    for tipo in TIPOS:
        for canal in CANAIS:
            con.execute(
                "INSERT INTO preferencia_notificacao (id_pessoa, tipo, canal, ativo) "
                "VALUES (?,?,?,?)",
                (id_pessoa, tipo, canal, 1 if (tipo, canal) in ativas else 0))
    con.commit()


# ------------------------------------------------------------------ despacho
def despachar(con, limite: int = 200) -> dict:
    """Envia o que está na outbox e marca. Idempotente: rodar duas vezes não duplica.

    O canal `app` já está entregue no momento em que a linha existe — marcar
    `enviado_em` apenas fecha o ciclo. Canais externos entram aqui quando a
    fonte de identidade estiver decidida.
    """
    pendentes = [dict(l) for l in con.execute(
        "SELECT * FROM notificacao WHERE enviado_em IS NULL "
        "ORDER BY id_notificacao OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY", (limite,))]
    por_canal: dict[str, int] = {}
    ignoradas = 0
    for n in pendentes:
        if n["canal"] not in CANAIS_DISPONIVEIS:
            ignoradas += 1
            continue
        con.execute("UPDATE notificacao SET enviado_em = CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120) "
                    "WHERE id_notificacao = ?", (n["id_notificacao"],))
        por_canal[n["canal"]] = por_canal.get(n["canal"], 0) + 1
    con.commit()
    return {"despachadas": sum(por_canal.values()), "por_canal": por_canal,
            "sem_canal_disponivel": ignoradas}


def vigiar_sla(con, agora: datetime | None = None) -> dict:
    """Gera avisos de SLA vencendo e vencido para a fila pendente.

    A chave única carrega o dia, então rodar de hora em hora não repete o
    mesmo alerta para a mesma validação.
    """
    from . import acesso

    agora = agora or datetime.now()
    hoje = agora.date().isoformat()
    limite = agora + timedelta(hours=HORAS_AVISO_SLA)
    criadas = {"sla_vencendo": 0, "sla_vencido": 0}

    pendentes = [dict(l) for l in con.execute(
        "SELECT v.id_validacao, v.id_item, v.etapa, v.prazo, v.atribuido_a,"
        " i.nome, i.codigo FROM validacao v "
        "JOIN item_catalogo i ON i.id_item = v.id_item "
        "WHERE v.situacao = 'pendente' AND v.prazo IS NOT NULL")]

    for v in pendentes:
        try:
            prazo = datetime.fromisoformat(v["prazo"])
        except ValueError:
            continue
        if prazo < agora:
            tipo = "sla_vencido"
        elif prazo <= limite:
            tipo = "sla_vencendo"
        else:
            continue

        destinatarios = acesso.quem_pode_decidir(con, v["id_validacao"])
        if v["atribuido_a"]:
            dono = acesso.pessoa_por_login(con, v["atribuido_a"])
            if dono:
                destinatarios = [dono]
        titulo = (f"{TIPOS[tipo]['rotulo']}: {v['nome']}")
        corpo = (f"Etapa {v['etapa']} · prazo {v['prazo']}. "
                 f"{'Já venceu.' if tipo == 'sla_vencido' else 'Vence em menos de 24h.'}")
        criadas[tipo] += para_muitos(
            con, destinatarios, tipo, titulo, corpo,
            url=f"/validacoes?id_validacao={v['id_validacao']}",
            id_item=v["id_item"], id_validacao=v["id_validacao"],
            sufixo_chave=f"{tipo}:{v['id_validacao']}:{hoje}")
    con.commit()
    return criadas
