"""Telas nucleares: catálogo, wizard, visão 360° e central de validações."""
from __future__ import annotations

import json

from functools import wraps

from flask import (Blueprint, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)

from . import (acesso, cartilha as guia, governanca, integracoes, notificacoes,
               servicos, tipos)
from .db import ErroIntegridade, get_db

bp = Blueprint("web", __name__)

# Seção do menu a que cada tela pertence. O destaque do menu passa a ser por
# família de rota: entrar num ativo não apaga mais o "você está aqui".
SECOES = {
    "web.dashboard": "painel",
    "web.catalogo": "catalogo",
    "web.detalhe": "catalogo",
    "web.editar": "catalogo",
    "web.responsavel": "catalogo",
    "web.relacao": "catalogo",
    "web.evidencia": "catalogo",
    "web.submeter": "catalogo",
    "web.revisar": "catalogo",
    "web.descontinuar": "catalogo",
    "web.comparar": "catalogo",
    "web.relacoes_lote": "catalogo",
    "web.grafo": "catalogo",
    "web.mapa": "mapa",
    "web.perfil": "perfil",
    "web.caixa_notificacoes": "notificacoes",
    "web.preferencias_notificacao": "notificacoes",
    "web.novo_ativo": "novo",
    "web.descobertas": "descobertas",
    "web.triagem": "descobertas",
    "web.meu_trabalho": "mesa",
    "web.validacoes": "validacoes",
    "web.decidir": "validacoes",
    "web.assumir": "validacoes",
    "web.liberar": "validacoes",
    "web.politicas": "politicas",
    "web.cartilha": "cartilha",
    "web.acessos": "acessos",
    "web.decidir_acesso": "acessos",
    "web.squads": "squads",
    "web.gestao_acessos": "acessos",
    "web.editar_pessoa": "acessos",
    "web.inativar_pessoa": "acessos",
    "web.excluir_pessoa": "acessos",
    "web.solicitar_acesso": "perfil",
}

# Abas da visão 360°: leitura de um lado, escrita dentro da aba a que pertence.
ABAS_ATIVO = [("resumo", "Resumo"), ("relacoes", "Relações"), ("pessoas", "Pessoas"),
              ("evidencias", "Evidências"), ("historico", "Histórico")]

# Filtros do catálogo, com o rótulo usado nos chips de filtro ativo.
FILTROS_CATALOGO = {
    "termo": "Busca",
    "tipo_item": "Tipo",
    "status": "Status",
    "id_squad": "Squad",
    "criticidade": "Criticidade",
    "sem_owner": "Sem responsável",
    "origem": "Origem do cadastro",
}
POR_PAGINA = 50
POR_PAGINA_GESTAO = 20


def pessoa_atual() -> dict | None:
    """A pessoa da sessão. Hoje escolhida em /perfil; amanhã, vinda do SSO.

    A decisão 12.1-a troca apenas a origem deste valor — papéis, escopos e as
    regras de autorização não mudam.
    """
    id_pessoa = session.get("id_pessoa")
    if not id_pessoa:
        return None
    return acesso.pessoa(get_db(), id_pessoa)


def usuario_atual() -> str:
    """Identificador gravado na trilha de auditoria."""
    quem = pessoa_atual()
    if quem:
        return quem.get("login") or quem["matricula"]
    return session.get("usuario", "curador.demo")


def modo_leitura() -> bool:
    return session.get("modo", "edicao") == "leitura"


def pode(acao: str, id_item: int | None = None, tipo_item: str | None = None) -> bool:
    """Autorização para uso nos templates: esconde o que a pessoa não pode fazer."""
    if modo_leitura():
        return False
    quem = pessoa_atual()
    if quem is None:
        return False
    return acesso.pode(get_db(), quem["id_pessoa"], acao, id_item, tipo_item)


def exige(acao: str):
    """Autorização na rota. Esconder o botão não é autorização: a rota recusa.

    O escopo sai do próprio alvo — quando a view recebe `id_item`, o papel é
    resolvido no domínio daquele ativo.
    """
    def decorador(vista):
        @wraps(vista)
        def envolvida(*args, **kwargs):
            quem = pessoa_atual()
            id_item = kwargs.get("id_item")
            if quem is None:
                flash("Escolha quem é você antes de agir no catálogo.", "erro")
                return redirect(url_for("web.perfil", destino=request.referrer or "/"))
            if modo_leitura():
                flash("Você está em modo de leitura. Troque no seu perfil para editar.",
                      "erro")
                return redirect(request.referrer or url_for("web.dashboard"))
            if not acesso.pode(get_db(), quem["id_pessoa"], acao, id_item):
                raise acesso.SemPermissao(
                    f"Seu papel não permite {acao} neste ativo.")
            return vista(*args, **kwargs)
        return envolvida
    return decorador


@bp.app_errorhandler(acesso.SemPermissao)
def sem_permissao(exc):
    flash(str(exc), "erro")
    return redirect(request.referrer or url_for("web.dashboard")), 303


def secao_atual() -> str:
    return SECOES.get(request.endpoint or "", "")


@bp.app_template_filter("rotulo_tipo")
def rotulo_tipo(chave):
    return tipos.TIPOS[chave].rotulo if chave in tipos.TIPOS else chave


@bp.app_template_filter("rotulo_status")
def rotulo_status(chave):
    return tipos.CICLO_VIDA.get(chave, chave)


@bp.app_template_filter("sla")
def filtro_sla(prazo):
    return governanca.sla_restante(prazo)


@bp.app_template_filter("numero")
def filtro_numero(valor):
    """9.0 vira '9'; 8.5 vira '8,5' — separador decimal em português."""
    if valor is None:
        return "—"
    if float(valor) == int(valor):
        return str(int(valor))
    return f"{float(valor):.1f}".replace(".", ",")


@bp.app_context_processor
def contexto():
    quem = pessoa_atual()
    return {"TIPOS": tipos.TIPOS, "CICLO": tipos.CICLO_VIDA,
            "CRITICIDADES": tipos.CRITICIDADES, "usuario": usuario_atual(),
            "secao": secao_atual(), "pessoa": quem, "leitura": modo_leitura(),
            "pode": pode,
            "nao_lidas": notificacoes.nao_lidas(get_db(), quem["id_pessoa"])
                         if quem else 0}


