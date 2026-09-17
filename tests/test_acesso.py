"""Testes da fase 4: identidade, RBAC, notificações e grafo.

O que estes testes protegem e antes não existia: **a autorização acontece na
rota, não na tela** — esconder o botão nunca foi autorização.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import apoio  # noqa: E402

from catalogo import (acesso, create_app, db as banco, governanca,  # noqa: E402
                      notificacoes, servicos)


@pytest.fixture()
def app(tmp_path):
    aplicacao = create_app({"DATABASE": str(tmp_path / "acesso.db"), "TESTING": True,
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
    """Uma pessoa por papel, mais um catálogo mínimo para agir sobre ele."""
    with app.app_context():
        con = banco.get_db()
        pessoas = {
            "admin": apoio.criar_pessoa(con, "Admin", "admin.teste", "admin"),
            "curador": apoio.criar_pessoa(con, "Curadora", "cura.teste", "curador"),
            "negocio": apoio.criar_pessoa(con, "Negócio", "nego.teste", "negocio"),
            "tech_lead": apoio.criar_pessoa(con, "Tech Lead", "tech.teste", "tech_lead"),
            "arquiteto": apoio.criar_pessoa(con, "Arquiteta", "arqui.teste", "arquiteto"),
            "consulta": apoio.criar_pessoa(con, "Visitante", "visi.teste", "consulta"),
        }
    return pessoas


def montar(con, usuario="cura.teste"):
    dom = servicos.criar_item(con, tipo_item="dominio", nome="Contrato",
                              descricao="Domínio", usuario=usuario,
                              atributos={"visao": "Sustentar"})
    sub = servicos.criar_item(con, tipo_item="subdominio", nome="Originação",
                              descricao="Formalização", id_pai=dom, usuario=usuario,
                              atributos={"classificacao": "core"})
    ctx = servicos.criar_item(con, tipo_item="contexto", nome="Simulação",
                              descricao="Cálculo", id_pai=sub, usuario=usuario)
    cap = servicos.criar_item(con, tipo_item="capacidade", nome="Simular",
                              descricao="Calcula", id_pai=ctx, usuario=usuario,
                              atributos={"resultado_esperado": "Proposta"})
    return dom, sub, ctx, cap


def submeter(con, cap, elenco, usuario="cura.teste"):
    """Leva a capacidade até a fila de validação."""
    servicos.definir_responsavel(con, cap, elenco["negocio"], "owner_negocial", usuario)
    servicos.definir_responsavel(con, cap, elenco["tech_lead"], "owner_tecnico", usuario)
    servicos.anexar_evidencia(con, cap, "documento", "Política", usuario=usuario)
    sis = servicos.criar_item(con, tipo_item="sistema", nome="Plataforma",
                              descricao="Sistema", usuario=usuario,
                              atributos={"plataforma": "nuvem"})
    aplic = servicos.criar_item(con, tipo_item="aplicacao", nome="Motor",
                                descricao="App", id_pai=sis, usuario=usuario,
                                atributos={"tecnologia": "Python"})
    servicos.relacionar(con, aplic, cap, "implementa", usuario=usuario)
    servicos.submeter(con, cap, "Publicação inicial", usuario)
    return {l["etapa"]: l["id_validacao"] for l in con.execute(
        "SELECT etapa, id_validacao FROM validacao WHERE id_item = ? "
        "AND situacao = 'pendente'", (cap,))}


# ------------------------------------------------------------------- F4.1
def test_papel_global_vale_em_qualquer_item(app, elenco):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar(con)
        assert acesso.pode(con, elenco["curador"], "editar", cap)
        assert not acesso.pode(con, elenco["consulta"], "editar", cap)


def test_papel_de_dominio_nao_vale_em_outro_dominio(app, elenco):
    with app.app_context():
        con = banco.get_db()
        dom, _, _, cap = montar(con)
        outro = servicos.criar_item(con, tipo_item="dominio", nome="Garantias",
                                    descricao="Outro", atributos={"visao": "Risco"})
        local = apoio.criar_pessoa(con, "Curador Local", "local.teste", "curador",
                                   "dominio", dom)
        assert acesso.pode(con, local, "editar", cap)      # dentro do domínio
        assert not acesso.pode(con, local, "editar", outro)  # fora dele


def test_etapa_negocial_exige_papel_de_negocio(app, elenco):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar(con)
        vals = submeter(con, cap, elenco)
        pode_tech, motivo = acesso.pode_decidir(con, elenco["tech_lead"],
                                                vals["negocial"])
        pode_nego, _ = acesso.pode_decidir(con, elenco["negocio"], vals["negocial"])
    assert not pode_tech and "negocio" in motivo
    assert pode_nego


def test_segregacao_de_funcao_quem_submete_nao_aprova(app, elenco):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar(con, usuario="admin.teste")
        vals = submeter(con, cap, elenco, usuario="admin.teste")
        autorizado, motivo = acesso.pode_decidir(con, elenco["admin"],
                                                 vals["negocial"])
    assert not autorizado
    assert "Segregação de função" in motivo


def test_servico_recusa_decisao_sem_papel(app, elenco):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar(con)
        vals = submeter(con, cap, elenco)
        with pytest.raises(acesso.SemPermissao):
            servicos.decidir_validacao(con, vals["negocial"], True, "ok",
                                       "tech.teste", id_pessoa=elenco["tech_lead"])
        # sem pessoa na chamada (CLI, carga) o serviço segue funcionando
        resultado = servicos.decidir_validacao(con, vals["negocial"], True, "ok")
    assert resultado["situacao"] == "aprovada"


def test_rota_de_escrita_recusa_mesmo_sem_passar_pela_tela(app, elenco):
    """O formulário enviado direto tem de ser recusado igual."""
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar(con)
    visitante = app.test_client()
    apoio.entrar(visitante, elenco["consulta"])
    resposta = visitante.post(f"/ativo/{cap}/evidencia",
                              data={"tipo": "documento", "titulo": "Contrabando"})
    assert resposta.status_code in (302, 303)
    with app.app_context():
        total = banco.get_db().execute(
            "SELECT COUNT(*) FROM evidencia WHERE id_item = ?", (cap,)).fetchone()[0]
    assert total == 0


def test_sessao_sem_pessoa_e_mandada_ao_perfil(app, elenco):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar(con)
    anonimo = app.test_client()
    resposta = anonimo.post(f"/ativo/{cap}/submeter", data={"motivo": "vai"})
    assert "/perfil" in resposta.headers["Location"]


# ------------------------------------------------------------------- F4.0
def test_modo_leitura_esconde_os_formularios(app, elenco):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar(con)
    leitor = app.test_client()
    apoio.entrar(leitor, elenco["admin"], modo="leitura")
    html = leitor.get(f"/ativo/{cap}?aba=relacoes").get_data(as_text=True)
    assert "Registrar relação" not in html
    assert 'class="escrever"' not in html
    assert "leitura" in html          # o modo aparece no cabeçalho


def test_modo_leitura_tambem_recusa_na_rota(app, elenco):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar(con)
    leitor = app.test_client()
    apoio.entrar(leitor, elenco["admin"], modo="leitura")
    leitor.post(f"/ativo/{cap}/evidencia", data={"tipo": "link", "titulo": "X"})
    with app.app_context():
        total = banco.get_db().execute(
            "SELECT COUNT(*) FROM evidencia WHERE id_item = ?", (cap,)).fetchone()[0]
    assert total == 0


def test_descontinuar_com_consumidor_critico_exige_o_codigo(app, elenco):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar(con)
        sis = servicos.criar_item(con, tipo_item="sistema", nome="Core",
                                  descricao="S", atributos={"plataforma": "mainframe"})
        aplic = servicos.criar_item(con, tipo_item="aplicacao", nome="Gestor",
                                    descricao="A", id_pai=sis,
                                    atributos={"tecnologia": "COBOL"})
        servicos.relacionar(con, aplic, cap, "implementa", criticidade="critica")
        con.execute("UPDATE item_catalogo SET status_ciclo_vida = 'publicado' "
                    "WHERE id_item IN (?, ?)", (aplic, cap))
        con.commit()
        codigo = con.execute("SELECT codigo FROM item_catalogo WHERE id_item = ?",
                             (cap,)).fetchone()["codigo"]
    cliente = app.test_client()
    apoio.entrar(cliente, elenco["admin"])

    cliente.post(f"/ativo/{cap}/descontinuar",
                 data={"motivo": "obsoleta", "confirmacao": "qualquer coisa"})
    with app.app_context():
        status = banco.get_db().execute(
            "SELECT status_ciclo_vida FROM item_catalogo WHERE id_item = ?",
            (cap,)).fetchone()["status_ciclo_vida"]
    assert status == "publicado"      # confirmação errada não descontinua

    cliente.post(f"/ativo/{cap}/descontinuar",
                 data={"motivo": "obsoleta", "confirmacao": codigo, "forcar": "1"})
    with app.app_context():
        status = banco.get_db().execute(
            "SELECT status_ciclo_vida FROM item_catalogo WHERE id_item = ?",
            (cap,)).fetchone()["status_ciclo_vida"]
    assert status == "descontinuado"


def test_acessibilidade_do_esqueleto(app, elenco):
    cliente = app.test_client()
    apoio.entrar(cliente, elenco["admin"])
    html = cliente.get("/").get_data(as_text=True)
    assert 'class="pular"' in html                  # pular para o conteúdo
    assert 'id="conteudo"' in html
    assert "API de indicadores" not in html         # JSON cru fora do menu humano


def test_criticidade_media_e_baixa_tem_estilos_proprios(app):
    css = (Path(__file__).resolve().parent.parent
           / "catalogo" / "static" / "estilo.css").read_text(encoding="utf-8")
    assert ".etiqueta.media" in css and ".etiqueta.baixa" in css


# ------------------------------------------------------------------- F4.3
def test_submissao_avisa_quem_pode_decidir(app, elenco):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar(con)
        vals = submeter(con, cap, elenco)
        caixa_negocio = notificacoes.caixa(con, elenco["negocio"])
        caixa_visitante = notificacoes.caixa(con, elenco["consulta"])
    assert any(n["tipo"] == "revisao_submetida" for n in caixa_negocio)
    assert caixa_visitante == []          # quem não decide não é incomodado
    assert vals


def test_notificacao_entra_na_mesma_transacao_e_fica_na_outbox(app, elenco):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar(con)
        submeter(con, cap, elenco)
        pendentes = con.execute(
            "SELECT COUNT(*) FROM notificacao WHERE enviado_em IS NULL").fetchone()[0]
        primeiro = notificacoes.despachar(con)
        segundo = notificacoes.despachar(con)
    assert pendentes > 0
    assert primeiro["despachadas"] == pendentes
    assert segundo["despachadas"] == 0      # idempotente


def test_preferencia_desligada_nao_gera_notificacao(app, elenco):
    with app.app_context():
        con = banco.get_db()
        notificacoes.salvar_preferencias(con, elenco["negocio"], set())
        _, _, _, cap = montar(con)
        submeter(con, cap, elenco)
        assert notificacoes.caixa(con, elenco["negocio"]) == []
        assert notificacoes.caixa(con, elenco["arquiteto"]) == []


def test_rejeicao_avisa_o_autor(app, elenco):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar(con, usuario="cura.teste")
        vals = submeter(con, cap, elenco, usuario="cura.teste")
        servicos.decidir_validacao(con, vals["negocial"], False, "faltou contexto",
                                   "nego.teste", id_pessoa=elenco["negocio"])
        caixa_autor = notificacoes.caixa(con, elenco["curador"])
    assert any(n["tipo"] == "revisao_rejeitada" and "faltou contexto" in (n["corpo"] or "")
               for n in caixa_autor)


def test_vigia_de_sla_nao_repete_o_alerta_no_mesmo_dia(app, elenco):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar(con)
        vals = submeter(con, cap, elenco)
        vencido = (datetime.now() - timedelta(hours=2)).isoformat(" ", "seconds")
        con.execute("UPDATE validacao SET prazo = ? WHERE id_validacao = ?",
                    (vencido, vals["negocial"]))
        con.commit()
        primeiro = notificacoes.vigiar_sla(con)
        segundo = notificacoes.vigiar_sla(con)
    assert primeiro["sla_vencido"] > 0
    assert segundo["sla_vencido"] == 0


def test_sino_mostra_a_contagem_de_nao_lidas(app, elenco):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar(con)
        submeter(con, cap, elenco)
    cliente = app.test_client()
    apoio.entrar(cliente, elenco["negocio"])
    html = cliente.get("/").get_data(as_text=True)
    assert 'class="bolha"' in html
    caixa = cliente.get("/notificacoes").get_data(as_text=True)
    assert "aguarda validação" in caixa


# ------------------------------------------------------------------- F4.2
def test_vizinhanca_de_um_salto_traz_so_os_vizinhos_diretos(app, elenco):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar(con)
        submeter(con, cap, elenco)
        aplic = con.execute("SELECT id_item FROM item_catalogo WHERE nome = 'Motor'"
                            ).fetchone()["id_item"]
        um = servicos.vizinhanca(con, cap, saltos=1)
    assert {n["id_item"] for n in um["nos"]} == {cap, aplic}
    assert um["arestas"][0]["tipo_relacao"] == "implementa"
    assert not um["truncado"]


def test_vizinhanca_de_dois_saltos_nao_repete_nos(app, elenco):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar(con)
        submeter(con, cap, elenco)
        aplic = con.execute("SELECT id_item FROM item_catalogo WHERE nome = 'Motor'"
                            ).fetchone()["id_item"]
        outra = servicos.criar_item(con, tipo_item="capacidade", nome="Renegociar",
                                    descricao="Outra", id_pai=con.execute(
                                        "SELECT id_item FROM item_catalogo "
                                        "WHERE tipo_item = 'contexto'").fetchone()["id_item"],
                                    atributos={"resultado_esperado": "x"})
        servicos.relacionar(con, aplic, outra, "implementa")
        dois = servicos.vizinhanca(con, cap, saltos=2)
    ids = [n["id_item"] for n in dois["nos"]]
    assert len(ids) == len(set(ids))
    assert outra in ids
    assert {n["id_item"]: n["salto"] for n in dois["nos"]}[outra] == 2


def test_teto_marca_truncado(app, elenco):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar(con)
        sis = servicos.criar_item(con, tipo_item="sistema", nome="Plataforma",
                                  descricao="S", atributos={"plataforma": "nuvem"})
        for n in range(6):
            aplic = servicos.criar_item(con, tipo_item="aplicacao", nome=f"App {n}",
                                        descricao="A", id_pai=sis,
                                        atributos={"tecnologia": "Python"})
            servicos.relacionar(con, aplic, cap, "implementa")
        cortado = servicos.vizinhanca(con, cap, saltos=1, teto=3)
    assert cortado["truncado"]
    assert len(cortado["nos"]) <= 3


def test_filtro_por_tipo_de_relacao_reduz_o_grafo(app, elenco):
    with app.app_context():
        con = banco.get_db()
        _, _, ctx, cap = montar(con)
        sis = servicos.criar_item(con, tipo_item="sistema", nome="Plataforma",
                                  descricao="S", atributos={"plataforma": "nuvem"})
        aplic = servicos.criar_item(con, tipo_item="aplicacao", nome="Motor",
                                    descricao="A", id_pai=sis,
                                    atributos={"tecnologia": "Python"})
        servicos.relacionar(con, aplic, cap, "implementa")
        servicos.relacionar(con, aplic, ctx, "consome")
        tudo = servicos.vizinhanca(con, aplic, saltos=1)
        so_implementa = servicos.vizinhanca(con, aplic, saltos=1,
                                            tipos_relacao=("implementa",))
    assert len(tudo["nos"]) == 3
    assert len(so_implementa["nos"]) == 2


def test_layout_poe_o_centro_no_meio(app, elenco):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar(con)
        submeter(con, cap, elenco)
        posicionado = servicos.posicionar_vizinhanca(
            servicos.vizinhanca(con, cap, saltos=1), largura=800, altura=600)
    centro = [n for n in posicionado["nos"] if n["salto"] == 0][0]
    assert (centro["x"], centro["y"]) == (400.0, 300.0)
    assert all(n["x"] is not None and n["y"] is not None for n in posicionado["nos"])
    assert all({"x1", "y1", "x2", "y2"} <= set(a) for a in posicionado["arestas"])


def test_tela_do_grafo_responde_e_avisa_o_corte(app, elenco):
    with app.app_context():
        con = banco.get_db()
        _, _, _, cap = montar(con)
        submeter(con, cap, elenco)
    cliente = app.test_client()
    apoio.entrar(cliente, elenco["admin"])
    html = cliente.get(f"/ativo/{cap}/grafo?saltos=2").get_data(as_text=True)
    assert "svg" in html and "Quem depende deste ativo" in html
    assert cliente.get(f"/api/v1/itens/{cap}/vizinhanca").get_json()["centro"] == cap


# ------------------------------------------------- aparência (tema e menu)
def test_tema_noturno_tem_os_tres_estados(app):
    """Escolha explícita clara, escura e o padrão do sistema."""
    css = (Path(__file__).resolve().parent.parent
           / "catalogo" / "static" / "estilo.css").read_text(encoding="utf-8")
    assert "@media (prefers-color-scheme: dark)" in css
    assert ':root:not([data-tema="claro"])' in css   # sistema escuro, sem escolha manual
    assert ':root[data-tema="escuro"]' in css        # escolha manual vence o sistema
    assert "color-scheme: dark" in css


def test_paleta_e_toda_por_token(app):
    """Nenhuma cor fixa fora da declaração dos tokens: senão um tema quebra o outro."""
    import re
    css = (Path(__file__).resolve().parent.parent
           / "catalogo" / "static" / "estilo.css").read_text(encoding="utf-8")
    fora = [linha.strip() for linha in css.splitlines()
            if re.search(r"#[0-9a-fA-F]{3,6}\b", linha) and not linha.strip().startswith("--")]
    assert fora == [], fora


def test_menu_recolhivel_tem_controle_e_iniciais(app, elenco):
    cliente = app.test_client()
    apoio.entrar(cliente, elenco["admin"])
    html = cliente.get("/").get_data(as_text=True)
    assert 'id="recolher-menu"' in html
    assert 'aria-controls="menu-lateral"' in html
    assert 'aria-expanded="true"' in html
    # cada item leva a inicial que aparece quando o menu está estreito
    assert '<span class="inicial" aria-hidden="true">VE</span>' in html
    assert '<span class="rotulo">Visão executiva</span>' in html


def test_menu_compacto_esconde_rotulo_e_mostra_inicial(app):
    css = (Path(__file__).resolve().parent.parent
           / "catalogo" / "static" / "estilo.css").read_text(encoding="utf-8")
    assert ':root[data-menu="compacto"] { --menu-largura: 68px; }' in css
    assert ':root[data-menu="compacto"] .menu a .rotulo { display: none; }' in css
    assert ':root[data-menu="compacto"] .menu .inicial { display: flex; }' in css


def test_preferencia_aplicada_antes_da_pintura(app, elenco):
    """O script de tema vem antes do CSS: sem piscada de tela clara."""
    cliente = app.test_client()
    apoio.entrar(cliente, elenco["admin"])
    html = cliente.get("/").get_data(as_text=True)
    assert html.index("localStorage.getItem('tema')") < html.index("estilo.css")
    assert 'id="alternar-tema"' in html
