"""Testes da cartilha de uso.

O risco desta tela não é quebrar — é **envelhecer**. Uma cartilha que descreve
uma regra que o sistema não aplica mais é pior do que não ter cartilha: a pessoa
confia nela e erra. Por isso os testes aqui não conferem texto bonito, e sim que
a matriz da página continua saindo de `acesso.PERMISSOES` e a tabela de ritos, da
tabela de políticas.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import apoio  # noqa: E402

from catalogo import (acesso, cartilha, create_app, db as banco,  # noqa: E402
                      governanca)

CSS = Path(__file__).resolve().parent.parent / "catalogo" / "static" / "estilo.css"


@pytest.fixture()
def app(tmp_path):
    aplicacao = create_app({"DATABASE": str(tmp_path / "cartilha.db"), "TESTING": True,
                            "SECRET_KEY": "teste"})
    with aplicacao.app_context():
        banco.init_db()
        governanca.semear_politicas(banco.get_db())
    return aplicacao


@pytest.fixture()
def cliente(app):
    return app.test_client()


# ------------------------------------------------------------------ a página
def test_cartilha_abre_sem_identificacao(cliente):
    """Quem ainda não se identificou é justamente quem mais precisa do guia."""
    resposta = cliente.get("/cartilha")
    assert resposta.status_code == 200
    assert "O fluxo de cada perfil" in resposta.get_data(as_text=True)


def test_cartilha_nao_escreve_nada(cliente):
    """Página de leitura: nenhum formulário de escrita, para nenhum papel."""
    html = cliente.get("/cartilha").get_data(as_text=True)
    assert 'method="post"' not in html.lower()


def test_cada_perfil_tem_secao_e_atalho(cliente):
    html = cliente.get("/cartilha").get_data(as_text=True)
    for perfil in cartilha.PERFIS:
        assert 'id="%s"' % perfil["chave"] in html      # a seção existe
        assert 'href="#%s"' % perfil["chave"] in html   # e o atalho chega nela
        assert perfil["lema"] in html


# ------------------------------------------- a matriz sai do código, não do texto
def test_matriz_reflete_as_permissoes_reais():
    """Cada célula da matriz é lida de acesso.PERMISSOES, ação por ação."""
    linhas = {l["acao"]: l for l in cartilha.matriz()}
    for acao, papeis in acesso.PERMISSOES.items():
        for papel in cartilha.PAPEIS_ORDEM:
            assert linhas[acao]["papeis"][papel] == (papel in papeis), (acao, papel)


def test_matriz_acompanha_mudanca_de_permissao(cliente):
    """Mudou a regra no código, muda a página — sem ninguém editar a cartilha."""
    html = cliente.get("/cartilha").get_data(as_text=True)
    assert "Descontinuar ativo" in html

    original = acesso.PERMISSOES
    try:
        acesso.PERMISSOES = dict(original, descontinuar=set())  # ninguém descontinua
        linhas = {l["acao"]: l for l in cartilha.matriz()}
        assert not any(linhas["descontinuar"]["papeis"].values())
    finally:
        acesso.PERMISSOES = original

    linhas = {l["acao"]: l for l in cartilha.matriz()}
    assert linhas["descontinuar"]["papeis"]["arquiteto"] is True


def test_curador_nao_aparece_decidindo_validacao():
    """A segregação de função precisa estar visível, não só aplicada."""
    linhas = {l["acao"]: l for l in cartilha.matriz()}
    assert linhas["decidir"]["papeis"]["curador"] is False
    assert linhas["decidir"]["papeis"]["admin"] is True


def test_consulta_nao_pode_nada_na_matriz():
    for linha in cartilha.matriz():
        assert linha["papeis"]["consulta"] is False, linha["acao"]


def test_etapas_por_papel_sai_do_acesso():
    mapa = cartilha.etapas_por_papel()
    assert mapa["negocio"] == ["negocial"]
    assert mapa["tech_lead"] == ["tecnica"]
    assert mapa["arquiteto"] == ["arquitetural"]
    assert sorted(mapa["admin"]) == ["arquitetural", "negocial", "tecnica"]


# ------------------------------------------------- os ritos saem do banco
def test_ritos_vem_da_tabela_de_politicas(app, cliente):
    html = cliente.get("/cartilha").get_data(as_text=True)
    with app.app_context():
        linhas = banco.get_db().execute(
            "SELECT tipo_item, score_minimo, sla_horas FROM politica_governanca").fetchall()
    assert linhas, "políticas não semeadas: o teste não provaria nada"
    for linha in linhas:
        assert "%s%%" % linha["score_minimo"] in html
        assert "%sh" % linha["sla_horas"] in html


def test_rito_critico_e_mais_apertado_que_o_padrao(app):
    """O que a cartilha afirma sobre criticidade precisa ser verdade no banco."""
    with app.app_context():
        con = banco.get_db()
        padrao = con.execute(
            "SELECT * FROM politica_governanca WHERE tipo_item='api' AND criticidade='*'"
        ).fetchone()
        critica = con.execute(
            "SELECT * FROM politica_governanca WHERE tipo_item='api' AND criticidade='critica'"
        ).fetchone()
    assert critica["score_minimo"] > padrao["score_minimo"]
    assert critica["sla_horas"] < padrao["sla_horas"]
    assert critica["evidencia_minima"] > padrao["evidencia_minima"]


# --------------------------------------------------------- os dois acessos
def test_rodape_leva_a_cartilha_em_qualquer_tela(app, cliente):
    """O rodapé é do site, não da tela: precisa estar em todas."""
    with app.app_context():
        apoio.criar_pessoa(banco.get_db(), "Admin", "admin.teste", "admin")
    apoio.entrar(cliente, 1)
    for rota in ("/", "/catalogo", "/politicas", "/mapa", "/cartilha"):
        html = cliente.get(rota).get_data(as_text=True)
        assert '<footer class="rodape">' in html, rota
        assert 'Cartilha de uso' in html, rota


def test_atalho_fica_ao_lado_do_botao_de_identificacao(cliente):
    """Ao lado de "quem sou eu" fica "o que eu posso fazer"."""
    html = cliente.get("/").get_data(as_text=True)
    assert 'class="cartilha-atalho' in html
    identifica = html.index('class="quem"')
    atalho = html.index('class="cartilha-atalho')
    fim_identidade = html.index("</div>", identifica)
    assert identifica < atalho < fim_identidade    # dentro da mesma barra, logo depois


def test_atalho_se_marca_quando_voce_esta_na_cartilha(cliente):
    assert 'class="cartilha-atalho ativo"' in cliente.get("/cartilha").get_data(as_text=True)
    assert 'class="cartilha-atalho ativo"' not in cliente.get("/").get_data(as_text=True)


# ------------------------------------------------------------------ aparência
def test_cores_de_perfil_existem_nos_tres_estados_de_tema():
    """Se a cor só existe no claro, a cartilha fica ilegível de noite."""
    css = CSS.read_text(encoding="utf-8")
    for bloco in ("--perfil-negocio", "--perfil-tech", "--perfil-arquiteto",
                  "--perfil-curador", "--perfil-admin", "--perfil-consulta"):
        assert css.count(bloco + ":") >= 3, bloco   # claro, sistema escuro e manual


def test_rodape_e_atalho_tem_estilo_proprio():
    css = CSS.read_text(encoding="utf-8")
    assert ".rodape {" in css
    assert ".identidade .cartilha-atalho {" in css
