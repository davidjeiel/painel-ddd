"""Identidade, papéis com escopo e autorização (F4.1).

A fonte de identidade ainda é o cadastro local — a decisão 12.1-a, quando sair,
troca apenas *de onde* a pessoa vem: `pessoa.identidade_externa` e
`origem_identidade` já existem para receber o `sub` de um provedor OIDC sem
mexer em papel, escopo ou nas regras deste módulo.

O que este módulo garante hoje e não existia antes: **a etapa de validação só é
aprovada por quem tem o papel correspondente naquele domínio**, e quem submeteu
não aprova a própria revisão.
"""
from __future__ import annotations

import re

from . import notificacoes, servicos, tipos

# Papéis, do mais amplo ao mais restrito.
PAPEIS = {
    "admin": "Administrador do catálogo",
    "curador": "Curador (cadastra e submete)",
    "arquiteto": "Arquiteto",
    "tech_lead": "Time técnico",
    "negocio": "Negócio",
    "consulta": "Somente consulta",
}

ESCOPOS = ("global", "dominio", "squad")

# Ação → papéis que a permitem. Mantido junto de PAPEIS porque é a mesma
# família de regra das políticas de governança.
PERMISSOES = {
    "cadastrar":   {"admin", "curador", "arquiteto", "tech_lead", "negocio"},
    "editar":      {"admin", "curador", "arquiteto", "tech_lead", "negocio"},
    "relacionar":  {"admin", "curador", "arquiteto", "tech_lead"},
    "submeter":    {"admin", "curador", "arquiteto", "tech_lead", "negocio"},
    "revisar":     {"admin", "curador", "arquiteto", "tech_lead", "negocio"},
    "descontinuar": {"admin", "curador", "arquiteto"},
    "importar":    {"admin", "curador", "tech_lead"},
    "triar":       {"admin", "curador", "tech_lead"},
    "decidir":     {"admin", "arquiteto", "tech_lead", "negocio"},
    "conceder":    {"admin", "curador"},
    "administrar": {"admin"},
}

# Bloco de tipos em que cada papel pode escrever. Sem isto, o papel autoriza a
# *ação* mas não o *objeto*: quem responde pelo negócio conseguia cadastrar uma
# API, e quem responde pela técnica conseguia redesenhar a hierarquia de
# domínios. Arquiteto, curador e admin atravessam os dois blocos por ofício.
TODOS_OS_BLOCOS = frozenset(tipos.blocos())
BLOCOS_POR_PAPEL = {
    "negocio": frozenset({"Estrutura DDD"}),
    "tech_lead": frozenset({"Ativos técnicos"}),
    "arquiteto": TODOS_OS_BLOCOS,
    "curador": TODOS_OS_BLOCOS,
    "admin": TODOS_OS_BLOCOS,
    "consulta": frozenset(),
}

# Ações que recaem sobre um ativo — só estas olham o bloco do tipo.
ACOES_SOBRE_ATIVO = frozenset({"cadastrar", "editar", "relacionar", "submeter",
                               "revisar", "descontinuar"})

# Matrícula: uma letra (normalmente C, E, F ou P) e seis números.
MATRICULA = re.compile(r"^[A-Za-z][0-9]{6}$")
LETRAS_USUAIS = ("C", "E", "F", "P")
# Unidade organizacional: código de quatro números.
UNIDADE = re.compile(r"^[0-9]{4}$")

STATUS_SOLICITACAO = ("pendente", "aprovada", "negada")

# Etapa de validação → papel exigido. É a regra que faltava: antes, qualquer
# pessoa aprovava qualquer etapa.
PAPEL_POR_ETAPA = {
    "negocial": {"admin", "negocio"},
    "tecnica": {"admin", "tech_lead"},
    "arquitetural": {"admin", "arquiteto"},
}

# Papel do ownership que também autoriza a etapa, quando a pessoa é responsável
# pelo próprio ativo.
OWNER_POR_ETAPA = {
    "negocial": "owner_negocial",
    "tecnica": "owner_tecnico",
    "arquitetural": "arquiteto",
}


