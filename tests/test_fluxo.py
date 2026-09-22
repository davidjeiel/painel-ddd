"""Testes da onda 2 de navegação: fluxo de trabalho.

Abas da visão 360°, checklist vivo até a publicação, loop de decisão do
validador, mesa de trabalho pessoal e o formulário de relações com mecanismo.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import apoio  # noqa: E402

from catalogo import create_app, db as banco, governanca, servicos, tipos  # noqa: E402


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
        con.execute("INSERT INTO pessoa (matricula, nome, perfil) "
                    "VALUES ('M2', 'Bruno Técnico', 'tech_lead')")
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


def montar_capacidade(con, usuario="curador.demo"):
    dom = servicos.criar_item(con, tipo_item="dominio", nome="Contrato",
                              descricao="Domínio de contratos", usuario=usuario,
                              atributos={"visao": "Sustentar contratos"})
    sub = servicos.criar_item(con, tipo_item="subdominio", nome="Originação",
                              descricao="Formalização", id_pai=dom, usuario=usuario,
                              atributos={"classificacao": "core"})
    ctx = servicos.criar_item(con, tipo_item="contexto", nome="Simulação",
                              descricao="Cálculo de condições", id_pai=sub, usuario=usuario,
                              atributos={"linguagem_ubiqua": "Simulação"})
    cap = servicos.criar_item(con, tipo_item="capacidade", nome="Simular Financiamento",
                              descricao="Calcula condições", id_pai=ctx, usuario=usuario,
                              atributos={"resultado_esperado": "Proposta simulada"})
    return dom, sub, ctx, cap


def completar(con, cap, usuario="curador.demo"):
    """Leva a capacidade ao estado em que o pré-check aprova."""
    servicos.definir_responsavel(con, cap, 1, "owner_negocial", usuario)
    servicos.definir_responsavel(con, cap, 2, "owner_tecnico", usuario)
    servicos.anexar_evidencia(con, cap, "documento", "Política de crédito", usuario=usuario)
    sis = servicos.criar_item(con, tipo_item="sistema", nome="Plataforma",
                              descricao="Sistema", usuario=usuario,
                              atributos={"plataforma": "nuvem"})
    aplic = servicos.criar_item(con, tipo_item="aplicacao", nome="Motor",
                                descricao="Serviço de cálculo", id_pai=sis, usuario=usuario,
                                atributos={"tecnologia": "Python"})
    servicos.relacionar(con, aplic, cap, "implementa", usuario=usuario)
    return aplic


# ------------------------------------------------------------------------ P07
def test_visao_360_abre_no_resumo_e_esconde_as_outras_abas(app, cliente):
    with app.app_context():
        _, _, _, cap = montar_capacidade(banco.get_db())
    html = cliente.get(f"/ativo/{cap}").get_data(as_text=True)
    assert 'id="painel-resumo"' in html
    assert '<section class="painel-aba" id="painel-relacoes" hidden>' in html
    assert '<section class="painel-aba" id="painel-pessoas" hidden>' in html


def test_aba_escolhida_e_a_que_abre(app, cliente):
    with app.app_context():
        _, _, _, cap = montar_capacidade(banco.get_db())
    html = cliente.get(f"/ativo/{cap}?aba=evidencias").get_data(as_text=True)
    assert '<section class="painel-aba" id="painel-evidencias" >' in html
    assert '<section class="painel-aba" id="painel-resumo" hidden>' in html
    assert 'aria-selected="true"' in html


def test_aba_desconhecida_cai_no_resumo(app, cliente):
    with app.app_context():
        _, _, _, cap = montar_capacidade(banco.get_db())
    html = cliente.get(f"/ativo/{cap}?aba=inventada").get_data(as_text=True)
    assert '<section class="painel-aba" id="painel-resumo" >' in html


def test_escrita_volta_para_a_aba_de_origem(app, cliente):
    with app.app_context():
        _, _, _, cap = montar_capacidade(banco.get_db())
    resposta = cliente.post(f"/ativo/{cap}/responsavel",
                            data={"id_pessoa": "1", "papel": "owner_negocial"})
    assert resposta.headers["Location"].endswith(f"/ativo/{cap}?aba=pessoas")


# ------------------------------------------------------------------------ P08
def test_checklist_reflete_o_que_falta(app):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar_capacidade(con)
        caminho = governanca.caminho_publicacao(con, cap)
    por_chave = {p["chave"]: p for p in caminho["passos"]}
    assert por_chave["descrever"]["ok"]                 # descrição e campos preenchidos
    assert not por_chave["responsaveis"]["ok"]          # falta owner negocial e técnico
    assert not por_chave["evidenciar"]["ok"]            # política exige 1 evidência
    assert caminho["concluidos"] < caminho["total"]
    assert not caminho["aprovado"]


def test_checklist_fica_completo_quando_o_precheck_aprova(app):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar_capacidade(con)
        completar(con, cap)
        caminho = governanca.caminho_publicacao(con, cap)
        checagem = governanca.pre_check(con, cap)
    assert checagem["aprovado"]
    assert caminho["aprovado"]
    assert caminho["concluidos"] == caminho["total"]
    assert all(p["ok"] for p in caminho["passos"])


def test_todo_bloqueio_do_precheck_cai_em_algum_passo(app):
    """O checklist não pode esconder um impedimento que a submissão vai levantar."""
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar_capacidade(con)
        con.execute("UPDATE item_catalogo SET descricao = '', atributos = '{}' "
                    "WHERE id_item = ?", (cap,))
        con.commit()
        checagem = governanca.pre_check(con, cap)
        caminho = governanca.caminho_publicacao(con, cap, checagem)
    mostrados = [f for p in caminho["passos"] for f in p["pendencias"]]
    assert sorted(mostrados) == sorted(checagem["bloqueios"])
    assert len(checagem["codigos"]) == len(checagem["bloqueios"])


def test_checklist_aparece_no_rascunho_e_some_no_publicado(app, cliente):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar_capacidade(con)
    assert "Caminho até a publicação" in cliente.get(f"/ativo/{cap}").get_data(as_text=True)
    with app.app_context():
        con = banco.get_db()
        con.execute("UPDATE item_catalogo SET status_ciclo_vida = 'publicado' "
                    "WHERE id_item = ?", (cap,))
        con.commit()
    assert "Caminho até a publicação" not in cliente.get(f"/ativo/{cap}").get_data(as_text=True)


def test_wizard_antecipa_o_rito_do_tipo(cliente):
    html = cliente.get("/ativo/novo?tipo_item=api&criticidade=critica").get_data(as_text=True)
    assert "Rito de publicação" in html
    assert "negocial → tecnica → arquitetural" in html   # política de api crítica
    assert "80%" in html


# ------------------------------------------------------------------------ P09
def _submeter(app, usuario="curador.demo"):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar_capacidade(con, usuario)
        completar(con, cap, usuario)
        servicos.submeter(con, cap, "Publicação inicial", usuario)
        vals = [l["id_validacao"] for l in con.execute(
            "SELECT id_validacao FROM validacao WHERE id_item = ? "
            "AND situacao = 'pendente' ORDER BY id_validacao", (cap,))]
    return cap, vals


def test_painel_do_validador_mostra_evidencias_e_responsaveis(app, cliente):
    cap, vals = _submeter(app)
    html = cliente.get(f"/validacoes?id_validacao={vals[0]}").get_data(as_text=True)
    assert "Política de crédito" in html          # evidência anexada
    assert "Ana Negócio" in html                  # responsável
    assert "Primeira revisão deste ativo" in html  # não há anterior para comparar


def test_painel_mostra_o_que_mudou_na_segunda_revisao(app, cliente):
    cap, vals = _submeter(app)
    with app.app_context():
        con = banco.get_db()
        for v in vals:
            servicos.decidir_validacao(con, v, True, "ok")
        servicos.abrir_revisao(con, cap, "curador.demo")
        servicos.atualizar_item(con, cap, {"descricao": "Calcula condições e taxas"},
                                "curador.demo")
        servicos.submeter(con, cap, "Ajuste de escopo", "curador.demo")
        nova = con.execute("SELECT id_validacao FROM validacao WHERE id_item = ? "
                           "AND situacao = 'pendente' ORDER BY id_validacao", (cap,)).fetchone()
    html = cliente.get(f"/validacoes?id_validacao={nova['id_validacao']}").get_data(as_text=True)
    assert "O que mudou" in html and "revisão #2" in html
    assert "Calcula condições e taxas" in html
    assert 'class="antes"' in html
    assert "Descrição" in html          # rótulo legível, não o nome da coluna
    assert "revisao_atual" not in html  # campo mecânico fica fora do resumo


def test_decidir_preserva_a_etapa_e_segue_para_a_proxima(app, cliente):
    cap, vals = _submeter(app)
    with app.app_context():
        con = banco.get_db()
        etapa = con.execute("SELECT etapa FROM validacao WHERE id_validacao = ?",
                            (vals[0],)).fetchone()["etapa"]
        outra_mesma_etapa = con.execute(
            "SELECT id_validacao FROM validacao WHERE etapa = ? AND situacao = 'pendente' "
            "AND id_validacao <> ?", (etapa, vals[0])).fetchone()
    resposta = cliente.post(f"/validacoes/{vals[0]}/decidir",
                            data={"decisao": "aprovar", "parecer": "ok",
                                  "etapa": etapa, "seguir": "1"})
    destino = resposta.headers["Location"]
    assert f"etapa={etapa}" in destino
    if outra_mesma_etapa:
        assert f"id_validacao={outra_mesma_etapa['id_validacao']}" in destino


def test_decidir_sem_seguir_nao_seleciona_ninguem(app, cliente):
    cap, vals = _submeter(app)
    resposta = cliente.post(f"/validacoes/{vals[0]}/decidir",
                            data={"decisao": "aprovar", "parecer": "ok", "etapa": "tecnica"})
    assert "id_validacao" not in resposta.headers["Location"]
    assert "etapa=tecnica" in resposta.headers["Location"]


def test_abas_da_fila_mostram_a_contagem(app, cliente):
    _submeter(app)
    html = cliente.get("/validacoes").get_data(as_text=True)
    assert 'class="conta"' in html


# ------------------------------------------------------------------------ P10
def test_assumir_e_liberar_uma_validacao(app):
    cap, vals = _submeter(app)
    with app.app_context():
        con = banco.get_db()
        assert governanca.assumir_validacao(con, vals[0], "ana")["assumida"]
        recusa = governanca.assumir_validacao(con, vals[0], "bruno")
        assert not recusa["assumida"] and "ana" in recusa["motivo"]
        assert [v["id_validacao"] for v in governanca.fila_validacao(con, atribuido_a="ana")] == [vals[0]]
        assert vals[0] not in [v["id_validacao"]
                               for v in governanca.fila_validacao(con, apenas_livres=True)]
        governanca.liberar_validacao(con, vals[0], "ana")
        assert vals[0] in [v["id_validacao"]
                           for v in governanca.fila_validacao(con, apenas_livres=True)]


def test_minha_mesa_separa_o_que_e_meu(app):
    cap, vals = _submeter(app, "curador.demo")
    with app.app_context():
        con = banco.get_db()
        servicos.criar_item(con, tipo_item="dominio", nome="Garantias",
                            descricao="Outro domínio", usuario="outra.pessoa",
                            atributos={"visao": "Reduzir risco"})
        governanca.assumir_validacao(con, vals[0], "curador.demo")
        mesa = servicos.minha_mesa(con, "curador.demo")
    assert [v["id_validacao"] for v in mesa["minhas_validacoes"]] == [vals[0]]
    assert vals[0] not in [v["id_validacao"] for v in mesa["fila_livre"]]
    assert "Garantias" not in [i["nome"] for i in mesa["meus_rascunhos"]]
    assert "Simular Financiamento" in [i["nome"] for i in mesa["aguardando_decisao"]]


def test_tela_da_mesa_responde_e_entra_no_menu(app, cliente):
    _submeter(app)
    html = cliente.get("/meu-trabalho").get_data(as_text=True)
    assert "Minha mesa" in html
    assert 'href="/meu-trabalho" class="ativo" aria-current="page"' in html
    assert "Fila livre" in html


def test_migracao_cria_a_coluna_em_banco_antigo(app):
    """Banco criado antes da onda 2 recebe atribuido_a sem perder dados.

    No dialeto anterior dava para forjar a tabela antiga do zero. Aqui a base é
    compartilhada pela sessão, então o estado anterior é simulado removendo a
    coluna — o que se quer provar é o mecanismo do ALTER, não como ele chegou lá.
    """
    with app.app_context():
        con = banco.get_db()
        con.execute("INSERT INTO validacao (id_item, etapa) VALUES (NULL, 'tecnica')")
        con.execute("ALTER TABLE validacao DROP COLUMN atribuido_a")
        con.commit()
        assert banco.migrar(con) == ["validacao.atribuido_a"]
        assert con.execute(
            "SELECT atribuido_a FROM validacao").fetchone()["atribuido_a"] is None
        assert banco.migrar(con) == []          # idempotente


# ------------------------------------------------------------------------ P11
def test_formulario_de_relacao_oferece_mecanismo(app, cliente):
    with app.app_context():
        _, _, _, cap = montar_capacidade(banco.get_db())
    html = cliente.get(f"/ativo/{cap}?aba=relacoes").get_data(as_text=True)
    assert 'name="mecanismo"' in html
    assert "Assíncrono (evento/fila)" in html
    assert 'id="destino-busca"' in html      # combobox no lugar do select gigante


def test_mecanismo_chega_ao_banco(app, cliente):
    with app.app_context():
        con = banco.get_db()
        _, _, ctx, cap = montar_capacidade(con)
        aplic = completar(con, cap)
    cliente.post(f"/ativo/{aplic}/relacao", data={
        "tipo_relacao": "consome", "id_destino": str(ctx),
        "mecanismo": "assincrono", "criticidade": "alta"})
    with app.app_context():
        linha = banco.get_db().execute(
            "SELECT mecanismo, criticidade FROM relacionamento_ativo "
            "WHERE id_origem = ? AND id_destino = ?", (aplic, ctx)).fetchone()
    assert linha["mecanismo"] == "assincrono"
    assert linha["criticidade"] == "alta"


def test_relacao_sem_destino_avisa_em_vez_de_quebrar(app, cliente):
    with app.app_context():
        _, _, _, cap = montar_capacidade(banco.get_db())
    resposta = cliente.post(f"/ativo/{cap}/relacao",
                            data={"tipo_relacao": "consome", "id_destino": ""},
                            follow_redirects=True)
    assert resposta.status_code == 200
    assert "Escolha um ativo de destino" in resposta.get_data(as_text=True)


def test_destinos_sugeridos_cobrem_todas_as_relacoes(app):
    """A lista que filtra o combobox não pode deixar uma relação sem sugestão."""
    assert set(tipos.DESTINOS_SUGERIDOS) == set(tipos.RELACOES)
    conhecidos = set(tipos.TIPOS)
    for relacao, destinos in tipos.DESTINOS_SUGERIDOS.items():
        assert destinos, relacao
        assert set(destinos) <= conhecidos, relacao
