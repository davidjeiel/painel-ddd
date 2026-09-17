"""API interna (JSON) para integrações e para a camada analítica."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from . import governanca, qualidade, servicos
from .db import get_db

bp = Blueprint("api", __name__, url_prefix="/api/v1")


@bp.errorhandler(servicos.RegraDeNegocio)
def erro_regra(exc):
    return jsonify({"erro": str(exc)}), 422


@bp.errorhandler(KeyError)
def erro_campo_ausente(exc):
    return jsonify({"erro": f"campo obrigatório ausente ou inválido: {exc}"}), 400


@bp.get("/itens")
def listar_itens():
    itens = servicos.buscar(
        get_db(),
        termo=request.args.get("termo", ""),
        tipo_item=request.args.get("tipo_item", ""),
        status=request.args.get("status", ""),
        criticidade=request.args.get("criticidade", ""),
        origem=request.args.get("origem", ""),
        limite=int(request.args.get("limite", 200)),
    )
    return jsonify({"total": len(itens), "itens": itens})


@bp.post("/itens")
def criar_item():
    corpo = request.get_json(force=True)
    id_item = servicos.criar_item(
        get_db(),
        tipo_item=corpo["tipo_item"],
        nome=corpo["nome"],
        descricao=corpo.get("descricao", ""),
        id_pai=corpo.get("id_pai"),
        id_squad=corpo.get("id_squad"),
        criticidade=corpo.get("criticidade", "media"),
        atributos=corpo.get("atributos"),
        usuario=corpo.get("usuario", "api"),
    )
    return jsonify({"id_item": id_item}), 201


@bp.get("/itens/<int:id_item>")
def obter_item(id_item: int):
    dados = servicos.visao_360(get_db(), id_item)
    return jsonify(dados)


@bp.get("/itens/<int:id_item>/qualidade")
def obter_qualidade(id_item: int):
    return jsonify(qualidade.avaliar(get_db(), id_item))


@bp.get("/itens/<int:id_item>/vizinhanca")
def obter_vizinhanca(id_item: int):
    return jsonify(servicos.vizinhanca(
        get_db(), id_item,
        saltos=int(request.args.get("saltos", 1)),
        tipos_relacao=tuple(request.args.getlist("tipo")),
        teto=int(request.args.get("teto", 150))))


@bp.get("/itens/<int:id_item>/precheck")
def obter_precheck(id_item: int):
    return jsonify(governanca.pre_check(get_db(), id_item))


@bp.post("/itens/<int:id_item>/submeter")
def submeter(id_item: int):
    corpo = request.get_json(silent=True) or {}
    return jsonify(servicos.submeter(get_db(), id_item, corpo.get("motivo", ""),
                                     corpo.get("usuario", "api")))


@bp.post("/itens/<int:id_item>/relacoes")
def criar_relacao(id_item: int):
    corpo = request.get_json(force=True)
    id_relacao = servicos.relacionar(
        get_db(), id_item, corpo["id_destino"], corpo["tipo_relacao"],
        corpo.get("criticidade", "media"), corpo.get("mecanismo"),
        corpo.get("origem_evidencia", "manual"), corpo.get("usuario", "api"))
    return jsonify({"id_relacao": id_relacao}), 201


@bp.get("/validacoes")
def listar_validacoes():
    return jsonify(governanca.fila_validacao(get_db(), request.args.get("etapa")))


@bp.post("/validacoes/<int:id_validacao>")
def decidir(id_validacao: int):
    corpo = request.get_json(force=True)
    return jsonify(servicos.decidir_validacao(
        get_db(), id_validacao, bool(corpo["aprovar"]), corpo.get("parecer", ""),
        corpo.get("usuario", "api")))


@bp.get("/indicadores")
def indicadores():
    con = get_db()
    return jsonify({
        "kpis": servicos.indicadores(con),
        "cobertura_por_dominio": servicos.cobertura_por_dominio(con),
        "pendencias": servicos.pendencias_prioritarias(con),
    })


@bp.post("/snapshots")
def snapshot():
    corpo = request.get_json(silent=True) or {}
    servicos.gerar_snapshot(get_db(), corpo.get("competencia"))
    return jsonify({"situacao": "gerado"}), 201