class SemPermissao(Exception):
    """Ação recusada por falta de papel — 403, não erro de regra de negócio."""


# ------------------------------------------------------------------- pessoas
def pessoa_por_login(con, login: str) -> dict | None:
    linha = con.execute(
        "SELECT * FROM pessoa WHERE login = ? AND ativo = 1", (login,)).fetchone()
    return dict(linha) if linha else None


def pessoa(con, id_pessoa: int) -> dict | None:
    linha = con.execute(
        "SELECT * FROM pessoa WHERE id_pessoa = ?", (id_pessoa,)).fetchone()
    return dict(linha) if linha else None


def pessoas_ativas(con) -> list[dict]:
    return [dict(l) for l in con.execute(
        "SELECT p.*, s.nome AS squad FROM pessoa p "
        "LEFT JOIN squad s ON s.id_squad = p.id_squad "
        "WHERE p.ativo = 1 ORDER BY p.nome")]


def pessoas(con, termo: str = "") -> list[dict]:
    """Lista cadastros, opcionalmente filtrados por qualquer dado visível."""
    sql = (
        "SELECT p.*, s.nome AS squad FROM pessoa p "
        "LEFT JOIN squad s ON s.id_squad = p.id_squad "
    )
    parametros: list[str] = []
    if termo.strip():
        partes = [
            "p.nome", "p.matricula", "p.login", "p.email", "p.unidade",
            "p.perfil", "s.nome", "s.codigo", "CAST(p.id_pessoa AS TEXT)",
        ]
        sql += " WHERE " + " OR ".join(
            "LOWER(COALESCE({}, '')) LIKE LOWER(?)".format(parte)
            for parte in partes)
        parametros = [f"%{termo.strip()}%"] * len(partes)
    sql += " ORDER BY p.ativo DESC, p.nome"
    return [dict(l) for l in con.execute(sql, parametros)]


def interacoes_pessoa(con, id_pessoa: int) -> list[str]:
    """Retorna os vínculos que tornam um cadastro parte do histórico do sistema."""
    cadastro = pessoa(con, id_pessoa)
    identificadores = tuple(v for v in (
        cadastro.get("login") if cadastro else None,
        cadastro.get("matricula") if cadastro else None,
    ) if v)
    consultas = (
        ("papéis atribuídos", "SELECT 1 FROM atribuicao_papel WHERE id_pessoa = ?"),
        ("pleitos de acesso", "SELECT 1 FROM solicitacao_acesso WHERE id_pessoa = ?"),
        ("responsabilidades em ativos", "SELECT 1 FROM responsabilidade WHERE id_pessoa = ?"),
        ("notificações", "SELECT 1 FROM notificacao WHERE id_pessoa = ?"),
        ("preferências de notificação",
         "SELECT 1 FROM preferencia_notificacao WHERE id_pessoa = ?"),
    )
    interacoes = [nome for nome, sql in consultas
            if con.execute(sql, (id_pessoa,)).fetchone()]
    autoria = (
        ("ativos cadastrados", "SELECT 1 FROM item_catalogo WHERE criado_por IN ({})"),
        ("revisões criadas", "SELECT 1 FROM revisao_catalogo WHERE criado_por IN ({})"),
        ("eventos de auditoria", "SELECT 1 FROM auditoria_evento WHERE usuario IN ({})"),
    )
    if identificadores:
        marcadores = ",".join("?" for _ in identificadores)
        for nome, sql in autoria:
            if con.execute(sql.format(marcadores), identificadores).fetchone():
                interacoes.append(nome)
    return interacoes


