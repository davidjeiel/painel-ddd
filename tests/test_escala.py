"""Testes da onda 3: escala e o time técnico.

Descoberta automática com prévia e bandeja de triagem, relações em lote,
catálogo paginado e ordenável, as duas árvores do mapa e a análise de impacto.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import apoio  # noqa: E402

from catalogo import (create_app, db as banco, governanca, integracoes,  # noqa: E402
                      servicos)

CONTRATO = json.dumps({
    "info": {"title": "API Simulação", "version": "2.1",
             "description": "Simulação de financiamento"},
    "paths": {
        "/simulacoes": {"post": {"summary": "Cria uma simulação"},
                        "get": {"summary": "Lista simulações"}},
        "/simulacoes/{id}": {"get": {"summary": "Consulta uma simulação"},
                             "options": {"summary": "Ignorado: método fora da lista"}},
    },
})

INVENTARIO = json.dumps([
    {"nome": "motor-simulacao", "url": "https://git.interno/motor", "linguagem": "Python"},
    {"nome": "portal-credito", "url": "https://git.interno/portal", "linguagem": "TypeScript"},
])


@pytest.fixture()
def app(tmp_path):
    aplicacao = create_app({"DATABASE": str(tmp_path / "escala.db"), "TESTING": True,
                            "SECRET_KEY": "teste"})
    with aplicacao.app_context():
        banco.init_db()
        con = banco.get_db()
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


def montar_tecnico(con):
    """Sistema → Aplicação, o pai natural dos ativos descobertos."""
    sis = servicos.criar_item(con, tipo_item="sistema", nome="Plataforma de Crédito",
                              descricao="Sistema", atributos={"plataforma": "nuvem"})
    aplic = servicos.criar_item(con, tipo_item="aplicacao", nome="Motor de Simulação",
                                descricao="Serviço", id_pai=sis,
                                atributos={"tecnologia": "Python"})
    return sis, aplic


def montar_negocio(con):
    dom = servicos.criar_item(con, tipo_item="dominio", nome="Contrato",
                              descricao="Domínio", atributos={"visao": "Sustentar"})
    sub = servicos.criar_item(con, tipo_item="subdominio", nome="Originação",
                              descricao="Formalização", id_pai=dom,
                              atributos={"classificacao": "core"})
    ctx = servicos.criar_item(con, tipo_item="contexto", nome="Simulação",
                              descricao="Cálculo", id_pai=sub)
    cap = servicos.criar_item(con, tipo_item="capacidade", nome="Simular Financiamento",
                              descricao="Calcula", id_pai=ctx,
                              atributos={"resultado_esperado": "Proposta"})
    return dom, sub, ctx, cap


# ------------------------------------------------------------------------ P12
def test_previa_do_openapi_nao_escreve_nada(app):
    with app.app_context():
        con = banco.get_db()
        _, aplic = montar_tecnico(con)
        antes = servicos.contar(con)
        plano = integracoes.plano_openapi(con, id_aplicacao=aplic, conteudo=CONTRATO)
        assert servicos.contar(con) == antes
    assert plano["titulo"] == "API Simulação"
    assert plano["criar"] == 4          # a API e três operações válidas
    assert plano["manter"] == 0
    nomes = [a["nome"] for a in plano["acoes"]]
    assert "GET /simulacoes" in nomes
    assert not any("OPTIONS" in n for n in nomes)   # método fora da lista


def test_previa_marca_o_que_ja_existe(app):
    with app.app_context():
        con = banco.get_db()
        _, aplic = montar_tecnico(con)
        integracoes.importar_openapi(con, id_aplicacao=aplic, conteudo=CONTRATO)
        plano = integracoes.plano_openapi(con, id_aplicacao=aplic, conteudo=CONTRATO)
    assert plano["criar"] == 0
    assert plano["manter"] == 4


def test_importacao_marca_a_origem_e_cai_na_bandeja(app):
    with app.app_context():
        con = banco.get_db()
        _, aplic = montar_tecnico(con)
        integracoes.importar_openapi(con, id_aplicacao=aplic, conteudo=CONTRATO,
                                     usuario="integracao")
        bandeja = servicos.descobertas(con)
        manuais = servicos.buscar(con, origem="manual")
    assert {i["nome"] for i in bandeja} >= {"API Simulação", "GET /simulacoes"}
    assert all(i["origem"] == "automatica" for i in bandeja)
    assert all(i["status_ciclo_vida"] == "rascunho" for i in bandeja)
    assert "Motor de Simulação" in [i["nome"] for i in manuais]  # cadastro humano intacto


def test_inventario_git_tambem_entra_na_bandeja(app):
    with app.app_context():
        con = banco.get_db()
        _, aplic = montar_tecnico(con)
        plano = integracoes.plano_repositorios(con, id_aplicacao=aplic, conteudo=INVENTARIO)
        integracoes.importar_repositorios(con, id_aplicacao=aplic, conteudo=INVENTARIO)
        bandeja = [i["nome"] for i in servicos.descobertas(con)]
    assert plano["criar"] == 2
    assert "motor-simulacao" in bandeja and "portal-credito" in bandeja


def test_tela_de_descobertas_mostra_previa_antes_de_gravar(app, cliente):
    with app.app_context():
        con = banco.get_db()
        _, aplic = montar_tecnico(con)
        antes = servicos.contar(con)
    resposta = cliente.post("/descobertas", data={
        "fonte": "openapi", "acao": "previa", "conteudo": CONTRATO, "id_pai": str(aplic)})
    html = resposta.get_data(as_text=True)
    assert "API Simulação" in html and "4 a criar" in html
    with app.app_context():
        assert servicos.contar(banco.get_db()) == antes   # prévia não gravou


def test_tela_de_descobertas_importa_ao_confirmar(app, cliente):
    with app.app_context():
        con = banco.get_db()
        _, aplic = montar_tecnico(con)
    cliente.post("/descobertas", data={
        "fonte": "openapi", "acao": "importar", "conteudo": CONTRATO,
        "id_pai": str(aplic)}, follow_redirects=True)
    with app.app_context():
        bandeja = [i["nome"] for i in servicos.descobertas(banco.get_db())]
    assert "API Simulação" in bandeja


def test_json_invalido_avisa_em_vez_de_quebrar(app, cliente):
    resposta = cliente.post("/descobertas", data={
        "fonte": "openapi", "acao": "previa", "conteudo": "{isto não é json"})
    assert resposta.status_code == 200
    assert "Não consegui ler esse conteúdo" in resposta.get_data(as_text=True)


def test_triagem_aceita_e_descarta(app):
    with app.app_context():
        con = banco.get_db()
        _, aplic = montar_tecnico(con)
        integracoes.importar_openapi(con, id_aplicacao=aplic, conteudo=CONTRATO)
        bandeja = servicos.descobertas(con)
        aceitar, descartar = bandeja[0]["id_item"], bandeja[1]["id_item"]

        assert servicos.triar(con, [aceitar], "aceitar")["tratados"] == 1
        assert servicos.triar(con, [descartar], "descartar")["tratados"] == 1
        restantes = [i["id_item"] for i in servicos.descobertas(con)]
        aceito = con.execute("SELECT origem, status_ciclo_vida FROM item_catalogo "
                             "WHERE id_item = ?", (aceitar,)).fetchone()
        jogado = con.execute("SELECT status_ciclo_vida FROM item_catalogo "
                             "WHERE id_item = ?", (descartar,)).fetchone()
    assert aceitar not in restantes and descartar not in restantes
    assert aceito["origem"] == "manual"                  # segue no catálogo
    assert aceito["status_ciclo_vida"] == "rascunho"     # sem mexer no ciclo de vida
    assert jogado["status_ciclo_vida"] == "arquivado"


def test_triagem_nao_toca_em_cadastro_humano(app):
    with app.app_context():
        con = banco.get_db()
        sis, _ = montar_tecnico(con)
        resultado = servicos.triar(con, [sis], "descartar")
        status = con.execute("SELECT status_ciclo_vida FROM item_catalogo "
                             "WHERE id_item = ?", (sis,)).fetchone()
    assert resultado["tratados"] == 0
    assert status["status_ciclo_vida"] == "rascunho"


def test_triagem_recusa_acao_desconhecida(app):
    with app.app_context():
        with pytest.raises(servicos.RegraDeNegocio):
            servicos.triar(banco.get_db(), [1], "apagar")


# ------------------------------------------------------------------------ P13
def test_lote_cria_varias_e_ignora_as_existentes(app):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar_negocio(con)
        _, aplic = montar_tecnico(con)
        integracoes.importar_openapi(con, id_aplicacao=aplic, conteudo=CONTRATO)
        endpoints = [i["id_item"] for i in servicos.buscar(con, tipo_item="endpoint")]

        primeiro = servicos.relacionar_em_lote(con, aplic, endpoints, "expoe",
                                               mecanismo="sincrono")
        repetido = servicos.relacionar_em_lote(con, aplic, endpoints, "expoe")
        mecanismos = [l["mecanismo"] for l in con.execute(
            "SELECT mecanismo FROM relacionamento_ativo WHERE id_origem = ?", (aplic,))]
    assert primeiro["criadas"] == len(endpoints)
    assert repetido["criadas"] == 0 and repetido["ignoradas"] == len(endpoints)
    assert set(mecanismos) == {"sincrono"}


def test_lote_ignora_o_proprio_ativo(app):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar_negocio(con)
        _, aplic = montar_tecnico(con)
        resultado = servicos.relacionar_em_lote(con, aplic, [aplic, cap], "implementa")
    assert resultado["criadas"] == 1 and resultado["ignoradas"] == 1


def test_tela_de_lote_marca_o_que_ja_existe(app, cliente):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar_negocio(con)
        _, aplic = montar_tecnico(con)
        servicos.relacionar(con, aplic, cap, "implementa")
    html = cliente.get(f"/ativo/{aplic}/relacoes-lote?tipo_relacao=implementa").get_data(as_text=True)
    assert "checked disabled" in html
    assert "já relacionado" in html


def test_post_do_lote_volta_para_a_aba_de_relacoes(app, cliente):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar_negocio(con)
        _, aplic = montar_tecnico(con)
    resposta = cliente.post(f"/ativo/{aplic}/relacoes-lote",
                            data={"tipo_relacao": "implementa", "destino": str(cap),
                                  "mecanismo": "batch", "criticidade": "alta"})
    assert resposta.headers["Location"].endswith(f"/ativo/{aplic}?aba=relacoes")
    with app.app_context():
        linha = banco.get_db().execute(
            "SELECT mecanismo, criticidade FROM relacionamento_ativo "
            "WHERE id_origem = ? AND id_destino = ?", (aplic, cap)).fetchone()
    assert linha["mecanismo"] == "batch" and linha["criticidade"] == "alta"


# ------------------------------------------------------------------------ P14
def _muitos(con, quantos=57):
    sis = servicos.criar_item(con, tipo_item="sistema", nome="Base",
                              descricao="Sistema", atributos={"plataforma": "nuvem"})
    for n in range(quantos):
        servicos.criar_item(con, tipo_item="aplicacao", nome=f"Aplicação {n:03d}",
                            descricao="gerada", id_pai=sis,
                            atributos={"tecnologia": "Python"})
    return sis


def test_pagina_traz_o_total_real_e_nao_o_tamanho_da_pagina(app):
    with app.app_context():
        con = banco.get_db()
        _muitos(con, 57)
        pagina = servicos.buscar_pagina(con, pagina=1, por_pagina=50,
                                        tipo_item="aplicacao")
        ultima = servicos.buscar_pagina(con, pagina=2, por_pagina=50,
                                        tipo_item="aplicacao")
    assert pagina["total"] == 57 and pagina["paginas"] == 2
    assert len(pagina["itens"]) == 50 and pagina["primeiro"] == 1 and pagina["ultimo"] == 50
    assert len(ultima["itens"]) == 7 and ultima["ultimo"] == 57


def test_pagina_fora_do_intervalo_volta_para_a_ultima(app):
    with app.app_context():
        con = banco.get_db()
        _muitos(con, 10)
        pagina = servicos.buscar_pagina(con, pagina=99, por_pagina=50)
    assert pagina["pagina"] == pagina["paginas"]


def test_ordenacao_por_score_e_por_nome(app):
    with app.app_context():
        con = banco.get_db()
        montar_negocio(con)
        nomes = [i["nome"] for i in servicos.buscar(con, ordenar="nome")]
        invertido = [i["nome"] for i in servicos.buscar(con, ordenar="nome",
                                                        descendente=True)]
        criticidade = servicos.buscar(con, ordenar="criticidade")
    assert nomes == sorted(nomes)
    assert invertido == list(reversed(nomes))
    assert criticidade      # ordenação por criticidade não quebra a consulta


def test_ordenacao_desconhecida_cai_no_padrao(app, cliente):
    with app.app_context():
        montar_negocio(banco.get_db())
    assert cliente.get("/catalogo?ordenar=DROP+TABLE").status_code == 200


def test_catalogo_mostra_total_e_paginacao(app, cliente):
    with app.app_context():
        _muitos(banco.get_db(), 57)
    html = cliente.get("/catalogo?tipo_item=aplicacao").get_data(as_text=True)
    assert "<strong>57</strong> ativo(s)" in html   # total real, não o da página
    assert "Mostrando 1–50" in html
    assert "Página 1 de 2" in html and "Próxima" in html


def test_filtro_de_origem_separa_o_que_a_maquina_trouxe(app, cliente):
    with app.app_context():
        con = banco.get_db()
        _, aplic = montar_tecnico(con)
        integracoes.importar_openapi(con, id_aplicacao=aplic, conteudo=CONTRATO)
    html = cliente.get("/catalogo?origem=automatica").get_data(as_text=True)
    assert ">API Simulação</a>" in html
    # a aplicação cadastrada à mão sai da lista (ainda aparece como pai, em texto)
    assert ">Motor de Simulação</a>" not in html
    assert "descoberta automática" in html   # chip do filtro ativo


# ------------------------------------------------------------------------ P15
def test_arvore_de_negocio_desce_quatro_niveis(app):
    with app.app_context():
        con = banco.get_db()
        montar_negocio(con)
        raizes = servicos.arvore(con, "dominio")
    assert [r["nome"] for r in raizes] == ["Contrato"]
    sub = raizes[0]["filhos"][0]
    ctx = sub["filhos"][0]
    assert sub["nome"] == "Originação" and ctx["nome"] == "Simulação"
    assert ctx["filhos"][0]["nome"] == "Simular Financiamento"


def test_arvore_tecnica_usa_a_mesma_mecanica(app):
    with app.app_context():
        con = banco.get_db()
        _, aplic = montar_tecnico(con)
        integracoes.importar_openapi(con, id_aplicacao=aplic, conteudo=CONTRATO)
        raizes = servicos.arvore(con, "sistema")
    aplicacao = raizes[0]["filhos"][0]
    api = aplicacao["filhos"][0]
    assert raizes[0]["nome"] == "Plataforma de Crédito"
    assert api["nome"] == "API Simulação"
    assert len(api["filhos"]) == 3          # os endpoints descobertos


def test_arvore_conta_implementacoes_da_capacidade(app):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar_negocio(con)
        _, aplic = montar_tecnico(con)
        servicos.relacionar(con, aplic, cap, "implementa")
        raizes = servicos.arvore(con, "dominio")
    capacidade = raizes[0]["filhos"][0]["filhos"][0]["filhos"][0]
    assert capacidade["implementacoes"] == 1


def test_mapa_tem_as_duas_visoes(app, cliente):
    with app.app_context():
        con = banco.get_db()
        montar_negocio(con)
        montar_tecnico(con)
    negocio = cliente.get("/mapa").get_data(as_text=True)
    tecnica = cliente.get("/mapa?visao=tecnica").get_data(as_text=True)
    assert "Contrato" in negocio and "Plataforma de Crédito" not in negocio
    assert "Plataforma de Crédito" in tecnica
    assert 'id="filtro-arvore"' in negocio    # busca dentro da árvore


# ------------------------------------------------------------------------ P16
def test_analise_agrupa_os_consumidores(app):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar_negocio(con)
        sis, aplic = montar_tecnico(con)
        outra = servicos.criar_item(con, tipo_item="aplicacao", nome="Portal",
                                    descricao="App", id_pai=sis,
                                    atributos={"tecnologia": "React"})
        servicos.relacionar(con, aplic, cap, "implementa", criticidade="critica")
        servicos.relacionar(con, outra, cap, "consome", criticidade="baixa")
        con.execute("UPDATE item_catalogo SET status_ciclo_vida = 'publicado' "
                    "WHERE id_item IN (?, ?)", (aplic, outra))
        con.commit()
        analise = servicos.analise_impacto(con, cap)
    assert analise["total"] == 2
    assert analise["por_tipo"] == {"aplicacao": 2}
    assert analise["por_criticidade"] == {"critica": 1, "baixa": 1}
    assert [c["nome"] for c in analise["criticos"]] == ["Motor de Simulação"]


def test_tela_mostra_quem_depende_antes_de_descontinuar(app, cliente):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar_negocio(con)
        _, aplic = montar_tecnico(con)
        servicos.relacionar(con, aplic, cap, "implementa", criticidade="critica")
        con.execute("UPDATE item_catalogo SET status_ciclo_vida = 'publicado' "
                    "WHERE id_item IN (?, ?)", (aplic, cap))
        con.commit()
    html = cliente.get(f"/ativo/{cap}?aba=relacoes").get_data(as_text=True)
    assert "Quem depende deste ativo" in html
    assert "1 de alta criticidade" in html
    assert "Ver quem seria afetado" in html   # dentro do cartão de descontinuação


def test_ativo_sem_consumidor_diz_isso_claramente(app, cliente):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar_negocio(con)
    html = cliente.get(f"/ativo/{cap}?aba=relacoes").get_data(as_text=True)
    assert "Nenhum ativo vigente depende deste" in html