# ------------------------------------------------------------------ dashboard
@bp.route("/")
def dashboard():
    con = get_db()
    id_dominio = request.args.get("id_dominio", type=int)
    id_subdominio = request.args.get("id_subdominio", type=int)
    id_item = request.args.get("id_item", type=int)
    dominios = [dict(l) for l in con.execute(
        "SELECT id_item, nome FROM item_catalogo WHERE tipo_item = 'dominio' "
        "ORDER BY nome")]
    if id_dominio:
        subdominios = [dict(l) for l in con.execute(
            "SELECT id_item, nome, id_pai FROM item_catalogo "
            "WHERE tipo_item = 'subdominio' AND id_pai = ? ORDER BY nome",
            (id_dominio,))]
    else:
        subdominios = [dict(l) for l in con.execute(
            "SELECT id_item, nome, id_pai FROM item_catalogo "
            "WHERE tipo_item = 'subdominio' ORDER BY nome")]
    return render_template(
        "dashboard.html",
        kpis=servicos.indicadores(con),
        grafo_catalogo=servicos.grafo_catalogo(con, id_dominio, id_subdominio, id_item),
        dominios_grafo=dominios, subdominios_grafo=subdominios,
        filtro_dominio=id_dominio, filtro_subdominio=id_subdominio,
        variacao=servicos.variacao_indicadores(con),
        cobertura=servicos.cobertura_por_dominio(con),
        pendencias=servicos.pendencias_prioritarias(con),
        serie=servicos.serie_historica(con, "cobertura"),
        serie_qualidade=servicos.serie_historica(con, "qualidade_media"),
        fila=governanca.fila_validacao(con)[:5],
    )


# ------------------------------------------------------------------- perfil
def _com_escopo(con, pleitos: list[dict]) -> list[dict]:
    for p in pleitos:
        p["escopo_rotulo"] = acesso.rotulo_escopo(con, p["escopo_tipo"], p["escopo_id"])
    return pleitos


def _papeis_legiveis(con, quem: dict | None) -> list[dict]:
    if not quem:
        return []
    linhas = acesso.papeis(con, quem["id_pessoa"])
    for p in linhas:
        p["escopo_rotulo"] = acesso.rotulo_escopo(con, p["escopo_tipo"], p["escopo_id"])
        p["blocos"] = sorted(acesso.BLOCOS_POR_PAPEL.get(p["papel"], ()))
    return linhas


@bp.route("/perfil", methods=["GET", "POST"])
def perfil():
    """Quem é você e em que modo trabalha.

    Enquanto a fonte de identidade não é decidida, a pessoa é escolhida aqui.
    Quando o SSO entrar, esta tela perde o seletor e mantém o resto.
    """
    con = get_db()
    if request.method == "POST":
        id_pessoa = request.form.get("id_pessoa", type=int)
        if id_pessoa and acesso.pessoa(con, id_pessoa):
            session["id_pessoa"] = id_pessoa
        elif request.form.get("id_pessoa") == "":
            session.pop("id_pessoa", None)
        session["modo"] = ("leitura" if request.form.get("modo") == "leitura"
                           else "edicao")
        flash("Perfil atualizado.", "ok")
        destino = request.form.get("destino") or url_for("web.perfil")
        return redirect(destino)

    quem = pessoa_atual()
    return render_template(
        "perfil.html", pessoas=acesso.pessoas_ativas(con),
        papeis=acesso.papeis(con, quem["id_pessoa"]) if quem else [],
        meus_pleitos=_com_escopo(con, acesso.solicitacoes(
            con, id_pessoa=quem["id_pessoa"]) if quem else []),
        papeis_com_escopo=_papeis_legiveis(con, quem),
        catalogo_papeis=acesso.PAPEIS, permissoes=acesso.PERMISSOES,
        etapas=acesso.PAPEL_POR_ETAPA, blocos_por_papel=acesso.BLOCOS_POR_PAPEL,
        destino=request.args.get("destino", ""))


# --------------------------------------------------------- pleito de acesso
@bp.route("/acesso/solicitar", methods=["GET", "POST"])
def solicitar_acesso():
    """Cadastro e pleito de papel — a única tela de escrita aberta a quem não tem papel.

    Tem de ser aberta: é justamente quem ainda não foi autorizado que precisa
    dela. O que ela grava não autoriza nada — cria a pessoa e um pedido.
    """
    con = get_db()
    if request.method == "POST":
        try:
            pleito = acesso.solicitar_acesso(
                con,
                matricula=request.form.get("matricula", ""),
                nome=request.form.get("nome", ""),
                email=request.form.get("email", ""),
                unidade=request.form.get("unidade", ""),
                papel_pleiteado=request.form.get("papel_pleiteado", ""),
                justificativa=request.form.get("justificativa", ""))
        except servicos.RegraDeNegocio as erro:
            flash(str(erro), "erro")
        else:
            # quem acabou de se cadastrar já passa a ser quem ele disse que é:
            # consulta liberada na hora, escrita só quando o papel sair
            session["id_pessoa"] = pleito["id_pessoa"]
            session["modo"] = "edicao"
            flash("Cadastro registrado e pleito enviado. Até a decisão sair, você "
                  "consulta o catálogo inteiro.", "ok")
            return redirect(url_for("web.perfil"))

    return render_template("solicitar_acesso.html", papeis=acesso.PAPEIS,
                           blocos_por_papel=acesso.BLOCOS_POR_PAPEL,
                           permissoes=acesso.PERMISSOES, form=request.form)


@bp.route("/acessos")
@exige("conceder")
def acessos():
    """Fila de pleitos — quem espera há mais tempo primeiro."""
    con = get_db()
    quem = pessoa_atual()
    pleitos = acesso.solicitacoes(con, status=request.args.get("status") or None)
    for p in pleitos:
        p["escopo_rotulo"] = acesso.rotulo_escopo(con, p["escopo_tipo"], p["escopo_id"])
    dominios = [dict(l) for l in con.execute(
        "SELECT id_item, codigo, nome FROM item_catalogo WHERE tipo_item = 'dominio' "
        "ORDER BY nome")]
    squads = [dict(l) for l in con.execute("SELECT * FROM squad ORDER BY nome")]
    return render_template(
        "acessos.html", pleitos=pleitos, papeis=acesso.PAPEIS,
        dominios=dominios, squads=squads,
        pode_admin=acesso.pode_conceder(con, quem["id_pessoa"], "admin")[0],
        filtro=request.args.get("status", ""),
        pendentes=sum(1 for p in pleitos if p["status"] == "pendente"))