def atualizar_pessoa(con, id_pessoa: int, nome: str, email: str,
                     unidade: str, id_squad: int | None, papel: str,
                     ativo: bool, concedido_por: str) -> None:
    if papel not in PAPEIS:
        raise servicos.RegraDeNegocio("papel desconhecido")
    pessoa_atual = pessoa(con, id_pessoa)
    if pessoa_atual is None:
        raise servicos.RegraDeNegocio("cadastro não encontrado")
    if not nome.strip():
        raise servicos.RegraDeNegocio("nome é obrigatório")
    con.execute(
        "UPDATE pessoa SET nome = ?, email = ?, unidade = ?, id_squad = ?, "
        "perfil = ?, ativo = ? WHERE id_pessoa = ?",
        (nome.strip(), email.strip(), unidade.strip(), id_squad, papel,
         int(ativo), id_pessoa))
    con.execute(
        "UPDATE atribuicao_papel SET fim_vigencia = date('now') "
        "WHERE id_pessoa = ? AND fim_vigencia IS NULL", (id_pessoa,))
    if ativo:
        conceder(con, id_pessoa, papel, concedido_por=concedido_por, commit=False)
    con.commit()


def inativar_pessoa(con, id_pessoa: int) -> None:
    if pessoa(con, id_pessoa) is None:
        raise servicos.RegraDeNegocio("cadastro não encontrado")
    con.execute("UPDATE pessoa SET ativo = 0 WHERE id_pessoa = ?", (id_pessoa,))
    con.execute("UPDATE atribuicao_papel SET fim_vigencia = date('now') "
                "WHERE id_pessoa = ? AND fim_vigencia IS NULL", (id_pessoa,))
    con.commit()


def excluir_pessoa(con, id_pessoa: int) -> None:
    interacoes = interacoes_pessoa(con, id_pessoa)
    if interacoes:
        raise servicos.RegraDeNegocio(
            "cadastro não pode ser excluído: " + ", ".join(interacoes) + ".")
    cur = con.execute("DELETE FROM pessoa WHERE id_pessoa = ?", (id_pessoa,))
    if not cur.rowcount:
        raise servicos.RegraDeNegocio("cadastro não encontrado")
    con.commit()


# -------------------------------------------------------------------- papéis
def conceder(con, id_pessoa: int, papel: str, escopo_tipo: str = "global",
             escopo_id: int | None = None, concedido_por: str = "sistema",
             commit: bool = True) -> int:
    if papel not in PAPEIS:
        raise servicos.RegraDeNegocio(f"papel desconhecido: {papel}")
    if escopo_tipo not in ESCOPOS:
        raise servicos.RegraDeNegocio(f"escopo desconhecido: {escopo_tipo}")
    if escopo_tipo != "global" and not escopo_id:
        raise servicos.RegraDeNegocio(f"escopo {escopo_tipo} exige um alvo")
    cur = con.execute(
        "INSERT INTO atribuicao_papel (id_pessoa, papel, escopo_tipo, escopo_id,"
        " concedido_por) VALUES (?,?,?,?,?)",
        (id_pessoa, papel, escopo_tipo, escopo_id, concedido_por))
    if commit:
        con.commit()
    return cur.lastrowid


def revogar(con, id_atribuicao: int) -> None:
    con.execute("UPDATE atribuicao_papel SET fim_vigencia = date('now') "
                "WHERE id_atribuicao = ? AND fim_vigencia IS NULL", (id_atribuicao,))
    con.commit()


def papeis(con, id_pessoa: int) -> list[dict]:
    return [dict(l) for l in con.execute(
        "SELECT * FROM atribuicao_papel WHERE id_pessoa = ? "
        "AND (fim_vigencia IS NULL OR fim_vigencia >= date('now')) "
        "ORDER BY papel", (id_pessoa,))]


def _dominio_do_item(con, id_item: int) -> int | None:
    """A que domínio este ativo pertence — sobe a hierarquia até a raiz.

    Reaproveita a mesma trilha que desenha o breadcrumb: quem responde
    "Domínio › Subdomínio › Contexto" responde também pelo escopo.
    """
    caminho = servicos.trilha(con, id_item)
    for no in caminho:
        if no["tipo_item"] == "dominio":
            return no["id_item"]
    item = con.execute("SELECT tipo_item FROM item_catalogo WHERE id_item = ?",
                       (id_item,)).fetchone()
    return id_item if item and item["tipo_item"] == "dominio" else None


