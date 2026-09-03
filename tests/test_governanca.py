"""Testes das regras centrais: ciclo de vida, pré-check, qualidade e publicação."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from catalogo import create_app, db as banco, governanca, qualidade, servicos  # noqa: E402


@pytest.fixture()
def con(tmp_path):
    caminho = tmp_path / "teste.db"
    conexao = banco.conectar(str(caminho))
    banco.criar_schema(conexao)
    governanca.semear_politicas(conexao)
    conexao.execute("INSERT INTO squad (codigo, nome) VALUES ('SQ-1', 'Squad Teste')")
    conexao.execute(
        "INSERT INTO pessoa (matricula, nome, perfil) VALUES ('M1', 'Teste Negócio', 'negocio')")
    conexao.execute(
        "INSERT INTO pessoa (matricula, nome, perfil) VALUES ('M2', 'Teste Técnico', 'tech_lead')")
    conexao.commit()
    yield conexao
    conexao.close()


def montar_capacidade(con):
    dom = servicos.criar_item(con, tipo_item="dominio", nome="Contrato",
                              descricao="Domínio de contratos",
                              atributos={"visao": "Sustentar contratos"})
    sub = servicos.criar_item(con, tipo_item="subdominio", nome="Originação",
                              descricao="Formalização", id_pai=dom,
                              atributos={"classificacao": "core"})
    ctx = servicos.criar_item(con, tipo_item="contexto", nome="Simulação",
                              descricao="Cálculo de condições", id_pai=sub,
                              atributos={"linguagem_ubiqua": "Simulação"})
    cap = servicos.criar_item(con, tipo_item="capacidade", nome="Simular Financiamento",
                              descricao="Calcula condições", id_pai=ctx,
                              atributos={"resultado_esperado": "Proposta simulada"})
    return dom, sub, ctx, cap


def test_hierarquia_invalida_e_recusada(con):
    dom, _, _, _ = montar_capacidade(con)
    with pytest.raises(servicos.RegraDeNegocio):
        servicos.criar_item(con, tipo_item="capacidade", nome="Capacidade solta",
                            id_pai=dom)


def test_nome_duplicado_no_mesmo_tipo(con):
    montar_capacidade(con)
    with pytest.raises(servicos.RegraDeNegocio):
        servicos.criar_item(con, tipo_item="dominio", nome="contrato")


def test_precheck_bloqueia_sem_owner(con):
    _, _, _, cap = montar_capacidade(con)
    resultado = governanca.pre_check(con, cap)
    assert not resultado["aprovado"]
    assert any("negocial" in b.lower() for b in resultado["bloqueios"])


def test_fluxo_completo_ate_publicacao(con):
    _, _, _, cap = montar_capacidade(con)
    servicos.definir_responsavel(con, cap, 1, "owner_negocial")
    servicos.definir_responsavel(con, cap, 2, "owner_tecnico")
    servicos.anexar_evidencia(con, cap, "documento", "Política de crédito")
    servicos.criar_item(con, tipo_item="sistema", nome="Plataforma",
                        descricao="Sistema", atributos={"plataforma": "nuvem"})
    app_id = servicos.criar_item(con, tipo_item="aplicacao", nome="Motor",
                                 descricao="Serviço de cálculo", id_pai=5,
                                 atributos={"tecnologia": "Python"})
    servicos.relacionar(con, app_id, cap, "implementa")

    resultado = servicos.submeter(con, cap, "Publicação inicial")
    assert resultado["aprovado"], resultado["bloqueios"]

    pendentes = con.execute(
        "SELECT id_validacao FROM validacao WHERE id_item = ? AND situacao = 'pendente'",
        (cap,)).fetchall()
    assert len(pendentes) == 2  # negocial + técnica

    for linha in pendentes[:-1]:
        parcial = servicos.decidir_validacao(con, linha["id_validacao"], True, "ok")
        assert not parcial["publicado"]
    final = servicos.decidir_validacao(con, pendentes[-1]["id_validacao"], True, "ok")
    assert final["publicado"]

    item = con.execute("SELECT * FROM item_catalogo WHERE id_item = ?", (cap,)).fetchone()
    assert item["status_ciclo_vida"] == "publicado"
    assert item["revisao_atual"] is not None


def test_publicado_e_imutavel(con):
    _, _, _, cap = montar_capacidade(con)
    con.execute("UPDATE item_catalogo SET status_ciclo_vida = 'publicado' WHERE id_item = ?",
                (cap,))
    con.commit()
    with pytest.raises(servicos.RegraDeNegocio):
        servicos.atualizar_item(con, cap, {"nome": "Outro nome"})


def test_rejeicao_devolve_para_rascunho(con):
    _, _, _, cap = montar_capacidade(con)
    servicos.definir_responsavel(con, cap, 1, "owner_negocial")
    servicos.definir_responsavel(con, cap, 2, "owner_tecnico")
    servicos.anexar_evidencia(con, cap, "documento", "Política")
    sis = servicos.criar_item(con, tipo_item="sistema", nome="Plataforma",
                              descricao="Sistema", atributos={"plataforma": "nuvem"})
    app_id = servicos.criar_item(con, tipo_item="aplicacao", nome="Motor",
                                 descricao="Serviço", id_pai=sis,
                                 atributos={"tecnologia": "Python"})
    servicos.relacionar(con, app_id, cap, "implementa")
    servicos.submeter(con, cap, "tentativa")
    val = con.execute(
        "SELECT id_validacao FROM validacao WHERE id_item = ? LIMIT 1", (cap,)).fetchone()
    servicos.decidir_validacao(con, val["id_validacao"], False, "faltou evidência")
    status = con.execute("SELECT status_ciclo_vida FROM item_catalogo WHERE id_item = ?",
                         (cap,)).fetchone()["status_ciclo_vida"]
    assert status == "rascunho"


def test_dependencia_circular_recusada(con):
    _, _, ctx_a, _ = montar_capacidade(con)
    sub = con.execute("SELECT id_item FROM item_catalogo WHERE tipo_item = 'subdominio'"
                      ).fetchone()["id_item"]
    ctx_b = servicos.criar_item(con, tipo_item="contexto", nome="Garantias",
                                descricao="Contexto de garantias", id_pai=sub)
    servicos.relacionar(con, ctx_a, ctx_b, "depende_de")
    with pytest.raises(servicos.RegraDeNegocio):
        servicos.relacionar(con, ctx_b, ctx_a, "depende_de")


def test_descontinuacao_bloqueada_por_consumidor_critico(con):
    _, _, _, cap = montar_capacidade(con)
    sis = servicos.criar_item(con, tipo_item="sistema", nome="Core",
                              descricao="Legado", atributos={"plataforma": "mainframe"})
    app_id = servicos.criar_item(con, tipo_item="aplicacao", nome="Gestor",
                                 descricao="App", id_pai=sis,
                                 atributos={"tecnologia": "COBOL"})
    servicos.relacionar(con, app_id, cap, "implementa", criticidade="critica")
    con.execute("UPDATE item_catalogo SET status_ciclo_vida = 'publicado' WHERE id_item = ?",
                (app_id,))
    con.commit()
    resultado = servicos.descontinuar(con, cap, "obsoleta")
    assert resultado["bloqueado"]
    forcado = servicos.descontinuar(con, cap, "obsoleta", forcar=True)
    assert not forcado["bloqueado"]


def test_score_de_qualidade_sobe_com_cadastro_completo(con):
    _, _, _, cap = montar_capacidade(con)
    inicial = qualidade.avaliar(con, cap)["score_total"]
    servicos.definir_responsavel(con, cap, 1, "owner_negocial")
    servicos.definir_responsavel(con, cap, 2, "owner_tecnico")
    servicos.anexar_evidencia(con, cap, "documento", "Política")
    final = qualidade.avaliar(con, cap)["score_total"]
    assert final > inicial


def test_api_lista_itens(tmp_path):
    caminho = tmp_path / "api.db"
    app = create_app({"DATABASE": str(caminho), "TESTING": True})
    with app.app_context():
        banco.init_db()
        governanca.semear_politicas(banco.get_db())
        servicos.criar_item(banco.get_db(), tipo_item="dominio", nome="Garantias",
                            descricao="Domínio", atributos={"visao": "Reduzir risco"})
    cliente = app.test_client()
    resposta = cliente.get("/api/v1/itens")
    assert resposta.status_code == 200
    assert resposta.get_json()["total"] == 1
    assert cliente.get("/").status_code == 200