@bp.route("/acessos/<int:id_solicitacao>/decidir", methods=["POST"])
@exige("conceder")
def decidir_acesso(id_solicitacao: int):
    con = get_db()
    quem = pessoa_atual()
    try:
        pleito = acesso.decidir_solicitacao(
            con, id_solicitacao, quem["id_pessoa"],
            aprovar=request.form.get("decisao") == "aprovar",
            resposta=request.form.get("resposta", ""),
            papel_concedido=request.form.get("papel_concedido") or None,
            escopo_tipo=request.form.get("escopo_tipo", "global"),
            escopo_id=request.form.get("escopo_id", type=int))
    except servicos.RegraDeNegocio as erro:
        flash(str(erro), "erro")
    else:
        if pleito["status"] == "aprovada":
            flash(f"{pleito['nome']} agora é {acesso.PAPEIS[pleito['papel_concedido']]}"
                  f" ({pleito['escopo_tipo']}).", "ok")
        else:
            flash(f"Pleito de {pleito['nome']} negado, com a resposta registrada.", "ok")
    return redirect(url_for("web.acessos"))


# --------------------------------------------------------- gestão de acessos
@bp.route("/gestao-acessos", methods=["GET", "POST"])
@exige("administrar")
def gestao_acessos():
    con = get_db()
    termo = request.args.get("busca", "").strip()
    pessoas = acesso.pessoas(con, termo)
    for pessoa_cadastrada in pessoas:
        pessoa_cadastrada["interacoes"] = acesso.interacoes_pessoa(
            con, pessoa_cadastrada["id_pessoa"])
    total = len(pessoas)
    paginas = max(1, -(-total // POR_PAGINA_GESTAO))
    pagina_atual = min(max(1, request.args.get("pagina", 1, type=int)), paginas)
    inicio = (pagina_atual - 1) * POR_PAGINA_GESTAO
    detalhe_id = request.args.get("detalhe", type=int)
    detalhe = next((p for p in pessoas if p["id_pessoa"] == detalhe_id), None)
    quem = pessoa_atual()
    return render_template(
        "gestao_acessos.html", pessoas=pessoas[inicio:inicio + POR_PAGINA_GESTAO],
        detalhe=detalhe, pagina=pagina_atual, paginas=paginas, total=total,
        por_pagina=POR_PAGINA_GESTAO,
        busca=termo,
        pessoa_atual_id=quem["id_pessoa"] if quem else None,
        papeis=acesso.PAPEIS,
        squads=[dict(l) for l in con.execute(
            "SELECT * FROM squad WHERE ativo = 1 ORDER BY nome")])


@bp.route("/gestao-acessos/inativar-lote", methods=["POST"])
@exige("administrar")
def inativar_pessoas_lote():
    con = get_db()
    ids = {int(valor) for valor in request.form.getlist("id_pessoa")
           if valor.isdigit()}
    quem = pessoa_atual()
    if quem:
        ids.discard(quem["id_pessoa"])
    for id_pessoa in ids:
        try:
            acesso.inativar_pessoa(con, id_pessoa)
        except servicos.RegraDeNegocio:
            continue
    flash(f"{len(ids)} cadastro(s) inativado(s).", "ok")
    return redirect(url_for("web.gestao_acessos"))


@bp.route("/gestao-acessos/<int:id_pessoa>/editar", methods=["POST"])
@exige("administrar")
def editar_pessoa(id_pessoa: int):
    con = get_db()
    try:
        acesso.atualizar_pessoa(
            con, id_pessoa, request.form.get("nome", ""),
            request.form.get("email", ""), request.form.get("unidade", ""),
            request.form.get("id_squad", type=int),
            request.form.get("papel", "consulta"),
            request.form.get("ativo") == "1", usuario_atual())
    except servicos.RegraDeNegocio as erro:
        flash(str(erro), "erro")
    else:
        flash("Cadastro atualizado.", "ok")
    return redirect(url_for("web.gestao_acessos"))


@bp.route("/gestao-acessos/<int:id_pessoa>/inativar", methods=["POST"])
@exige("administrar")
def inativar_pessoa(id_pessoa: int):
    quem = pessoa_atual()
    if quem and quem["id_pessoa"] == id_pessoa:
        flash("O administrador conectado não pode inativar o próprio cadastro.", "erro")
        return redirect(url_for("web.gestao_acessos"))
    try:
        acesso.inativar_pessoa(get_db(), id_pessoa)
    except servicos.RegraDeNegocio as erro:
        flash(str(erro), "erro")
    else:
        flash("Cadastro inativado e acessos encerrados.", "ok")
    return redirect(url_for("web.gestao_acessos"))


@bp.route("/gestao-acessos/<int:id_pessoa>/excluir", methods=["POST"])
@exige("administrar")
def excluir_pessoa(id_pessoa: int):
    if pessoa_atual() and pessoa_atual()["id_pessoa"] == id_pessoa:
        flash("O administrador conectado não pode excluir o próprio cadastro.", "erro")
        return redirect(url_for("web.gestao_acessos"))
    try:
        acesso.excluir_pessoa(get_db(), id_pessoa)
    except servicos.RegraDeNegocio as erro:
        flash(str(erro), "erro")
    else:
        flash("Cadastro excluído.", "ok")
    return redirect(url_for("web.gestao_acessos"))


# --------------------------------------------------------------------- squads
@bp.route("/squads", methods=["GET", "POST"])
@exige("conceder")
def squads():
    con = get_db()
    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        sigla = request.form.get("sigla", "").strip().upper()
        descricao = request.form.get("descricao", "").strip()
        if not titulo or not sigla or not descricao:
            flash("Título, sigla e descrição são obrigatórios.", "erro")
        elif len(sigla) > 20:
            flash("A sigla deve ter no máximo 20 caracteres.", "erro")
        else:
            try:
                con.execute(
                    "INSERT INTO squad (nome, codigo, descricao) VALUES (?, ?, ?)",
                    (titulo, sigla, descricao))
                con.commit()
            except ErroIntegridade:
                flash("Já existe uma squad com essa sigla.", "erro")
            else:
                flash("Squad cadastrada.", "ok")
                return redirect(url_for("web.squads"))

    busca = request.args.get("busca", "").strip()
    sql = "SELECT * FROM squad"
    params = []
    if busca:
        sql += (" WHERE LOWER(COALESCE(nome, '')) LIKE LOWER(?)"
                " OR LOWER(COALESCE(codigo, '')) LIKE LOWER(?)"
                " OR LOWER(COALESCE(descricao, '')) LIKE LOWER(?)")
        params = [f"%{busca}%"] * 3
    sql += " ORDER BY ativo DESC, nome"
    todas = [dict(l) for l in con.execute(sql, params)]
    total = len(todas)
    paginas = max(1, -(-total // POR_PAGINA_GESTAO))
    pagina = min(max(1, request.args.get("pagina", 1, type=int)), paginas)
    inicio = (pagina - 1) * POR_PAGINA_GESTAO
    detalhe_id = request.args.get("detalhe", type=int)
    detalhe = next((s for s in todas if s["id_squad"] == detalhe_id), None)
    return render_template(
        "squads.html", squads=todas[inicio:inicio + POR_PAGINA_GESTAO],
        detalhe=detalhe, busca=busca, pagina=pagina, paginas=paginas,
        total=total, por_pagina=POR_PAGINA_GESTAO, form=request.form)


@bp.route("/squads/<int:id_squad>/editar", methods=["POST"])
@exige("conceder")
def editar_squad(id_squad: int):
    titulo = request.form.get("titulo", "").strip()
    sigla = request.form.get("sigla", "").strip().upper()
    descricao = request.form.get("descricao", "").strip()
    if not titulo or not sigla or not descricao:
        flash("Título, sigla e descrição são obrigatórios.", "erro")
    elif len(sigla) > 20:
        flash("A sigla deve ter no máximo 20 caracteres.", "erro")
    else:
        try:
            con = get_db()
            con.execute("UPDATE squad SET nome = ?, codigo = ?, descricao = ? "
                        "WHERE id_squad = ?",
                        (titulo, sigla, descricao, id_squad))
            con.commit()
        except ErroIntegridade:
            flash("Já existe uma squad com essa sigla.", "erro")
        else:
            flash("Squad atualizada.", "ok")
    return redirect(url_for("web.squads", detalhe=id_squad))


@bp.route("/squads/<int:id_squad>/inativar", methods=["POST"])
@exige("conceder")
def inativar_squad(id_squad: int):
    con = get_db()
    con.execute("UPDATE squad SET ativo = 0 WHERE id_squad = ?", (id_squad,))
    con.commit()
    flash("Squad inativada. Os vínculos existentes foram preservados.", "ok")
    return redirect(url_for("web.squads"))


# ------------------------------------------------------------- notificações
@bp.route("/notificacoes")
def caixa_notificacoes():
    quem = pessoa_atual()
    if quem is None:
        flash("Escolha quem é você para ver suas notificações.", "erro")
        return redirect(url_for("web.perfil"))
    con = get_db()
    return render_template("notificacoes.html",
                           itens=notificacoes.caixa(con, quem["id_pessoa"]),
                           tipos=notificacoes.TIPOS)


@bp.route("/notificacoes/<int:id_notificacao>/abrir")
def abrir_notificacao(id_notificacao: int):
    quem = pessoa_atual()
    if quem is None:
        return redirect(url_for("web.perfil"))
    con = get_db()
    linha = con.execute("SELECT url FROM notificacao WHERE id_notificacao = ? "
                        "AND id_pessoa = ?",
                        (id_notificacao, quem["id_pessoa"])).fetchone()
    notificacoes.marcar_lida(con, id_notificacao, quem["id_pessoa"])
    return redirect(linha["url"] if linha and linha["url"]
                    else url_for("web.caixa_notificacoes"))


@bp.route("/notificacoes/lidas", methods=["POST"])
def marcar_lidas():
    quem = pessoa_atual()
    if quem is None:
        return redirect(url_for("web.perfil"))
    total = notificacoes.marcar_todas_lidas(get_db(), quem["id_pessoa"])
    flash(f"{total} notificação(ões) marcada(s) como lida(s).", "ok")
    return redirect(url_for("web.caixa_notificacoes"))


@bp.route("/notificacoes/preferencias", methods=["GET", "POST"])
def preferencias_notificacao():
    quem = pessoa_atual()
    if quem is None:
        flash("Escolha quem é você para ajustar as preferências.", "erro")
        return redirect(url_for("web.perfil"))
    con = get_db()
    if request.method == "POST":
        ativas = {tuple(v.split(":", 1)) for v in request.form.getlist("pref")
                  if ":" in v}
        notificacoes.salvar_preferencias(con, quem["id_pessoa"], ativas)
        flash("Preferências salvas.", "ok")
        return redirect(url_for("web.preferencias_notificacao"))
    return render_template("preferencias.html",
                           preferencias=notificacoes.preferencias(con, quem["id_pessoa"]),
                           tipos=notificacoes.TIPOS, canais=notificacoes.CANAIS,
                           disponiveis=notificacoes.CANAIS_DISPONIVEIS)


# ------------------------------------------------------------------- grafo
@bp.route("/ativo/<int:id_item>/grafo")
def grafo(id_item: int):
    con = get_db()
    item = con.execute(
        "SELECT id_item, codigo, nome, tipo_item FROM item_catalogo "
        "WHERE id_item = ?", (id_item,)).fetchone()
    if item is None:
        abort(404)
    escolhidos = tuple(t for t in request.args.getlist("tipo") if t in tipos.RELACOES)
    dados = servicos.posicionar_vizinhanca(servicos.vizinhanca(
        con, id_item, saltos=request.args.get("saltos", 1, type=int),
        tipos_relacao=escolhidos))
    return render_template("grafo.html", item=dict(item), dados=dados,
                           trilha=servicos.trilha(con, id_item),
                           relacoes=tipos.RELACOES, escolhidos=escolhidos,
                           analise=servicos.analise_impacto(con, id_item))


# ---------------------------------------------------------------- busca global
@bp.route("/busca/sugestoes")
def sugestoes():
    """Resultados instantâneos para a busca do cabeçalho."""
    termo = request.args.get("termo", "").strip()
    if len(termo) < 2:
        return jsonify({"termo": termo, "itens": []})
    achados = servicos.buscar(get_db(), termo=termo, limite=8)
    return jsonify({"termo": termo, "itens": [
        {"id_item": i["id_item"], "nome": i["nome"], "codigo": i["codigo"],
         "tipo": rotulo_tipo(i["tipo_item"]),
         "status": rotulo_status(i["status_ciclo_vida"]),
         "url": url_for("web.detalhe", id_item=i["id_item"])}
        for i in achados]})


# -------------------------------------------------------------------- catálogo
def _filtros_do_pedido() -> dict:
    """Filtros da requisição, ou os últimos usados quando não veio nenhum.

    Sem argumentos na URL a tela retoma o recorte anterior — era a promessa de
    "filtros persistentes por sessão" que a sessão guardava e ninguém lia.
    """
    if request.args.get("limpar"):
        session.pop("filtros_catalogo", None)
        return {chave: "" for chave in FILTROS_CATALOGO}
    if not request.args:
        guardados = session.get("filtros_catalogo") or {}
        return {chave: str(guardados.get(chave, "")) for chave in FILTROS_CATALOGO}
    return {chave: request.args.get(chave, "").strip() for chave in FILTROS_CATALOGO}


def _chips(filtros: dict, squads: list[dict]) -> list[dict]:
    """Filtros ativos como etiquetas removíveis, cada uma com a URL sem ela."""
    nomes_squad = {str(s["id_squad"]): s["nome"] for s in squads}
    chips = []
    for chave, valor in filtros.items():
        if not valor:
            continue
        if chave == "tipo_item":
            legivel = rotulo_tipo(valor)
        elif chave == "status":
            legivel = rotulo_status(valor)
        elif chave == "id_squad":
            legivel = nomes_squad.get(str(valor), valor)
        elif chave == "sem_owner":
            legivel = "sim"
        elif chave == "origem":
            legivel = "descoberta automática" if valor == "automatica" else "manual"
        else:
            legivel = valor
        restante = {k: v for k, v in filtros.items() if v and k != chave}
        chips.append({"chave": chave, "rotulo": FILTROS_CATALOGO[chave],
                      "valor": legivel,
                      "url": url_for("web.catalogo", **restante) if restante
                             else url_for("web.catalogo", limpar=1)})
    return chips


@bp.route("/catalogo")
def catalogo():
    con = get_db()
    filtros = _filtros_do_pedido()
    session["filtros_catalogo"] = filtros  # filtros persistentes
    ordenar = request.args.get("ordenar", servicos.ORDEM_PADRAO)
    if ordenar not in servicos.ORDENACOES:
        ordenar = servicos.ORDEM_PADRAO
    descendente = request.args.get("desc") == "1"
    pagina = servicos.buscar_pagina(
        con, pagina=request.args.get("pagina", 1, type=int), por_pagina=POR_PAGINA,
        ordenar=ordenar, descendente=descendente, **filtros)
    squads = [dict(l) for l in con.execute("SELECT * FROM squad ORDER BY nome")]
    return render_template("catalogo.html", itens=pagina["itens"], pagina=pagina,
                           filtros=filtros, squads=squads,
                           ordenar=ordenar, descendente=descendente,
                           chips=_chips(filtros, squads))


@bp.route("/mapa")
def mapa():
    con = get_db()
    visao = request.args.get("visao", "negocio")
    if visao not in ("negocio", "tecnica"):
        visao = "negocio"
    return render_template(
        "mapa.html", visao=visao,
        arvore=servicos.arvore(con, "dominio" if visao == "negocio" else "sistema"),
        totais={"negocio": con.execute(
                    "SELECT COUNT(*) FROM item_catalogo WHERE tipo_item = 'dominio'"
                    " AND status_ciclo_vida <> 'arquivado'").fetchone()[0],
                "tecnica": con.execute(
                    "SELECT COUNT(*) FROM item_catalogo WHERE tipo_item = 'sistema'"
                    " AND status_ciclo_vida <> 'arquivado'").fetchone()[0]})


# ------------------------------------------------------------------ descobertas
@bp.route("/descobertas", methods=["GET", "POST"])
def descobertas():
    con = get_db()
    fonte = request.values.get("fonte", "openapi")
    if fonte not in integracoes.FONTES:
        fonte = "openapi"
    conteudo = request.form.get("conteudo", "")
    id_pai = request.form.get("id_pai", type=int)
    plano = None

    if request.method == "POST" and conteudo.strip():
        acao = request.form.get("acao", "previa")
        if acao == "importar" and not pode("importar"):
            raise acesso.SemPermissao("Seu papel não permite importar descobertas.")
        try:
            if acao == "importar":
                resultado = integracoes.FONTES[fonte]["importar"](
                    con, id_aplicacao=id_pai, usuario=usuario_atual(),
                    conteudo=conteudo)
                flash(f"Importação concluída: {resultado}. Os itens entraram na "
                      "bandeja abaixo como rascunho.", "ok")
                return redirect(url_for("web.descobertas", fonte=fonte))
            plano = integracoes.FONTES[fonte]["plano"](
                con, id_aplicacao=id_pai, conteudo=conteudo)
        except (ValueError, KeyError, TypeError) as erro:
            flash(f"Não consegui ler esse conteúdo: {erro}", "erro")
        except servicos.RegraDeNegocio as erro:
            flash(str(erro), "erro")
    elif request.method == "POST":
        flash("Cole o conteúdo JSON antes de gerar a prévia.", "erro")

    aplicacoes = [dict(l) for l in con.execute(
        "SELECT id_item, codigo, nome FROM item_catalogo WHERE tipo_item = 'aplicacao'"
        " AND status_ciclo_vida NOT IN ('descontinuado','arquivado') ORDER BY nome")]
    return render_template("descobertas.html", fontes=integracoes.FONTES, fonte=fonte,
                           plano=plano, conteudo=conteudo, id_pai=id_pai,
                           aplicacoes=aplicacoes,
                           bandeja=servicos.descobertas(con))


@bp.route("/descobertas/triagem", methods=["POST"])
@exige("triar")
def triagem():
    ids = [int(i) for i in request.form.getlist("id_item") if i.isdigit()]
    if not ids:
        flash("Escolha ao menos um item da bandeja.", "erro")
        return redirect(url_for("web.descobertas"))
    try:
        resultado = servicos.triar(get_db(), ids, request.form.get("acao", ""),
                                   usuario_atual())
    except servicos.RegraDeNegocio as erro:
        flash(str(erro), "erro")
        return redirect(url_for("web.descobertas"))
    verbo = "aceito(s)" if resultado["acao"] == "aceitar" else "descartado(s)"
    flash(f"{resultado['tratados']} item(ns) {verbo}.", "ok")
    return redirect(url_for("web.descobertas"))


# ---------------------------------------------------------------------- wizard
@bp.route("/ativo/novo", methods=["GET", "POST"])
def novo_ativo():
    con = get_db()
    tipo_item = request.values.get("tipo_item", "")
    if request.method == "POST" and request.form.get("acao") == "salvar":
        if not pode("cadastrar", tipo_item=tipo_item):
            bloco = tipos.TIPOS[tipo_item].bloco if tipo_item in tipos.TIPOS else ""
            raise acesso.SemPermissao(
                f"Seu papel não permite cadastrar ativos do bloco {bloco}."
                if bloco else "Seu papel não permite cadastrar ativos.")
        t = tipos.tipo(tipo_item)
        atributos = {c.nome: request.form.get(f"attr_{c.nome}", "").strip()
                     for c in t.campos}
        try:
            id_item = servicos.criar_item(
                con,
                tipo_item=tipo_item,
                nome=request.form["nome"],
                descricao=request.form.get("descricao", ""),
                id_pai=int(request.form["id_pai"]) if request.form.get("id_pai") else None,
                id_squad=int(request.form["id_squad"]) if request.form.get("id_squad") else None,
                criticidade=request.form.get("criticidade", "media"),
                atributos=atributos,
                usuario=usuario_atual(),
            )
        except servicos.RegraDeNegocio as erro:
            flash(str(erro), "erro")
        else:
            flash("Rascunho criado. Complete responsáveis, relações e evidências.", "ok")
            return redirect(url_for("web.detalhe", id_item=id_item))

    pais = []
    if tipo_item and tipos.TIPOS.get(tipo_item) and tipos.tipo(tipo_item).pai:
        pais = [dict(l) for l in con.execute(
            "SELECT id_item, codigo, nome FROM item_catalogo WHERE tipo_item = ? "
            "AND status_ciclo_vida NOT IN ('descontinuado','arquivado') ORDER BY nome",
            (tipos.tipo(tipo_item).pai,))]
    squads = [dict(l) for l in con.execute("SELECT * FROM squad ORDER BY nome")]
    # o rito do tipo escolhido já é conhecido antes de salvar: mostrar agora
    # evita a descoberta dos requisitos um erro de cada vez
    politica = (governanca.politica(con, tipo_item,
                                    request.values.get("criticidade", "media"))
                if tipo_item in tipos.TIPOS else None)
    # o wizard só oferece o que o papel escreve: oferecer e recusar depois seria
    # fazer a pessoa preencher um formulário para descobrir que não podia
    quem = pessoa_atual()
    meus_blocos = acesso.blocos_que_escreve(con, quem["id_pessoa"]) if quem else set()
    blocos = {b: lista for b, lista in tipos.blocos().items() if b in meus_blocos}
    return render_template("wizard.html", tipo_item=tipo_item, pais=pais,
                           squads=squads, blocos=blocos, politica=politica,
                           form=request.form, valores=request.values,
                           blocos_todos=tipos.blocos())


# ------------------------------------------------------------------- visão 360
@bp.route("/ativo/<int:id_item>")
def detalhe(id_item: int):
    con = get_db()
    dados = servicos.visao_360(con, id_item)
    pessoas = [dict(l) for l in con.execute(
        "SELECT id_pessoa, nome, perfil FROM pessoa WHERE ativo = 1 ORDER BY nome")]
    candidatos = [{**dict(l), "tipo_rotulo": rotulo_tipo(l["tipo_item"])}
                  for l in con.execute(
                      "SELECT id_item, codigo, nome, tipo_item FROM item_catalogo "
                      "WHERE id_item <> ? AND status_ciclo_vida NOT IN ('arquivado') "
                      "ORDER BY tipo_item, nome OFFSET 0 ROWS FETCH NEXT 300 ROWS ONLY", (id_item,))]
    checagem = governanca.pre_check(con, id_item)
    aba = request.args.get("aba", "resumo")
    if aba not in dict(ABAS_ATIVO):
        aba = "resumo"
    return render_template("detalhe.html", **dados, pessoas=pessoas,
                           candidatos=candidatos, relacoes=tipos.RELACOES,
                           destinos=tipos.DESTINOS_SUGERIDOS,
                           mecanismos=tipos.MECANISMOS,
                           trilha=servicos.trilha(con, id_item),
                           abas=ABAS_ATIVO, aba=aba,
                           analise=servicos.analise_impacto(con, id_item),
                           caminho=governanca.caminho_publicacao(con, id_item, checagem),
                           precheck=checagem)


@bp.route("/ativo/<int:id_item>/editar", methods=["POST"])
@exige("editar")
def editar(id_item: int):
    con = get_db()
    item = con.execute("SELECT tipo_item FROM item_catalogo WHERE id_item = ?",
                       (id_item,)).fetchone()
    t = tipos.tipo(item["tipo_item"])
    campos = {
        "nome": request.form["nome"],
        "descricao": request.form.get("descricao", ""),
        "criticidade": request.form.get("criticidade", "media"),
        "atributos": {c.nome: request.form.get(f"attr_{c.nome}", "").strip()
                      for c in t.campos},
    }
    if request.form.get("id_squad"):
        campos["id_squad"] = int(request.form["id_squad"])
    try:
        servicos.atualizar_item(con, id_item, campos, usuario_atual())
        flash("Alterações salvas no rascunho da revisão.", "ok")
    except servicos.RegraDeNegocio as erro:
        flash(str(erro), "erro")
    return redirect(url_for("web.detalhe", id_item=id_item))


@bp.route("/ativo/<int:id_item>/responsavel", methods=["POST"])
@exige("editar")
def responsavel(id_item: int):
    servicos.definir_responsavel(get_db(), id_item, int(request.form["id_pessoa"]),
                                 request.form["papel"], usuario_atual())
    flash("Responsável atualizado.", "ok")
    return redirect(url_for("web.detalhe", id_item=id_item, aba="pessoas"))


@bp.route("/ativo/<int:id_item>/relacao", methods=["POST"])
@exige("relacionar")
def relacao(id_item: int):
    destino = request.form.get("id_destino", "").strip()
    if not destino.isdigit():
        flash("Escolha um ativo de destino na lista.", "erro")
        return redirect(url_for("web.detalhe", id_item=id_item, aba="relacoes"))
    try:
        servicos.relacionar(get_db(), id_item, int(destino),
                            request.form["tipo_relacao"],
                            request.form.get("criticidade", "media"),
                            request.form.get("mecanismo") or None,
                            usuario=usuario_atual())
        flash("Relação registrada.", "ok")
    except servicos.RegraDeNegocio as erro:
        flash(str(erro), "erro")
    return redirect(url_for("web.detalhe", id_item=id_item, aba="relacoes"))


@bp.route("/ativo/<int:id_item>/evidencia", methods=["POST"])
@exige("editar")
def evidencia(id_item: int):
    servicos.anexar_evidencia(get_db(), id_item, request.form["tipo"],
                              request.form["titulo"], request.form.get("url"),
                              usuario=usuario_atual())
    flash("Evidência anexada.", "ok")
    return redirect(url_for("web.detalhe", id_item=id_item, aba="evidencias"))


@bp.route("/ativo/<int:id_item>/submeter", methods=["POST"])
@exige("submeter")
def submeter(id_item: int):
    con = get_db()
    try:
        resultado = servicos.submeter(con, id_item, request.form.get("motivo", ""),
                                      usuario_atual())
    except servicos.RegraDeNegocio as erro:
        flash(str(erro), "erro")
        return redirect(url_for("web.detalhe", id_item=id_item))
    if resultado["aprovado"]:
        flash(f"Revisão {resultado['numero_revisao']} enviada para validação.", "ok")
    else:
        flash("Pré-check reprovou: " + "; ".join(resultado["bloqueios"]), "erro")
    return redirect(url_for("web.detalhe", id_item=id_item))


@bp.route("/ativo/<int:id_item>/revisar", methods=["POST"])
@exige("revisar")
def revisar(id_item: int):
    try:
        servicos.abrir_revisao(get_db(), id_item, usuario_atual())
        flash("Revisão aberta. A versão publicada continua vigente.", "ok")
    except servicos.RegraDeNegocio as erro:
        flash(str(erro), "erro")
    return redirect(url_for("web.detalhe", id_item=id_item))


@bp.route("/ativo/<int:id_item>/descontinuar", methods=["POST"])
@exige("descontinuar")
def descontinuar(id_item: int):
    con = get_db()
    # confirmação em duas etapas quando há consumidor de alta criticidade:
    # a regra de bloqueio já existia; faltava a interface à altura dela
    analise = servicos.analise_impacto(con, id_item)
    if analise["criticos"]:
        item = con.execute("SELECT codigo FROM item_catalogo WHERE id_item = ?",
                           (id_item,)).fetchone()
        if request.form.get("confirmacao", "").strip().upper() != item["codigo"].upper():
            flash(f"Confirmação incorreta: digite o código {item['codigo']} para "
                  "descontinuar um ativo com consumidor crítico.", "erro")
            return redirect(url_for("web.detalhe", id_item=id_item, aba="relacoes"))
    resultado = servicos.descontinuar(con, id_item,
                                      request.form.get("motivo", ""),
                                      usuario_atual(),
                                      forcar=bool(request.form.get("forcar")))
    if resultado["bloqueado"]:
        flash(f"{resultado['motivo']} ({len(resultado['impacto'])} consumidores).", "erro")
    else:
        flash("Ativo descontinuado e relações encerradas.", "ok")
    return redirect(url_for("web.detalhe", id_item=id_item))


@bp.route("/ativo/<int:id_item>/relacoes-lote", methods=["GET", "POST"])
def relacoes_lote(id_item: int):
    """Mapear as dependências de uma aplicação inteira num gesto só."""
    con = get_db()
    item = con.execute("SELECT id_item, codigo, nome, tipo_item FROM item_catalogo "
                       "WHERE id_item = ?", (id_item,)).fetchone()
    if item is None:
        abort(404)
    tipo_relacao = request.values.get("tipo_relacao", "implementa")
    if tipo_relacao not in tipos.RELACOES:
        tipo_relacao = "implementa"

    if request.method == "POST":
        if not pode("relacionar", id_item):
            raise acesso.SemPermissao("Seu papel não permite relacionar este ativo.")
        destinos = [int(d) for d in request.form.getlist("destino") if d.isdigit()]
        if not destinos:
            flash("Marque ao menos um ativo.", "erro")
        else:
            resultado = servicos.relacionar_em_lote(
                con, id_item, destinos, tipo_relacao,
                request.form.get("criticidade", "media"),
                request.form.get("mecanismo") or None, usuario_atual())
            partes = [f"{resultado['criadas']} relação(ões) registrada(s)"]
            if resultado["ignoradas"]:
                partes.append(f"{resultado['ignoradas']} já existiam")
            flash(". ".join(partes) + ".", "ok")
            for erro in resultado["erros"]:
                flash(erro, "erro")
            return redirect(url_for("web.detalhe", id_item=id_item, aba="relacoes"))

    sugeridos = tipos.DESTINOS_SUGERIDOS.get(tipo_relacao, ())
    todos = request.values.get("todos") == "1"
    marcas = ",".join("?" * len(sugeridos))
    sql = ("SELECT i.id_item, i.codigo, i.nome, i.tipo_item, i.status_ciclo_vida,"
           " p.nome AS pai_nome,"
           " CASE WHEN EXISTS (SELECT 1 FROM relacionamento_ativo r WHERE r.id_origem = ?"
           "   AND r.id_destino = i.id_item AND r.tipo_relacao = ?) THEN 1 ELSE 0 END AS ja_existe"
           " FROM item_catalogo i LEFT JOIN item_catalogo p ON p.id_item = i.id_pai"
           " WHERE i.id_item <> ? AND i.status_ciclo_vida NOT IN ('arquivado')")
    params: list = [id_item, tipo_relacao, id_item]
    if sugeridos and not todos:
        sql += f" AND i.tipo_item IN ({marcas})"
        params += list(sugeridos)
    candidatos = [dict(l) for l in con.execute(
        sql + " ORDER BY i.tipo_item, i.nome OFFSET 0 ROWS FETCH NEXT 400 ROWS ONLY", params)]

    return render_template("relacoes_lote.html", item=dict(item),
                           trilha=servicos.trilha(con, id_item),
                           candidatos=candidatos, tipo_relacao=tipo_relacao,
                           relacoes=tipos.RELACOES, mecanismos=tipos.MECANISMOS,
                           sugeridos=sugeridos, todos=todos)


@bp.route("/ativo/<int:id_item>/comparar")
def comparar(id_item: int):
    con = get_db()
    item = con.execute(
        "SELECT * FROM item_catalogo WHERE id_item = ?", (id_item,)).fetchone()
    if item is None:
        abort(404)
    a = int(request.args.get("a", 1))
    b = int(request.args.get("b", 2))
    return render_template("comparar.html", id_item=id_item, a=a, b=b,
                           diff=servicos.comparar_revisoes(con, id_item, a, b),
                           trilha=servicos.trilha(con, id_item), item=item)


# ------------------------------------------------------- central de validações
@bp.route("/validacoes")
def validacoes():
    con = get_db()
    etapa = request.args.get("etapa", "")
    minhas = bool(request.args.get("minhas"))
    fila = governanca.fila_validacao(
        con, etapa or None, atribuido_a=usuario_atual() if minhas else None)
    contagem = {e["etapa"]: e["total"] for e in con.execute(
        "SELECT etapa, COUNT(*) total FROM validacao WHERE situacao = 'pendente' "
        "GROUP BY etapa")}
    contagem["minhas"] = len(governanca.fila_validacao(con, atribuido_a=usuario_atual()))
    selecionado = request.args.get("id_validacao", type=int)
    detalhe_val = None
    if selecionado:
        val = con.execute("SELECT * FROM validacao WHERE id_validacao = ?",
                          (selecionado,)).fetchone()
        if val:
            id_item = val["id_item"]
            detalhe_val = {
                "validacao": dict(val),
                "precheck": governanca.pre_check(con, id_item),
                "item": dict(con.execute(
                    "SELECT * FROM item_catalogo WHERE id_item = ?", (id_item,)).fetchone()),
                "trilha": servicos.trilha(con, id_item),
                "mudancas": servicos.diff_da_revisao(con, id_item, val["id_revisao"]),
                "evidencias": [dict(l) for l in con.execute(
                    "SELECT * FROM evidencia WHERE id_item = ? "
                    "ORDER BY id_evidencia DESC", (id_item,))],
                "responsaveis": [dict(l) for l in con.execute(
                    "SELECT r.papel, p.nome FROM responsabilidade r "
                    "JOIN pessoa p ON p.id_pessoa = r.id_pessoa "
                    "WHERE r.id_item = ? AND r.fim_vigencia IS NULL", (id_item,))],
            }
    return render_template("validacoes.html", fila=fila, contagem=contagem,
                           etapa=etapa, minhas=minhas, detalhe=detalhe_val)


def _proxima_da_fila(con, etapa: str, decidida: int) -> int | None:
    """Próximo item pendente da mesma aba, para o validador não voltar à lista."""
    for v in governanca.fila_validacao(con, etapa or None):
        if v["id_validacao"] != decidida:
            return v["id_validacao"]
    return None


@bp.route("/validacoes/<int:id_validacao>/assumir", methods=["POST"])
@exige("decidir")
def assumir(id_validacao: int):
    resultado = governanca.assumir_validacao(get_db(), id_validacao, usuario_atual())
    flash("Validação assumida por você." if resultado["assumida"]
          else resultado["motivo"], "ok" if resultado["assumida"] else "erro")
    return redirect(url_for("web.validacoes", etapa=request.form.get("etapa", ""),
                            id_validacao=id_validacao))


@bp.route("/validacoes/<int:id_validacao>/liberar", methods=["POST"])
@exige("decidir")
def liberar(id_validacao: int):
    governanca.liberar_validacao(get_db(), id_validacao, usuario_atual())
    flash("Validação devolvida à fila livre.", "ok")
    return redirect(url_for("web.validacoes", etapa=request.form.get("etapa", ""),
                            id_validacao=id_validacao))


@bp.route("/validacoes/<int:id_validacao>/decidir", methods=["POST"])
@exige("decidir")
def decidir(id_validacao: int):
    con = get_db()
    etapa = request.form.get("etapa", "")
    aprovar = request.form["decisao"] == "aprovar"
    seguir = bool(request.form.get("seguir"))
    proxima = _proxima_da_fila(con, etapa, id_validacao) if seguir else None
    quem = pessoa_atual()
    try:
        resultado = servicos.decidir_validacao(
            con, id_validacao, aprovar, request.form.get("parecer", ""),
            usuario_atual(), id_pessoa=quem["id_pessoa"] if quem else None)
    except servicos.RegraDeNegocio as erro:
        flash(str(erro), "erro")
        return redirect(url_for("web.validacoes", etapa=etapa))
    if resultado["publicado"]:
        flash("Todas as etapas aprovadas: nova revisão publicada.", "ok")
    elif aprovar:
        flash(f"Etapa aprovada. Restam {resultado['pendentes']} etapa(s).", "ok")
    else:
        flash("Revisão rejeitada e devolvida ao autor como rascunho.", "ok")
    if seguir and proxima is None:
        flash("Fila vazia: nada mais aguardando decisão nesta aba.", "ok")
    return redirect(url_for("web.validacoes", etapa=etapa, id_validacao=proxima))


@bp.route("/meu-trabalho")
def meu_trabalho():
    con = get_db()
    return render_template("mesa.html", **servicos.minha_mesa(con, usuario_atual()))


@bp.route("/politicas")
def politicas():
    con = get_db()
    linhas = [dict(l) for l in con.execute(
        "SELECT * FROM politica_governanca ORDER BY tipo_item, criticidade")]
    for l in linhas:
        l["etapas"] = json.loads(l["etapas"])
    return render_template("politicas.html", politicas=linhas,
                           matriz=governanca.MATRIZ_MUDANCA)


@bp.route("/cartilha")
def cartilha():
    """Guia de uso por perfil, dentro do layout do app.

    Matriz de permissões, trilha de etapas e ritos são derivados de
    `acesso.PERMISSOES`, `cartilha.FLUXOS` e da tabela de políticas — assim a
    cartilha não descreve uma ferramenta que já mudou.
    """
    con = get_db()
    ritos = [dict(l) for l in con.execute(
        "SELECT * FROM politica_governanca ORDER BY tipo_item, criticidade")]
    for r in ritos:
        codigos = json.loads(r["etapas"])
        r["etapas"] = [{"codigo": e, "rotulo": guia.ETAPA_ROTULO.get(e, e),
                        "classe": guia.ETAPA_CLASSE.get(e, "")} for e in codigos]
        r["criticidade"] = guia.CRITICIDADE_ROTULO.get(r["criticidade"], r["criticidade"])
    return render_template(
        "cartilha.html",
        perfis=guia.PERFIS,
        fluxos=guia.FLUXOS,
        primeiros_passos=guia.PRIMEIROS_PASSOS,
        regras=guia.REGRAS,
        duvidas=guia.DUVIDAS,
        matriz=guia.matriz(),
        papeis_ordem=guia.PAPEIS_ORDEM,
        papel_curto=guia.PAPEL_CURTO,
        etapa_rotulo=guia.ETAPA_ROTULO,
        total_tipos=len(tipos.TIPOS),
        ritos=ritos)