def papeis_efetivos(con, id_pessoa: int, id_item: int | None = None) -> set[str]:
    """Papéis que valem para este item: os globais mais os do escopo dele."""
    dominio = _dominio_do_item(con, id_item) if id_item else None
    squad = None
    if id_item:
        linha = con.execute("SELECT id_squad FROM item_catalogo WHERE id_item = ?",
                            (id_item,)).fetchone()
        squad = linha["id_squad"] if linha else None
    efetivos = set()
    for p in papeis(con, id_pessoa):
        if p["escopo_tipo"] == "global":
            efetivos.add(p["papel"])
        elif p["escopo_tipo"] == "dominio" and dominio and p["escopo_id"] == dominio:
            efetivos.add(p["papel"])
        elif p["escopo_tipo"] == "squad" and squad and p["escopo_id"] == squad:
            efetivos.add(p["papel"])
    return efetivos


def _bloco_do_alvo(con, id_item: int | None, tipo_item: str | None) -> str | None:
    """Bloco de tipos a que o alvo pertence — o tipo dado, ou o do item."""
    if tipo_item:
        t = tipos.TIPOS.get(tipo_item)
        return t.bloco if t else None
    if id_item:
        linha = con.execute("SELECT tipo_item FROM item_catalogo WHERE id_item = ?",
                            (id_item,)).fetchone()
        if linha:
            t = tipos.TIPOS.get(linha["tipo_item"])
            return t.bloco if t else None
    return None


def pode(con, id_pessoa: int | None, acao: str, id_item: int | None = None,
         tipo_item: str | None = None) -> bool:
    """Ponto único de decisão de autorização.

    Três filtros, nesta ordem: o papel permite a ação, o escopo do papel alcança
    o ativo, e o papel escreve no bloco de tipos daquele ativo. O terceiro é o
    que impede alguém de negócio cadastrar um endpoint só porque "cadastrar"
    consta do seu papel.
    """
    if id_pessoa is None:
        return False
    permitidos = PERMISSOES.get(acao)
    if permitidos is None:
        raise servicos.RegraDeNegocio(f"ação desconhecida: {acao}")
    efetivos = papeis_efetivos(con, id_pessoa, id_item)
    if acao in ACOES_SOBRE_ATIVO:
        bloco = _bloco_do_alvo(con, id_item, tipo_item)
        if bloco:
            efetivos = {p for p in efetivos
                        if bloco in BLOCOS_POR_PAPEL.get(p, TODOS_OS_BLOCOS)}
    return bool(efetivos & permitidos)


def blocos_que_escreve(con, id_pessoa: int | None) -> set[str]:
    """Blocos de tipos em que esta pessoa pode cadastrar — usado pelo wizard."""
    if id_pessoa is None:
        return set()
    alcance: set[str] = set()
    for papel in {p["papel"] for p in papeis(con, id_pessoa)}:
        if papel in PERMISSOES["cadastrar"]:
            alcance |= set(BLOCOS_POR_PAPEL.get(papel, TODOS_OS_BLOCOS))
    return alcance


