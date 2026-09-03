"""Telas nucleares: catálogo, wizard, visão 360° e central de validações."""
from __future__ import annotations

import json

from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)

from . import governanca, servicos, tipos
from .db import get_db

bp = Blueprint("web", __name__)


def usuario_atual() -> str:
    return session.get("usuario", "curador.demo")


@bp.app_template_filter("rotulo_tipo")
def rotulo_tipo(chave):
    return tipos.TIPOS[chave].rotulo if chave in tipos.TIPOS else chave


@bp.app_template_filter("rotulo_status")
def rotulo_status(chave):
    return tipos.CICLO_VIDA.get(chave, chave)


@bp.app_template_filter("sla")
def filtro_sla(prazo):
    return governanca.sla_restante(prazo)


@bp.app_context_processor
def contexto():
    return {"TIPOS": tipos.TIPOS, "CICLO": tipos.CICLO_VIDA,
            "CRITICIDADES": tipos.CRITICIDADES, "usuario": usuario_atual()}


# ------------------------------------------------------------------ dashboard
@bp.route("/")
def dashboard():
    con = get_db()
    return render_template(
        "dashboard.html",
        kpis=servicos.indicadores(con),
        cobertura=servicos.cobertura_por_dominio(con),
        pendencias=servicos.pendencias_prioritarias(con),
        serie=servicos.serie_historica(con, "cobertura"),
        serie_qualidade=servicos.serie_historica(con, "qualidade_media"),
        fila=governanca.fila_validacao(con)[:5],
    )


# -------------------------------------------------------------------- catálogo
@bp.route("/catalogo")
def catalogo():
    con = get_db()
    filtros = {
        "termo": request.args.get("termo", "").strip(),
        "tipo_item": request.args.get("tipo_item", ""),
        "status": request.args.get("status", ""),
        "id_squad": request.args.get("id_squad", ""),
        "criticidade": request.args.get("criticidade", ""),
    }
    session["filtros_catalogo"] = filtros  # filtros persistentes
    itens = servicos.buscar(con, **filtros)
    squads = [dict(l) for l in con.execute("SELECT * FROM squad ORDER BY nome")]
    return render_template("catalogo.html", itens=itens, filtros=filtros, squads=squads)


@bp.route("/mapa")
def mapa():
    con = get_db()
    arvore = []
    for dominio in con.execute(
        "SELECT * FROM item_catalogo WHERE tipo_item = 'dominio' ORDER BY nome"
    ):
        subs = []
        for sub in con.execute(
            "SELECT * FROM item_catalogo WHERE id_pai = ? ORDER BY nome",
            (dominio["id_item"],)
        ):
            contextos = []
            for ctx in con.execute(
                "SELECT * FROM item_catalogo WHERE id_pai = ? ORDER BY nome",
                (sub["id_item"],)
            ):
                caps = [dict(c) for c in con.execute(
                    "SELECT i.*, (SELECT COUNT(*) FROM relacionamento_ativo r "
                    " WHERE r.id_destino = i.id_item AND r.tipo_relacao = 'implementa'"
                    "   AND r.fim_vigencia IS NULL) AS implementacoes "
                    "FROM item_catalogo i WHERE i.id_pai = ? ORDER BY i.nome",
                    (ctx["id_item"],))]
                contextos.append({**dict(ctx), "capacidades": caps})
            subs.append({**dict(sub), "contextos": contextos})
        arvore.append({**dict(dominio), "subdominios": subs})
    return render_template("mapa.html", arvore=arvore)


# ---------------------------------------------------------------------- wizard
@bp.route("/ativo/novo", methods=["GET", "POST"])
def novo_ativo():
    con = get_db()
    tipo_item = request.values.get("tipo_item", "")
    if request.method == "POST" and request.form.get("acao") == "salvar":
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
    return render_template("wizard.html", tipo_item=tipo_item, pais=pais,
                           squads=squads, blocos=tipos.blocos(),
                           form=request.form)


# ------------------------------------------------------------------- visão 360
@bp.route("/ativo/<int:id_item>")
def detalhe(id_item: int):
    con = get_db()
    dados = servicos.visao_360(con, id_item)
    pessoas = [dict(l) for l in con.execute(
        "SELECT id_pessoa, nome, perfil FROM pessoa WHERE ativo = 1 ORDER BY nome")]
    candidatos = [dict(l) for l in con.execute(
        "SELECT id_item, codigo, nome, tipo_item FROM item_catalogo "
        "WHERE id_item <> ? AND status_ciclo_vida NOT IN ('arquivado') "
        "ORDER BY tipo_item, nome LIMIT 300", (id_item,))]
    return render_template("detalhe.html", **dados, pessoas=pessoas,
                           candidatos=candidatos, relacoes=tipos.RELACOES,
                           precheck=governanca.pre_check(con, id_item))


