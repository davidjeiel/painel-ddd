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

from . import servicos

# Papéis, do mais amplo ao mais restrito.
PAPEIS = {
    "admin": "Administrador do catálogo",
    "curador": "Curador (cadastra e submete)",
    "arquiteto": "Arquiteto",
    "tech_lead": "Tech lead",
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
    "administrar": {"admin"},
}

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


# -------------------------------------------------------------------- papéis
def conceder(con, id_pessoa: int, papel: str, escopo_tipo: str = "global",
             escopo_id: int | None = None, concedido_por: str = "sistema") -> int:
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


def pode(con, id_pessoa: int | None, acao: str, id_item: int | None = None) -> bool:
    """Ponto único de decisão de autorização."""
    if id_pessoa is None:
        return False
    permitidos = PERMISSOES.get(acao)
    if permitidos is None:
        raise servicos.RegraDeNegocio(f"ação desconhecida: {acao}")
    return bool(papeis_efetivos(con, id_pessoa, id_item) & permitidos)


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