def pode_decidir(con, id_pessoa: int | None, id_validacao: int) -> tuple[bool, str]:
    """Autorização da decisão de validação, com o motivo da recusa.

    Duas regras: o papel tem de bater com a etapa, e quem submeteu a revisão
    não decide sobre ela (segregação de função).
    """
    if id_pessoa is None:
        return False, "Sessão sem pessoa identificada."
    val = con.execute(
        "SELECT v.*, r.criado_por FROM validacao v "
        "LEFT JOIN revisao_catalogo r ON r.id_revisao = v.id_revisao "
        "WHERE v.id_validacao = ?", (id_validacao,)).fetchone()
    if val is None:
        return False, "Validação não encontrada."

    quem = pessoa(con, id_pessoa)
    if quem and val["criado_por"] and val["criado_por"] == (quem.get("login") or ""):
        return False, ("Segregação de função: quem submeteu a revisão não decide "
                       "sobre ela.")

    efetivos = papeis_efetivos(con, id_pessoa, val["id_item"])
    exigidos = PAPEL_POR_ETAPA.get(val["etapa"], {"admin"})
    if efetivos & exigidos:
        return True, ""

    # o responsável formal pelo ativo também responde pela etapa dele
    papel_owner = OWNER_POR_ETAPA.get(val["etapa"])
    if papel_owner and quem:
        sou_owner = con.execute(
            "SELECT 1 FROM responsabilidade WHERE id_item = ? AND id_pessoa = ? "
            "AND papel = ? AND fim_vigencia IS NULL",
            (val["id_item"], id_pessoa, papel_owner)).fetchone()
        if sou_owner:
            return True, ""

    nomes = ", ".join(sorted(exigidos - {"admin"})) or "administrador"
    return False, f"A etapa {val['etapa']} exige papel de {nomes}."


def quem_pode_decidir(con, id_validacao: int) -> list[dict]:
    """Pessoas aptas a decidir esta etapa — destinatárias da notificação."""
    val = con.execute("SELECT id_item, etapa FROM validacao WHERE id_validacao = ?",
                      (id_validacao,)).fetchone()
    if val is None:
        return []
    aptas = []
    for p in pessoas_ativas(con):
        ok, _ = pode_decidir(con, p["id_pessoa"], id_validacao)
        if ok:
            aptas.append(p)
    return aptas


# ------------------------------------------------------- pleito de acesso
def validar_cadastro(matricula: str, nome: str, email: str, unidade: str) -> dict:
    """Confere os dados do cadastro e devolve-os normalizados.

    Erro de digitação em matrícula é caro depois: é ela que amarra a pessoa à
    trilha de auditoria, e não há SSO para corrigir a grafia. Por isso a regra é
    conferida aqui, uma vez, e não em cada tela que grava pessoa.
    """
    matricula = (matricula or "").strip().upper()
    nome = (nome or "").strip()
    email = (email or "").strip()
    unidade = (unidade or "").strip()

    if not MATRICULA.match(matricula):
        raise servicos.RegraDeNegocio(
            "Matrícula inválida: uma letra seguida de seis números, como C123456.")
    if len(nome.split()) < 2:
        raise servicos.RegraDeNegocio("Informe o nome completo.")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise servicos.RegraDeNegocio("Informe um e-mail válido.")
    if not UNIDADE.match(unidade):
        raise servicos.RegraDeNegocio(
            "Unidade inválida: o código tem quatro números, como 0427.")
    return {"matricula": matricula, "nome": nome, "email": email, "unidade": unidade}


def quem_concede(con, papel_alvo: str | None = None) -> list[dict]:
    """Pessoas que podem despachar um pleito — destinatárias do aviso."""
    aptas = []
    for p in pessoas_ativas(con):
        ok, _ = pode_conceder(con, p["id_pessoa"], papel_alvo)
        if ok:
            aptas.append(p)
    return aptas


def pode_conceder(con, id_pessoa: int | None,
                  papel_alvo: str | None = None) -> tuple[bool, str]:
    """Quem despacha pleitos, e até onde vai — com o motivo da recusa.

    Curador despacha o dia a dia; só um administrador cria outro administrador.
    Sem esse teto, o poder de administrar a ferramenta se espalharia por
    concessão lateral, sem ninguém ter decidido isso.
    """
    if id_pessoa is None:
        return False, "Sessão sem pessoa identificada."
    efetivos = {p["papel"] for p in papeis(con, id_pessoa)}
    if not efetivos & PERMISSOES["conceder"]:
        return False, "Conceder acesso é atribuição de curador ou administrador."
    if papel_alvo == "admin" and "admin" not in efetivos:
        return False, "Só um administrador concede o papel de administrador."
    return True, ""


