"""Testes do rito de acesso: cadastro, pleito, concessão e alcance por tipo.

O que estes testes protegem: **ninguém ganha papel por se cadastrar**. O
cadastro cria a pessoa e um pedido; o papel só nasce de uma decisão de quem tem
atribuição para decidir, registrada com autor, data e resposta. E depois de
concedido, o papel vale para o que ele responde — não para o catálogo inteiro.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import apoio  # noqa: E402

from catalogo import (acesso, create_app, db as banco, governanca,  # noqa: E402
                      notificacoes, servicos)


@pytest.fixture()
def app(tmp_path):
    aplicacao = create_app({"DATABASE": str(tmp_path / "pleito.db"), "TESTING": True,
                            "SECRET_KEY": "teste"})
    with aplicacao.app_context():
        banco.init_db()
        con = banco.get_db()
        governanca.semear_politicas(con)
        con.execute("INSERT INTO squad (codigo, nome) VALUES ('SQ-1', 'Squad Crédito')")
        con.commit()
    return aplicacao


@pytest.fixture()
def elenco(app):
    with app.app_context():
        con = banco.get_db()
        yield {
            "admin": apoio.criar_pessoa(con, "Ana Admin", "admin.teste", "admin"),
            "curador": apoio.criar_pessoa(con, "Caio Curador", "curador.teste", "curador"),
            "negocio": apoio.criar_pessoa(con, "Bia Negocio", "negocio.teste", "negocio"),
        }


def pedir(app, papel="tech_lead", matricula="C123456", nome="Davi Souza",
          email="davi@empresa.com", unidade="0427", justificativa="Vou cadastrar APIs."):
    with app.app_context():
        return acesso.solicitar_acesso(banco.get_db(), matricula, nome, email,
                                       unidade, papel, justificativa)


# ------------------------------------------------------- validação do cadastro

def test_matricula_fora_do_formato_e_recusada(app):
    ruins = ["123456", "CC12345", "C12345", "C1234567", "", "C12345a", " C123456 x"]
    for matricula in ruins:
        with pytest.raises(servicos.RegraDeNegocio):
            acesso.validar_cadastro(matricula, "Davi Souza", "d@e.com", "0427")


def test_matricula_valida_em_qualquer_letra_inicial(app):
    for letra in ("C", "E", "F", "P", "X"):
        dados = acesso.validar_cadastro(f"{letra}123456", "Davi Souza", "d@e.com", "0427")
        assert dados["matricula"] == f"{letra}123456"


def test_matricula_e_normalizada_para_maiuscula(app):
    assert acesso.validar_cadastro("c123456", "Davi Souza", "d@e.com",
                                   "0427")["matricula"] == "C123456"


def test_unidade_exige_quatro_numeros(app):
    for unidade in ("427", "04277", "abcd", "", "04 7"):
        with pytest.raises(servicos.RegraDeNegocio):
            acesso.validar_cadastro("C123456", "Davi Souza", "d@e.com", unidade)
    assert acesso.validar_cadastro("C123456", "Davi Souza", "d@e.com",
                                   "0427")["unidade"] == "0427"


def test_nome_e_email_sao_conferidos(app):
    with pytest.raises(servicos.RegraDeNegocio):
        acesso.validar_cadastro("C123456", "Davi", "d@e.com", "0427")     # só um nome
    with pytest.raises(servicos.RegraDeNegocio):
        acesso.validar_cadastro("C123456", "Davi Souza", "davi", "0427")  # sem @


# ---------------------------------------------------------------- o pleito
def test_cadastro_nao_concede_papel_nenhum(app):
    """O ponto do rito: cadastrar-se não é ganhar acesso."""
    pleito = pedir(app)
    with app.app_context():
        con = banco.get_db()
        assert acesso.papeis(con, pleito["id_pessoa"]) == []
        assert acesso.pode(con, pleito["id_pessoa"], "cadastrar") is False


def test_quem_se_cadastra_consulta_o_catalogo(app):
    """Sem papel, tudo é leitura — e leitura tem de funcionar."""
    pleito = pedir(app)
    cliente = app.test_client()
    apoio.entrar(cliente, pleito["id_pessoa"])
    for rota in ("/", "/catalogo", "/mapa", "/politicas", "/cartilha"):
        assert cliente.get(rota).status_code == 200, rota


def test_pleito_nasce_pendente_com_os_dados_informados(app):
    pleito = pedir(app, papel="negocio")
    with app.app_context():
        registro = acesso.solicitacao(banco.get_db(), pleito["id_solicitacao"])
    assert registro["status"] == "pendente"
    assert registro["papel_pleiteado"] == "negocio"
    assert registro["matricula"] == "C123456"
    assert registro["unidade"] == "0427"
    assert registro["decidido_por"] is None


def test_segundo_pleito_pendente_e_recusado(app):
    pedir(app)
    with pytest.raises(servicos.RegraDeNegocio):
        pedir(app, papel="negocio")


def test_recadastro_atualiza_a_pessoa_sem_duplicar(app, elenco):
    pleito = pedir(app)
    with app.app_context():
        con = banco.get_db()
        acesso.decidir_solicitacao(con, pleito["id_solicitacao"], elenco["admin"],
                                   aprovar=True)
        de_novo = acesso.solicitar_acesso(con, "c123456", "Davi Souza Lima",
                                          "davi.lima@empresa.com", "0500", "arquiteto")
        assert de_novo["id_pessoa"] == pleito["id_pessoa"]
        pessoa = acesso.pessoa(con, pleito["id_pessoa"])
    assert pessoa["nome"] == "Davi Souza Lima"
    assert pessoa["unidade"] == "0500"


def test_quem_concede_e_avisado_do_pleito(app, elenco):
    pedir(app)
    with app.app_context():
        con = banco.get_db()
        for chave in ("admin", "curador"):
            caixa = notificacoes.caixa(con, elenco[chave])
            assert any(n["tipo"] == "acesso_solicitado" for n in caixa), chave
        assert not [n for n in notificacoes.caixa(con, elenco["negocio"])
                    if n["tipo"] == "acesso_solicitado"]


# -------------------------------------------------------------- a concessão
def test_aprovacao_concede_o_papel_e_responde(app, elenco):
    pleito = pedir(app)
    with app.app_context():
        con = banco.get_db()
        decidido = acesso.decidir_solicitacao(
            con, pleito["id_solicitacao"], elenco["curador"], aprovar=True,
            resposta="Bem-vindo.")
        assert decidido["status"] == "aprovada"
        assert decidido["papel_concedido"] == "tech_lead"
        assert acesso.pode(con, pleito["id_pessoa"], "importar") is True
        aviso = notificacoes.caixa(con, pleito["id_pessoa"])[0]
    assert aviso["tipo"] == "acesso_decidido"
    assert "Bem-vindo." in aviso["corpo"]


def test_negativa_exige_motivo_e_nao_concede_nada(app, elenco):
    pleito = pedir(app)
    with app.app_context():
        con = banco.get_db()
        with pytest.raises(servicos.RegraDeNegocio):
            acesso.decidir_solicitacao(con, pleito["id_solicitacao"],
                                       elenco["curador"], aprovar=False)
        decidido = acesso.decidir_solicitacao(
            con, pleito["id_solicitacao"], elenco["curador"], aprovar=False,
            resposta="Peça ao seu gestor primeiro.")
        assert decidido["status"] == "negada"
        assert acesso.papeis(con, pleito["id_pessoa"]) == []
        assert "gestor" in notificacoes.caixa(con, pleito["id_pessoa"])[0]["corpo"]


def test_papel_diferente_do_pleiteado_exige_explicacao(app, elenco):
    pleito = pedir(app, papel="admin")
    with app.app_context():
        con = banco.get_db()
        with pytest.raises(servicos.RegraDeNegocio):
            acesso.decidir_solicitacao(con, pleito["id_solicitacao"], elenco["admin"],
                                       aprovar=True, papel_concedido="negocio")
        decidido = acesso.decidir_solicitacao(
            con, pleito["id_solicitacao"], elenco["admin"], aprovar=True,
            papel_concedido="negocio", resposta="Admin não cabe aqui; negócio resolve.")
        assert decidido["papel_concedido"] == "negocio"


def test_concessao_com_escopo_de_dominio_nao_vale_fora_dele(app, elenco):
    pleito = pedir(app, papel="negocio")
    with app.app_context():
        con = banco.get_db()
        dentro = servicos.criar_item(con, tipo_item="dominio", nome="Crédito",
                                     usuario="admin.teste")
        fora = servicos.criar_item(con, tipo_item="dominio", nome="Logística",
                                   usuario="admin.teste")
        acesso.decidir_solicitacao(
            con, pleito["id_solicitacao"], elenco["admin"], aprovar=True,
            escopo_tipo="dominio", escopo_id=dentro,
            resposta="Só no seu domínio.")
        assert acesso.pode(con, pleito["id_pessoa"], "editar", dentro) is True
        assert acesso.pode(con, pleito["id_pessoa"], "editar", fora) is False


def test_pleito_ja_decidido_nao_se_decide_de_novo(app, elenco):
    pleito = pedir(app)
    with app.app_context():
        con = banco.get_db()
        acesso.decidir_solicitacao(con, pleito["id_solicitacao"], elenco["admin"],
                                   aprovar=True)
        with pytest.raises(servicos.RegraDeNegocio):
            acesso.decidir_solicitacao(con, pleito["id_solicitacao"], elenco["admin"],
                                       aprovar=False, resposta="mudei de ideia")


def test_ninguem_concede_acesso_a_si_mesmo(app, elenco):
    """Segregação de função também no acesso, não só na validação."""
    with app.app_context():
        con = banco.get_db()
        pessoa_admin = acesso.pessoa(con, elenco["admin"])
        con.execute("UPDATE pessoa SET matricula='A123456', unidade='0001' "
                    "WHERE id_pessoa=?", (elenco["admin"],))
        con.commit()
        meu = acesso.solicitar_acesso(con, "A123456", pessoa_admin["nome"],
                                      "ana@empresa.com", "0001", "arquiteto")
        with pytest.raises(servicos.RegraDeNegocio):
            acesso.decidir_solicitacao(con, meu["id_solicitacao"], elenco["admin"],
                                       aprovar=True)


# ----------------------------------------------------- quem pode conceder
def test_curador_concede_tudo_menos_admin(app, elenco):
    with app.app_context():
        con = banco.get_db()
        assert acesso.pode_conceder(con, elenco["curador"], "tech_lead")[0] is True
        pode, motivo = acesso.pode_conceder(con, elenco["curador"], "admin")
        assert pode is False
        assert "administrador" in motivo.lower()
        assert acesso.pode_conceder(con, elenco["admin"], "admin")[0] is True


def test_quem_nao_concede_nao_entra_na_fila(app, elenco):
    with app.app_context():
        assert acesso.pode_conceder(banco.get_db(), elenco["negocio"])[0] is False
    cliente = app.test_client()
    apoio.entrar(cliente, elenco["negocio"])
    assert cliente.get("/acessos").status_code in (302, 303)


def test_curador_que_tenta_conceder_admin_pela_rota_e_recusado(app, elenco):
    pleito = pedir(app, papel="admin")
    with app.app_context():
        con = banco.get_db()
        with pytest.raises(acesso.SemPermissao):
            acesso.decidir_solicitacao(con, pleito["id_solicitacao"],
                                       elenco["curador"], aprovar=True)


# ------------------------------------------- alcance do papel por tipo de ativo
def test_negocio_nao_cadastra_ativo_tecnico(app, elenco):
    """O papel autoriza a ação e também o objeto: era o furo antigo."""
    with app.app_context():
        con = banco.get_db()
        assert acesso.pode(con, elenco["negocio"], "cadastrar",
                           tipo_item="dominio") is True
        assert acesso.pode(con, elenco["negocio"], "cadastrar",
                           tipo_item="api") is False


def test_tech_lead_nao_redesenha_a_hierarquia_de_negocio(app, elenco):
    with app.app_context():
        con = banco.get_db()
        tech = apoio.criar_pessoa(con, "Tina Tech", "tech.teste", "tech_lead")
        assert acesso.pode(con, tech, "cadastrar", tipo_item="api") is True
        assert acesso.pode(con, tech, "cadastrar", tipo_item="dominio") is False


def test_arquiteto_e_curador_atravessam_os_dois_blocos(app, elenco):
    with app.app_context():
        con = banco.get_db()
        arq = apoio.criar_pessoa(con, "Artur Arq", "arq.teste", "arquiteto")
        for quem in (arq, elenco["curador"], elenco["admin"]):
            for tipo_item in ("dominio", "api"):
                assert acesso.pode(con, quem, "cadastrar", tipo_item=tipo_item), tipo_item


def test_edicao_de_ativo_existente_respeita_o_bloco(app, elenco):
    with app.app_context():
        con = banco.get_db()
        api = servicos.criar_item(con, tipo_item="api", nome="API de Crédito",
                                  usuario="admin.teste")
        assert acesso.pode(con, elenco["negocio"], "editar", api) is False


def test_rota_de_cadastro_recusa_tipo_fora_do_papel(app, elenco):
    cliente = app.test_client()
    apoio.entrar(cliente, elenco["negocio"])
    resposta = cliente.post("/ativo/novo", data={
        "acao": "salvar", "tipo_item": "api", "nome": "API pirata"}, follow_redirects=True)
    assert resposta.status_code == 200
    with app.app_context():
        achados = banco.get_db().execute(
            "SELECT COUNT(*) c FROM item_catalogo WHERE nome = 'API pirata'").fetchone()
    assert achados["c"] == 0


def test_wizard_so_oferece_os_blocos_do_papel(app, elenco):
    cliente = app.test_client()
    apoio.entrar(cliente, elenco["negocio"])
    html = cliente.get("/ativo/novo").get_data(as_text=True)
    assert "Estrutura DDD" in html
    assert "Ativos técnicos" not in html


def test_sem_papel_o_wizard_manda_pleitear(app):
    pleito = pedir(app)
    cliente = app.test_client()
    apoio.entrar(cliente, pleito["id_pessoa"])
    html = cliente.get("/ativo/novo").get_data(as_text=True)
    assert "/acesso/solicitar" in html


# --------------------------------------------------------------- as telas
def test_tela_de_cadastro_abre_sem_identificacao(app):
    cliente = app.test_client()
    html = cliente.get("/acesso/solicitar").get_data(as_text=True)
    assert 'name="matricula"' in html
    assert 'name="unidade"' in html
    assert 'name="papel_pleiteado"' in html


def test_cadastro_pela_tela_identifica_a_pessoa_na_hora(app):
    cliente = app.test_client()
    cliente.post("/acesso/solicitar", data={
        "matricula": "P654321", "nome": "Eva Lima", "email": "eva@empresa.com",
        "unidade": "0310", "papel_pleiteado": "negocio",
        "justificativa": "Respondo pelo domínio de Crédito."}, follow_redirects=True)
    with cliente.session_transaction() as sessao:
        assert sessao.get("id_pessoa")
    html = cliente.get("/perfil").get_data(as_text=True)
    assert "aguardando decisão" in html


def test_fila_mostra_o_pleito_a_quem_concede(app, elenco):
    pedir(app)
    cliente = app.test_client()
    apoio.entrar(cliente, elenco["curador"])
    html = cliente.get("/acessos").get_data(as_text=True)
    assert "Davi Souza" in html
    assert "C123456" in html
    assert "Vou cadastrar APIs." in html


def test_fila_nao_oferece_admin_a_curador(app, elenco):
    pedir(app, papel="admin")
    cliente = app.test_client()
    apoio.entrar(cliente, elenco["curador"])
    html = cliente.get("/acessos").get_data(as_text=True)
    assert 'value="admin"' not in html
    apoio.entrar(cliente, elenco["admin"])
    assert 'value="admin"' in cliente.get("/acessos").get_data(as_text=True)


def test_decisao_pela_tela_concede_e_aparece_no_perfil(app, elenco):
    pleito = pedir(app)
    cliente = app.test_client()
    apoio.entrar(cliente, elenco["admin"])
    cliente.post(f"/acessos/{pleito['id_solicitacao']}/decidir",
                 data={"decisao": "aprovar", "papel_concedido": "tech_lead",
                       "escopo_tipo": "global", "resposta": "Ok."},
                 follow_redirects=True)
    apoio.entrar(cliente, pleito["id_pessoa"])
    html = cliente.get("/perfil").get_data(as_text=True)
    assert "aprovado" in html
    assert "Time técnico" in html


def test_menu_so_mostra_a_fila_para_quem_concede(app, elenco):
    cliente = app.test_client()
    apoio.entrar(cliente, elenco["curador"])
    assert "Pleitos de acesso" in cliente.get("/").get_data(as_text=True)
    apoio.entrar(cliente, elenco["negocio"])
    assert "Pleitos de acesso" not in cliente.get("/").get_data(as_text=True)