@bp.route("/ativo/<int:id_item>/editar", methods=["POST"])
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
def responsavel(id_item: int):
    servicos.definir_responsavel(get_db(), id_item, int(request.form["id_pessoa"]),
                                 request.form["papel"], usuario_atual())
    flash("Responsável atualizado.", "ok")
    return redirect(url_for("web.detalhe", id_item=id_item))


@bp.route("/ativo/<int:id_item>/relacao", methods=["POST"])
def relacao(id_item: int):
    try:
        servicos.relacionar(get_db(), id_item, int(request.form["id_destino"]),
                            request.form["tipo_relacao"],
                            request.form.get("criticidade", "media"),
                            request.form.get("mecanismo") or None,
                            usuario=usuario_atual())
        flash("Relação registrada.", "ok")
    except servicos.RegraDeNegocio as erro:
        flash(str(erro), "erro")
    return redirect(url_for("web.detalhe", id_item=id_item))


@bp.route("/ativo/<int:id_item>/evidencia", methods=["POST"])
def evidencia(id_item: int):
    servicos.anexar_evidencia(get_db(), id_item, request.form["tipo"],
                              request.form["titulo"], request.form.get("url"),
                              usuario=usuario_atual())
    flash("Evidência anexada.", "ok")
    return redirect(url_for("web.detalhe", id_item=id_item))


@bp.route("/ativo/<int:id_item>/submeter", methods=["POST"])
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
def revisar(id_item: int):
    try:
        servicos.abrir_revisao(get_db(), id_item, usuario_atual())
        flash("Revisão aberta. A versão publicada continua vigente.", "ok")
    except servicos.RegraDeNegocio as erro:
        flash(str(erro), "erro")
    return redirect(url_for("web.detalhe", id_item=id_item))


@bp.route("/ativo/<int:id_item>/descontinuar", methods=["POST"])
def descontinuar(id_item: int):
    resultado = servicos.descontinuar(get_db(), id_item,
                                      request.form.get("motivo", ""),
                                      usuario_atual(),
                                      forcar=bool(request.form.get("forcar")))
    if resultado["bloqueado"]:
        flash(f"{resultado['motivo']} ({len(resultado['impacto'])} consumidores).", "erro")
    else:
        flash("Ativo descontinuado e relações encerradas.", "ok")
    return redirect(url_for("web.detalhe", id_item=id_item))


@bp.route("/ativo/<int:id_item>/comparar")
def comparar(id_item: int):
    con = get_db()
    a = int(request.args.get("a", 1))
    b = int(request.args.get("b", 2))
    return render_template("comparar.html", id_item=id_item, a=a, b=b,
                           diff=servicos.comparar_revisoes(con, id_item, a, b),
                           item=con.execute(
                               "SELECT * FROM item_catalogo WHERE id_item = ?",
                               (id_item,)).fetchone())


# ------------------------------------------------------- central de validações
@bp.route("/validacoes")
def validacoes():
    con = get_db()
    etapa = request.args.get("etapa", "")
    fila = governanca.fila_validacao(con, etapa or None)
    contagem = {e["etapa"]: e["total"] for e in con.execute(
        "SELECT etapa, COUNT(*) total FROM validacao WHERE situacao = 'pendente' "
        "GROUP BY etapa")}
    selecionado = request.args.get("id_validacao", type=int)
    detalhe_val = None
    if selecionado:
        val = con.execute("SELECT * FROM validacao WHERE id_validacao = ?",
                          (selecionado,)).fetchone()
        if val:
            detalhe_val = {"validacao": dict(val),
                           "precheck": governanca.pre_check(con, val["id_item"]),
                           "item": dict(con.execute(
                               "SELECT * FROM item_catalogo WHERE id_item = ?",
                               (val["id_item"],)).fetchone())}
    return render_template("validacoes.html", fila=fila, contagem=contagem,
                           etapa=etapa, detalhe=detalhe_val)


@bp.route("/validacoes/<int:id_validacao>/decidir", methods=["POST"])
def decidir(id_validacao: int):
    con = get_db()
    aprovar = request.form["decisao"] == "aprovar"
    try:
        resultado = servicos.decidir_validacao(
            con, id_validacao, aprovar, request.form.get("parecer", ""), usuario_atual())
    except servicos.RegraDeNegocio as erro:
        flash(str(erro), "erro")
        return redirect(url_for("web.validacoes"))
    if resultado["publicado"]:
        flash("Todas as etapas aprovadas: nova revisão publicada.", "ok")
    elif aprovar:
        flash(f"Etapa aprovada. Restam {resultado['pendentes']} etapa(s).", "ok")
    else:
        flash("Revisão rejeitada e devolvida ao autor como rascunho.", "ok")
    return redirect(url_for("web.validacoes"))


@bp.route("/politicas")
def politicas():
    con = get_db()
    linhas = [dict(l) for l in con.execute(
        "SELECT * FROM politica_governanca ORDER BY tipo_item, criticidade")]
    for l in linhas:
        l["etapas"] = json.loads(l["etapas"])
    return render_template("politicas.html", politicas=linhas,
                           matriz=governanca.MATRIZ_MUDANCA)