def solicitar_acesso(con, matricula: str, nome: str, email: str, unidade: str,
                     papel_pleiteado: str, justificativa: str = "") -> dict:
    """Cadastra a pessoa (se for nova) e registra o pleito de papel.

    O cadastro **não** concede nada: a pessoa nasce sem papel, isto é, com o
    catálogo inteiro em modo de consulta. O papel só existe depois que alguém
    com atribuição para tanto decide — é esse o ponto do rito.
    """
    dados = validar_cadastro(matricula, nome, email, unidade)
    if papel_pleiteado not in PAPEIS:
        raise servicos.RegraDeNegocio(f"papel desconhecido: {papel_pleiteado}")

    linha = con.execute("SELECT * FROM pessoa WHERE matricula = ?",
                        (dados["matricula"],)).fetchone()
    if linha:
        id_pessoa = linha["id_pessoa"]
        con.execute("UPDATE pessoa SET nome = ?, email = ?, unidade = ?, ativo = 1 "
                    "WHERE id_pessoa = ?",
                    (dados["nome"], dados["email"], dados["unidade"], id_pessoa))
        pendente = con.execute(
            "SELECT id_solicitacao FROM solicitacao_acesso "
            "WHERE id_pessoa = ? AND status = 'pendente'", (id_pessoa,)).fetchone()
        if pendente:
            raise servicos.RegraDeNegocio(
                "Já existe um pleito seu aguardando decisão. "
                "Acompanhe em Seu perfil.")
    else:
        cur = con.execute(
            "INSERT INTO pessoa (matricula, nome, email, unidade, perfil, login) "
            "VALUES (?,?,?,?,'consulta',?)",
            (dados["matricula"], dados["nome"], dados["email"], dados["unidade"],
             dados["matricula"].lower()))
        id_pessoa = cur.lastrowid

    cur = con.execute(
        "INSERT INTO solicitacao_acesso (id_pessoa, papel_pleiteado, justificativa) "
        "VALUES (?,?,?)", (id_pessoa, papel_pleiteado, (justificativa or "").strip()))
    id_solicitacao = cur.lastrowid

    notificacoes.para_muitos(
        con, quem_concede(con, papel_pleiteado), "acesso_solicitado",
        f"{dados['nome']} pleiteia o papel de {PAPEIS[papel_pleiteado]}",
        corpo=(f"Matrícula {dados['matricula']} · unidade {dados['unidade']}. "
               + (justificativa or "").strip()),
        url=f"/acessos#pleito-{id_solicitacao}",
        sufixo_chave=f"pleito-{id_solicitacao}")
    con.commit()
    return {"id_pessoa": id_pessoa, "id_solicitacao": id_solicitacao,
            **dados, "papel_pleiteado": papel_pleiteado}


def solicitacao(con, id_solicitacao: int) -> dict | None:
    linha = con.execute(
        "SELECT s.*, p.nome, p.matricula, p.email, p.unidade, p.login "
        "FROM solicitacao_acesso s JOIN pessoa p ON p.id_pessoa = s.id_pessoa "
        "WHERE s.id_solicitacao = ?", (id_solicitacao,)).fetchone()
    return dict(linha) if linha else None


def solicitacoes(con, status: str | None = None,
                 id_pessoa: int | None = None) -> list[dict]:
    """Pleitos, do mais antigo para o mais novo — quem espera há mais tempo primeiro."""
    condicoes, valores = [], []
    if status:
        condicoes.append("s.status = ?")
        valores.append(status)
    if id_pessoa:
        condicoes.append("s.id_pessoa = ?")
        valores.append(id_pessoa)
    onde = ("WHERE " + " AND ".join(condicoes)) if condicoes else ""
    return [dict(l) for l in con.execute(
        "SELECT s.*, p.nome, p.matricula, p.email, p.unidade, p.login "
        f"FROM solicitacao_acesso s JOIN pessoa p ON p.id_pessoa = s.id_pessoa {onde} "
        "ORDER BY s.status = 'pendente' DESC, s.criado_em", valores)]


