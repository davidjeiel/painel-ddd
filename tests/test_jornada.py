"""Testes da onda 1 de navegação: orientação, busca, filtros e cadastro.

Cobrem as seis correções de jornada — trilha hierárquica, destaque de menu por
família de rota, busca global, filtros que voltam, KPIs acionáveis e o
formulário que não perde o que foi digitado.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import apoio  # noqa: E402

from catalogo import create_app, db as banco, governanca, servicos  # noqa: E402


@pytest.fixture()
def app(base_de_testes):
    aplicacao = create_app({"DATABASE": base_de_testes, "TESTING": True,
                            "SECRET_KEY": "teste"})
    with aplicacao.app_context():
        con = banco.get_db()
        banco.limpar_tudo(con)
        governanca.semear_politicas(con)
        con.execute("INSERT INTO squad (codigo, nome) VALUES ('SQ-1', 'Squad Crédito')")
        con.execute("INSERT INTO pessoa (matricula, nome, perfil) "
                    "VALUES ('M1', 'Ana Negócio', 'negocio')")
        con.commit()
        apoio.criar_pessoa(con, 'Admin Teste', 'admin.teste')
    return aplicacao


@pytest.fixture()
def cliente(app):
    """Cliente já autenticado: as rotas de escrita exigem sessão desde a F4.1."""
    c = app.test_client()
    with app.app_context():
        admin = banco.get_db().execute(
            "SELECT id_pessoa FROM pessoa WHERE login = 'admin.teste'"
        ).fetchone()["id_pessoa"]
    apoio.entrar(c, admin)
    return c


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


# ------------------------------------------------------------------------ P01
def test_trilha_sobe_da_raiz_ate_o_pai_direto(app):
    with app.app_context():
        con = banco.get_db()
        dom, sub, ctx, cap = montar_capacidade(con)
        caminho = servicos.trilha(con, cap)
    assert [p["id_item"] for p in caminho] == [dom, sub, ctx]
    assert [p["nome"] for p in caminho] == ["Contrato", "Originação", "Simulação"]


def test_trilha_de_item_raiz_e_vazia(app):
    with app.app_context():
        con = banco.get_db()
        dom, _, _, _ = montar_capacidade(con)
        assert servicos.trilha(con, dom) == []


def test_tela_do_ativo_mostra_a_trilha_clicavel(app, cliente):
    with app.app_context():
        con = banco.get_db()
        dom, sub, ctx, cap = montar_capacidade(con)
    html = cliente.get(f"/ativo/{cap}").get_data(as_text=True)
    assert 'aria-label="Trilha hierárquica"' in html
    for ancestral in (dom, sub, ctx):
        assert f'href="/ativo/{ancestral}"' in html
    assert html.index("Contrato") < html.index("Originação") < html.index("Simulação")


# ------------------------------------------------------------------------ P02
def test_menu_continua_marcado_dentro_de_um_ativo(app, cliente):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar_capacidade(con)
    html = cliente.get(f"/ativo/{cap}").get_data(as_text=True)
    assert 'href="/catalogo" class="ativo" aria-current="page"' in html


def test_menu_marca_o_cadastro_no_wizard(cliente):
    html = cliente.get("/ativo/novo").get_data(as_text=True)
    assert 'href="/ativo/novo" class="ativo" aria-current="page"' in html


# ------------------------------------------------------------------------ P03
def test_busca_global_sugere_ativos_por_termo(app, cliente):
    with app.app_context():
        montar_capacidade(banco.get_db())
    dados = cliente.get("/busca/sugestoes?termo=simul").get_json()
    nomes = [i["nome"] for i in dados["itens"]]
    assert "Simulação" in nomes and "Simular Financiamento" in nomes
    assert all(i["url"].startswith("/ativo/") for i in dados["itens"])


def test_busca_global_ignora_termo_curto(app, cliente):
    with app.app_context():
        montar_capacidade(banco.get_db())
    assert cliente.get("/busca/sugestoes?termo=s").get_json()["itens"] == []


def test_campo_de_busca_existe_em_todas_as_telas(cliente):
    for rota in ("/", "/catalogo", "/mapa", "/validacoes", "/politicas"):
        assert 'id="busca-global"' in cliente.get(rota).get_data(as_text=True), rota


# ------------------------------------------------------------------------ P04
def test_filtros_voltam_na_visita_seguinte(app, cliente):
    with app.app_context():
        montar_capacidade(banco.get_db())
    cliente.get("/catalogo?tipo_item=dominio")
    html = cliente.get("/catalogo").get_data(as_text=True)
    assert 'value="dominio" selected' in html
    assert "Simular Financiamento" not in html  # o recorte anterior continua valendo


def test_chip_remove_apenas_o_proprio_filtro(app, cliente):
    with app.app_context():
        montar_capacidade(banco.get_db())
    html = cliente.get("/catalogo?tipo_item=dominio&criticidade=media").get_data(as_text=True)
    assert 'aria-label="Filtros ativos"' in html
    assert "criticidade=media" in html and "tipo_item=dominio" in html


def test_limpar_zera_os_filtros_guardados(app, cliente):
    with app.app_context():
        montar_capacidade(banco.get_db())
    cliente.get("/catalogo?tipo_item=dominio")
    cliente.get("/catalogo?limpar=1")
    html = cliente.get("/catalogo").get_data(as_text=True)
    assert "Simular Financiamento" in html
    assert 'aria-label="Filtros ativos"' not in html


# ------------------------------------------------------------------------ P05
def test_filtro_sem_owner_isola_os_ativos_sem_responsavel(app):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar_capacidade(con)
        servicos.definir_responsavel(con, cap, 1, "owner_negocial")
        orfaos = [i["nome"] for i in servicos.buscar(con, sem_owner="1")]
    assert "Simular Financiamento" not in orfaos
    assert "Contrato" in orfaos


def test_kpis_do_painel_levam_ao_recorte(app, cliente):
    with app.app_context():
        montar_capacidade(banco.get_db())
    html = cliente.get("/").get_data(as_text=True)
    for destino in ("/catalogo?tipo_item=dominio", "/catalogo?sem_owner=1",
                    "/catalogo?tipo_item=capacidade", "/catalogo?tipo_item=api"):
        assert f'href="{destino}"' in html, destino


def test_queda_de_pendencia_e_lida_como_melhora(app, cliente):
    """Cair é bom em 'sem responsável': a cor tem de acompanhar o sentido."""
    with app.app_context():
        con = banco.get_db()
        montar_capacidade(con)
        con.execute("INSERT INTO snapshot_indicador (competencia, indicador, valor) "
                    "VALUES ('2026-07', 'sem_owner', 9)")
        con.execute("INSERT INTO snapshot_indicador (competencia, indicador, valor) "
                    "VALUES ('2026-08', 'sem_owner', 4)")
        con.execute("INSERT INTO snapshot_indicador (competencia, indicador, valor) "
                    "VALUES ('2026-07', 'cobertura', 70)")
        con.execute("INSERT INTO snapshot_indicador (competencia, indicador, valor) "
                    "VALUES ('2026-08', 'cobertura', 55)")
        con.commit()
    html = cliente.get("/").get_data(as_text=True)
    assert 'class="delta bom"' in html    # menos órfãos, melhora
    assert 'class="delta ruim"' in html   # menos cobertura, piora
    assert "5 no mês" in html             # 9 → 4, sem casa decimal supérflua


def test_variacao_compara_as_duas_ultimas_competencias(app):
    with app.app_context():
        con = banco.get_db()
        con.execute("INSERT INTO snapshot_indicador (competencia, indicador, valor) "
                    "VALUES ('2026-07', 'cobertura', 60)")
        con.execute("INSERT INTO snapshot_indicador (competencia, indicador, valor) "
                    "VALUES ('2026-08', 'cobertura', 72)")
        con.execute("INSERT INTO snapshot_indicador (competencia, indicador, valor) "
                    "VALUES ('2026-08', 'pendencias', 4)")
        con.commit()
        variacao = servicos.variacao_indicadores(con)
    assert variacao["cobertura"] == 12
    assert "pendencias" not in variacao  # uma competência só não vira tendência


# ------------------------------------------------------------------------ P06
def test_wizard_devolve_o_que_foi_digitado_apos_erro(app, cliente):
    with app.app_context():
        montar_capacidade(banco.get_db())
    resposta = cliente.post("/ativo/novo", data={
        "acao": "salvar", "tipo_item": "dominio", "nome": "contrato",
        "descricao": "Outro domínio de contratos", "criticidade": "alta",
        "id_squad": "1", "attr_visao": "Unificar a originação",
        "attr_fórum": "Comitê de Crédito"})
    html = resposta.get_data(as_text=True)
    assert resposta.status_code == 200
    assert "Unificar a originação" in html          # campo de área do tipo
    assert "Comitê de Crédito" in html              # campo de texto do tipo
    assert 'value="alta" selected' in html          # criticidade escolhida
    assert 'value="1" selected' in html             # squad escolhida
    assert "Outro domínio de contratos" in html


def test_wizard_preserva_o_pai_escolhido_apos_erro(app, cliente):
    with app.app_context():
        con = banco.get_db()
        dom, _, _, _ = montar_capacidade(con)
    resposta = cliente.post("/ativo/novo", data={
        "acao": "salvar", "tipo_item": "subdominio", "nome": "originação",
        "descricao": "Duplicado", "id_pai": str(dom),
        "attr_classificacao": "suporte"})
    html = resposta.get_data(as_text=True)
    assert f'value="{dom}" selected' in html
    assert 'value="suporte" selected' in html