def decidir_solicitacao(con, id_solicitacao: int, id_decisor: int, aprovar: bool,
                        resposta: str = "", papel_concedido: str | None = None,
                        escopo_tipo: str = "global",
                        escopo_id: int | None = None) -> dict:
    """Concede ou nega o pleito, sempre com resposta a quem pediu.

    O aprovador pode conceder papel diferente do pleiteado — é o caso comum de
    quem pede mais do que precisa. Quando isso acontece, ou quando o pleito é
    negado, a resposta passa a ser obrigatória: a pessoa tem direito de saber
    por que o que ela recebeu não é o que ela pediu.
    """
    pedido = solicitacao(con, id_solicitacao)
    if pedido is None:
        raise servicos.RegraDeNegocio("Pleito não encontrado.")
    if pedido["status"] != "pendente":
        raise servicos.RegraDeNegocio(
            f"Este pleito já foi {pedido['status']} em {pedido['decidido_em']}.")
    if pedido["id_pessoa"] == id_decisor:
        raise servicos.RegraDeNegocio(
            "Segregação de função: ninguém concede acesso a si mesmo.")

    papel = (papel_concedido or pedido["papel_pleiteado"]) if aprovar else None
    ok, motivo = pode_conceder(con, id_decisor, papel)
    if not ok:
        raise SemPermissao(motivo)

    resposta = (resposta or "").strip()
    if not aprovar and not resposta:
        raise servicos.RegraDeNegocio("Negar um pleito exige dizer por quê.")
    if aprovar and papel != pedido["papel_pleiteado"] and not resposta:
        raise servicos.RegraDeNegocio(
            "Conceder papel diferente do pleiteado exige explicar a troca.")

    decisor = pessoa(con, id_decisor) or {}
    assinatura = decisor.get("login") or decisor.get("nome") or "desconhecido"

    if aprovar:
        conceder(con, pedido["id_pessoa"], papel, escopo_tipo, escopo_id,
                 assinatura, commit=False)
        con.execute("UPDATE pessoa SET perfil = ? WHERE id_pessoa = ?",
                    (papel, pedido["id_pessoa"]))

    con.execute(
        "UPDATE solicitacao_acesso SET status = ?, decidido_por = ?, "
        "decidido_em = datetime('now'), papel_concedido = ?, escopo_tipo = ?, "
        "escopo_id = ?, resposta = ? WHERE id_solicitacao = ?",
        ("aprovada" if aprovar else "negada", assinatura, papel,
         escopo_tipo if aprovar else None, escopo_id if aprovar else None,
         resposta, id_solicitacao))

    titulo = (f"Acesso concedido: {PAPEIS[papel]}" if aprovar
              else "Seu pleito de acesso foi negado")
    notificacoes.registrar(
        con, pedido["id_pessoa"], "acesso_decidido", titulo,
        corpo=resposta or f"Pleito de {PAPEIS[pedido['papel_pleiteado']]} aprovado.",
        url="/perfil", chave_unica=f"pleito-decidido-{id_solicitacao}")
    con.commit()
    return solicitacao(con, id_solicitacao)


def rotulo_escopo(con, escopo_tipo: str | None, escopo_id: int | None) -> str:
    """"dominio #1" não diz nada a quem lê; o nome do domínio, sim."""
    if not escopo_tipo or escopo_tipo == "global":
        return "todo o catálogo"
    if escopo_tipo == "dominio" and escopo_id:
        linha = con.execute("SELECT nome FROM item_catalogo WHERE id_item = ?",
                            (escopo_id,)).fetchone()
        return f"domínio {linha['nome']}" if linha else f"domínio #{escopo_id}"
    if escopo_tipo == "squad" and escopo_id:
        linha = con.execute("SELECT nome FROM squad WHERE id_squad = ?",
                            (escopo_id,)).fetchone()
        return f"squad {linha['nome']}" if linha else f"squad #{escopo_id}"
    return escopo_tipo
