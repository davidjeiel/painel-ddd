"""Carga assistida dos dois domínios piloto (Contrato e Garantias).

Reproduz o cenário usado nos protótipos da proposta: hierarquia de negócio,
ativos técnicos legados e modernos, ownership, evidências, revisões publicadas
e uma fila de validação com SLA em andamento.
"""
from __future__ import annotations

from datetime import date, timedelta

from . import servicos

# Squads ativas no arquivo Squads.csv. O título exibido no catálogo usa o
# Nome Curto; a descrição preserva o contexto do Título original.
SQUADS = [
    ("NM175", "Interface Regulatória", "NM175 - Interface Regulatória - SIACI"),
    ("NM176", "Fundos, Seguros e Componentes", "NM176 - Fundos, Seguros e Componentes - SIACI"),
    ("NM177", "Contábil e FCVS", "NM177 - Contábil e FCVS - SIACI"),
    ("NM178", "Cobrança e Inadimplência", "NM178 - Cobrança e Inadimplência - SIACI"),
    ("NM179", "Construção", "NM179 - Construção - SIACI"),
    ("NM180", "Portais e Serviços", "NM180 - Portais e Serviços - SIACI"),
    ("NM181", "Evolução Rotinas Críticas", "NM181 - Evolução Rotinas Críticas"),
    ("NM182", "Gestão da Originação e Entrada de Dados", "NM182 - Gestão da Originação e Integração"),
    ("NM183", "Jornada Backoffice - SISPH", "NM183 - Jornada Backoffice - SISPH"),
    ("NM184", "Jornada Baixa de Garantias - SISPH", "NM184 - Jornada Baixa de Garantias - SISPH"),
    ("NM185", "Plataforma Habitação", "NM185 - Plataforma Habitação - SISPH"),
    ("NM186", "Manual do Usuário - SIACI", "NM186 - Manual do Usuário - SIACI"),
    ("NM187", "Informações Gerenciais", "NM187 - Informações Gerenciais"),
    ("NM188", "Sustentação 2", "NM188 - Sustentação 2 - SIACI"),
    ("NM189", "POG, GRF e IR", "NM189 - POG, GRF e IR - SIACI"),
    ("NM190", "Estoque e Execução", "NM190 - Estoque e Execução"),
    ("NM191", "Sustentação 3", "NM191 - Sustentação 3"),
    ("NM192", "Backoffice e Serviços", "NM192 - Backoffice e Serviços - SIACI"),
    ("NM193", "Evolução Rotinas Específicas", "NM193 - Evolução - Online/Baixa Plataforma"),
    ("NM194", "Originação - Parâmetros e Integração", "NM194 - Entrada de Dados e Parâmetros"),
    ("NM195", "Apoio ao Desenvolvimento (G3)", "NM195 - Apoio ao Desenvolvimento (G3) - SIACI"),
    ("NM196", "Inteligência Artificial da Habitação - SIIAH", "NM196 - Inteligência Artificial da Habitação - SIIAH"),
    ("NM204", "Serviços de Sustentação 1 G2", "NM204 - Serviços de Sustentação 1 (G2) - SIACI"),
    ("NM205", "Jornada - SISPH", "NM205 - Jornada - SISPH"),
    ("NM206", "Apoio ao Desenvolvimento (G3)", "NM206 - Apoio ao Desenvolvimento (G3) - Negocial - SIACI"),
    ("NM208", "APIs .NET", "NM208 - APIs .NET"),
    ("NM209", "API JAVA", "NM209 - APIs JAVA"),
    ("NM210", "Débito Técnico .NET", "NM210 - Débito Técnico .NET"),
    ("NM211", "Débito Técnico Java", "NM211 - Débito Técnico Java"),
    ("NM212", "INTERNALIZAÇÃO LEGADO - .NET", "NM212 - INTERNALIZAÇÃO LEGADO - .NET"),
    ("NM213", "INTERNALIZAÇÃO SIACI - .NET", "NM213 - INTERNALIZAÇÃO SIACI - .NET"),
    ("NM214", "INTERNALIZAÇÃO LEGADO - JAVA", "NM214 - INTERNALIZAÇÃO LEGADO - JAVA"),
    ("NM215", "INTERNALIZAÇÃO SIACI - JAVA", "NM215 - INTERNALIZAÇÃO SIACI - JAVA"),
    ("NM216", "Sustentação 4", "NM216 - Sustentação 4 - SIACI"),
    ("Teste", "Time", "Time Teste"),
]

# Correspondência das squads usadas pelo cenário piloto com a taxonomia real.
SQUAD_PILOTO = {
    "SQ-CRE": "NM182",
    "SQ-CTR": "NM175",
    "SQ-GAR": "NM185",
    "SQ-LEG": "NM204",
}

PESSOAS = [
    ("M1001", "Ana Torres", "ana.torres@exemplo.com.br", "negocio", "SQ-CTR"),
    ("M1002", "Bruno Salles", "bruno.salles@exemplo.com.br", "tech_lead", "SQ-CTR"),
    ("M1003", "Carla Nunes", "carla.nunes@exemplo.com.br", "arquiteto", "SQ-LEG"),
    ("M1004", "Diego Prado", "diego.prado@exemplo.com.br", "tech_lead", "SQ-GAR"),
    ("M1005", "Eva Martins", "eva.martins@exemplo.com.br", "negocio", "SQ-GAR"),
    ("M1006", "Felipe Rocha", "felipe.rocha@exemplo.com.br", "curador", "SQ-LEG"),
    ("M1007", "Gabriela Lima", "gabriela.lima@exemplo.com.br", "tech_lead", "SQ-CRE"),
]


def carregar(con) -> dict:
    ids_squad = {}
    for codigo, nome, descricao in SQUADS:
        cur = con.execute(
            "INSERT INTO squad (codigo, nome, descricao) VALUES (?,?,?) "
            "ON CONFLICT(codigo) DO UPDATE SET nome = excluded.nome, "
            "descricao = excluded.descricao, ativo = 1",
            (codigo, nome, descricao))
        ids_squad[codigo] = con.execute(
            "SELECT id_squad FROM squad WHERE codigo = ?", (codigo,)).fetchone()[0]
    for legado, codigo in SQUAD_PILOTO.items():
        ids_squad[legado] = ids_squad[codigo]

    ids_pessoa = {}
    for matricula, nome, email, perfil, squad in PESSOAS:
        squad = SQUAD_PILOTO[squad]
        login = email.split("@")[0]
        cur = con.execute(
            "INSERT OR IGNORE INTO pessoa (matricula, nome, email, perfil, id_squad,"
            " login) VALUES (?,?,?,?,?,?)",
            (matricula, nome, email, perfil, ids_squad[squad], login))
        ids_pessoa[matricula] = cur.lastrowid or con.execute(
            "SELECT id_pessoa FROM pessoa WHERE matricula = ?", (matricula,)).fetchone()[0]
    con.commit()

    # o perfil declarado no cadastro vira papel efetivo, de escopo global no
    # piloto; a expansão corporativa é que dará escopo por domínio
    from . import acesso
    for matricula, _, _, perfil, _ in PESSOAS:
        ja_tem = con.execute(
            "SELECT 1 FROM atribuicao_papel WHERE id_pessoa = ? AND papel = ?",
            (ids_pessoa[matricula], perfil)).fetchone()
        if not ja_tem and perfil in acesso.PAPEIS:
            acesso.conceder(con, ids_pessoa[matricula], perfil,
                            concedido_por="carga.piloto")
    # uma pessoa com papel de curador global para operar o piloto de ponta a ponta
    curador = ids_pessoa["M1006"]
    if not con.execute("SELECT 1 FROM atribuicao_papel WHERE id_pessoa = ? "
                       "AND papel = 'admin'", (curador,)).fetchone():
        acesso.conceder(con, curador, "admin", concedido_por="carga.piloto")

    u = "carga.piloto"
    novo = lambda **kw: servicos.criar_item(con, usuario=u, **kw)

    # -------------------------------------------------- domínio: Contrato
    dom_ctr = novo(tipo_item="dominio", nome="Administração do Contrato",
                   descricao="Ciclo de vida do contrato de financiamento, da "
                             "proposta aprovada até a quitação.",
                   criticidade="alta",
                   atributos={"visao": "Sustentar a originação e a manutenção dos "
                                       "contratos de crédito imobiliário.",
                              "fórum": "Fórum de Arquitetura Corporativa"})
    sub_orig = novo(tipo_item="subdominio", nome="Originação", id_pai=dom_ctr,
                    descricao="Formalização e emissão do contrato.",
                    criticidade="alta", atributos={"classificacao": "core"})
    sub_manut = novo(tipo_item="subdominio", nome="Manutenção contratual",
                     id_pai=dom_ctr, descricao="Alterações, portabilidade e quitação.",
                     atributos={"classificacao": "suporte"})

    ctx_sim = novo(tipo_item="contexto", nome="Simulação", id_pai=sub_orig,
                   descricao="Cálculo de condições antes da contratação.",
                   criticidade="alta", id_squad=ids_squad["SQ-CRE"],
                   atributos={"linguagem_ubiqua": "Simulação, Cenário, Prazo, Taxa",
                              "estrategia_integracao": "serviço aberto"})
    ctx_gestao = novo(tipo_item="contexto", nome="Gestão de Contratos", id_pai=sub_manut,
                      descricao="Estado e eventos do contrato vigente.",
                      criticidade="critica", id_squad=ids_squad["SQ-CTR"],
                      atributos={"linguagem_ubiqua": "Contrato, Aditivo, Parcela",
                                 "estrategia_integracao": "cliente-fornecedor"})

    cap_sim = novo(tipo_item="capacidade", nome="Simular Financiamento", id_pai=ctx_sim,
                   descricao="Permite calcular condições de financiamento "
                             "considerando produto, cliente, garantias e políticas "
                             "vigentes.",
                   criticidade="alta", id_squad=ids_squad["SQ-CRE"],
                   atributos={"resultado_esperado": "Proposta simulada com parcelas, "
                                                    "CET e prazo.",
                              "processo_negocio": "Originação de crédito"})
    cap_port = novo(tipo_item="capacidade", nome="Registrar Portabilidade",
                    id_pai=ctx_gestao, descricao="Recebe e formaliza a portabilidade "
                                                 "de contrato de outra instituição.",
                    criticidade="media", id_squad=ids_squad["SQ-CTR"],
                    atributos={"resultado_esperado": "Contrato portado com saldo "
                                                     "devedor conciliado.",
                               "processo_negocio": "Manutenção contratual"})

    # -------------------------------------------------- domínio: Garantias
    dom_gar = novo(tipo_item="dominio", nome="Garantias",
                   descricao="Constituição, avaliação e liberação de garantias "
                             "vinculadas ao contrato.",
                   criticidade="alta",
                   atributos={"visao": "Reduzir risco de crédito com garantias "
                                       "válidas e rastreáveis.",
                              "fórum": "Fórum de Risco e Arquitetura"})
    sub_imob = novo(tipo_item="subdominio", nome="Garantia imobiliária", id_pai=dom_gar,
                    descricao="Imóveis dados em alienação fiduciária.",
                    criticidade="alta", atributos={"classificacao": "core"})
    ctx_imob = novo(tipo_item="contexto", nome="Garantia Imobiliária", id_pai=sub_imob,
                    descricao="Avaliação, registro em cartório e baixa de garantia.",
                    criticidade="alta", id_squad=ids_squad["SQ-GAR"],
                    atributos={"linguagem_ubiqua": "Imóvel, Laudo, Matrícula, Baixa",
                               "estrategia_integracao": "camada anticorrupção"})
    cap_aval = novo(tipo_item="capacidade", nome="Avaliar Imóvel", id_pai=ctx_imob,
                    descricao="Registra laudo de avaliação e valor aceito para "
                              "constituição da garantia.",
                    criticidade="alta", id_squad=ids_squad["SQ-GAR"],
                    atributos={"resultado_esperado": "Laudo aprovado e valor de "
                                                     "garantia definido.",
                               "processo_negocio": "Constituição de garantia"})

    # --------------------------------------------------- ativos técnicos
    sis_legado = novo(tipo_item="sistema", nome="SIACI - Core de Contratos",
                      descricao="Núcleo COBOL de contratos, ativo desde 1987.",
                      criticidade="critica", id_squad=ids_squad["SQ-LEG"],
                      atributos={"plataforma": "mainframe", "situacao": "em modernização"})
    sis_digital = novo(tipo_item="sistema", nome="Plataforma Digital de Crédito",
                       descricao="Camada distribuída de originação digital.",
                       criticidade="alta", id_squad=ids_squad["SQ-CRE"],
                       atributos={"plataforma": "nuvem", "situacao": "estratégico"})

    app_sim = novo(tipo_item="aplicacao", nome="Motor de Simulação", id_pai=sis_digital,
                   descricao="Serviço de cálculo de condições de financiamento.",
                   criticidade="alta", id_squad=ids_squad["SQ-CRE"],
                   atributos={"tecnologia": "Java 21 / Spring Boot",
                              "ambiente": "des, hml, prd"})
    app_ctr = novo(tipo_item="aplicacao", nome="Gestor de Contratos", id_pai=sis_legado,
                   descricao="Programas COBOL de manutenção contratual.",
                   criticidade="critica", id_squad=ids_squad["SQ-LEG"],
                   atributos={"tecnologia": "COBOL / CICS / DB2", "ambiente": "prd"})
    app_gar = novo(tipo_item="aplicacao", nome="Portal de Garantias", id_pai=sis_digital,
                   descricao="Cadastro e acompanhamento de garantias.",
                   criticidade="alta", id_squad=ids_squad["SQ-GAR"],
                   atributos={"tecnologia": "Python / FastAPI", "ambiente": "hml, prd"})

    repo_sim = novo(tipo_item="repositorio", nome="motor-simulacao", id_pai=app_sim,
                    descricao="Código do motor de cálculo.",
                    id_squad=ids_squad["SQ-CRE"],
                    atributos={"url": "https://git.exemplo.com.br/credito/motor-simulacao",
                               "branch_principal": "main", "linguagem": "Java",
                               "ultima_atividade": date.today().isoformat()})
    repo_legado = novo(tipo_item="repositorio", nome="siaci-core", id_pai=app_ctr,
                       descricao="Fontes COBOL do core de contratos.",
                       criticidade="critica", id_squad=ids_squad["SQ-LEG"],
                       atributos={"url": "https://git.exemplo.com.br/legado/siaci-core",
                                  "branch_principal": "master", "linguagem": "COBOL",
                                  "ultima_atividade": (date.today() - timedelta(days=240)).isoformat()})
    repo_gar = novo(tipo_item="repositorio", nome="calculo-habitacao", id_pai=app_gar,
                    descricao="Rotinas de cálculo de garantia habitacional.",
                    id_squad=ids_squad["SQ-GAR"],
                    atributos={"url": "https://git.exemplo.com.br/garantias/calculo-habitacao",
                               "branch_principal": "main", "linguagem": "Python",
                               "ultima_atividade": date.today().isoformat()})

    api_sim = novo(tipo_item="api", nome="API Simulação", id_pai=app_sim,
                   descricao="Expõe o cálculo de condições para canais digitais.",
                   criticidade="alta", id_squad=ids_squad["SQ-CRE"],
                   atributos={"versao": "2.3", "estilo": "REST",
                              "url_contrato": "https://api.exemplo.com.br/simulacao/openapi.json"})
    api_ctr = novo(tipo_item="api", nome="API Contratos", id_pai=app_ctr,
                   descricao="Consulta e manutenção de contratos vigentes.",
                   criticidade="critica", id_squad=ids_squad["SQ-CTR"],
                   atributos={"versao": "3.0", "estilo": "REST",
                              "url_contrato": "https://api.exemplo.com.br/contratos/openapi.json"})
    api_gar = novo(tipo_item="api", nome="API Garantias", id_pai=app_gar,
                   descricao="Registro e consulta de garantias.",
                   criticidade="alta", id_squad=ids_squad["SQ-GAR"],
                   atributos={"versao": "1.4", "estilo": "REST"})

    end_sim = novo(tipo_item="endpoint", nome="POST /simulacoes", id_pai=api_sim,
                   descricao="Cria uma simulação de financiamento.",
                   atributos={"metodo": "POST", "rota": "/simulacoes"})
    novo(tipo_item="endpoint", nome="GET /contratos/{id}", id_pai=api_ctr,
         descricao="Consulta contrato por identificador.",
         criticidade="alta", atributos={"metodo": "GET", "rota": "/contratos/{id}"})
    novo(tipo_item="endpoint", nome="POST /garantias/{id}/laudos", id_pai=api_gar,
         descricao="Anexa laudo de avaliação à garantia.",
         atributos={"metodo": "POST", "rota": "/garantias/{id}/laudos"})

    bd_ctr = novo(tipo_item="base_dados", nome="DB2 Contratos", id_pai=sis_legado,
                  descricao="Base transacional do core de contratos.",
                  criticidade="critica", id_squad=ids_squad["SQ-LEG"],
                  atributos={"sgbd": "IBM DB2 z/OS", "classificacao_dado": "restrito"})
    obj_ctr = novo(tipo_item="objeto_dado", nome="TB_CONTRATO", id_pai=bd_ctr,
                   descricao="Tabela mestre de contratos.",
                   criticidade="critica",
                   atributos={"sistema_registro": "sim", "granularidade": "1 linha por contrato"})

    evt = novo(tipo_item="evento", nome="ContratoFormalizado", id_pai=ctx_gestao,
               descricao="Publicado quando o contrato é assinado e registrado.",
               criticidade="alta", id_squad=ids_squad["SQ-CTR"],
               atributos={"topico": "contratos.formalizado.v1", "formato": "Avro"})

    # ------------------------------------------------------------ ownership
    papeis = [
        (dom_ctr, "M1001", "owner_negocial"), (sub_orig, "M1001", "owner_negocial"),
        (sub_manut, "M1001", "owner_negocial"),
        (ctx_sim, "M1001", "owner_negocial"), (ctx_sim, "M1007", "owner_tecnico"),
        (ctx_gestao, "M1001", "owner_negocial"), (ctx_gestao, "M1002", "owner_tecnico"),
        (cap_sim, "M1001", "owner_negocial"), (cap_sim, "M1007", "owner_tecnico"),
        (cap_port, "M1001", "owner_negocial"), (cap_port, "M1002", "owner_tecnico"),
        (dom_gar, "M1005", "owner_negocial"), (sub_imob, "M1005", "owner_negocial"),
        (ctx_imob, "M1005", "owner_negocial"), (ctx_imob, "M1004", "owner_tecnico"),
        (cap_aval, "M1005", "owner_negocial"), (cap_aval, "M1004", "owner_tecnico"),
        (sis_legado, "M1003", "owner_tecnico"), (sis_digital, "M1007", "owner_tecnico"),
        (app_sim, "M1007", "owner_tecnico"), (app_ctr, "M1002", "owner_tecnico"),
        (app_gar, "M1004", "owner_tecnico"),
        (repo_sim, "M1007", "owner_tecnico"), (repo_gar, "M1004", "owner_tecnico"),
        (api_sim, "M1007", "owner_tecnico"), (api_ctr, "M1002", "owner_tecnico"),
        (api_gar, "M1004", "owner_tecnico"),
        (bd_ctr, "M1003", "owner_tecnico"), (evt, "M1002", "owner_tecnico"),
    ]
    for id_item, matricula, papel in papeis:
        servicos.definir_responsavel(con, id_item, ids_pessoa[matricula], papel, u)

    # ------------------------------------------------------------- relações
    relacoes = [
        (app_sim, cap_sim, "implementa", "alta", None),
        (app_ctr, cap_port, "implementa", "critica", None),
        (app_gar, cap_aval, "implementa", "alta", None),
        (api_sim, cap_sim, "implementa", "alta", "sincrono"),
        (api_ctr, cap_port, "implementa", "critica", "sincrono"),
        (api_gar, cap_aval, "implementa", "alta", "sincrono"),
        (api_sim, end_sim, "expoe", "media", None),
        (app_sim, api_gar, "consome", "alta", "sincrono"),
        (app_ctr, obj_ctr, "persiste_em", "critica", None),
        (ctx_sim, ctx_imob, "depende_de", "alta", "sincrono"),
        (ctx_gestao, ctx_imob, "depende_de", "critica", "assincrono"),
        (app_ctr, evt, "produz", "alta", "assincrono"),
        (app_gar, evt, "consome", "media", "assincrono"),
    ]
    for origem, destino, tipo_rel, crit, mecanismo in relacoes:
        servicos.relacionar(con, origem, destino, tipo_rel, crit, mecanismo, usuario=u)

    # ----------------------------------------------------------- evidências
    evidencias = [
        (dom_ctr, "documento", "Ata do fórum de governança", None),
        (dom_gar, "documento", "Política corporativa de garantias", None),
        (ctx_sim, "adr", "ADR-014 separação simulação/contratação", None),
        (ctx_gestao, "adr", "ADR-021 estratégia de portabilidade", None),
        (ctx_imob, "adr", "ADR-009 camada anticorrupção de cartório", None),
        (cap_sim, "documento", "Manual de política de crédito", None),
        (cap_aval, "documento", "Norma de avaliação de imóveis", None),
        (cap_port, "documento", "Fluxo de portabilidade", None),
        (api_sim, "openapi", "Contrato OpenAPI 2.3",
         "https://api.exemplo.com.br/simulacao/openapi.json"),
        (api_ctr, "openapi", "Contrato OpenAPI 3.0",
         "https://api.exemplo.com.br/contratos/openapi.json"),
        (api_gar, "openapi", "Contrato OpenAPI 1.4", None),
        (repo_sim, "repositorio", "Repositório Git",
         "https://git.exemplo.com.br/credito/motor-simulacao"),
        (repo_gar, "repositorio", "Repositório Git",
         "https://git.exemplo.com.br/garantias/calculo-habitacao"),
        (app_sim, "documento", "Diagrama de implantação", None),
        (app_ctr, "documento", "Inventário de programas COBOL", None),
        (app_gar, "documento", "Diagrama de contexto", None),
        (sis_digital, "documento", "Visão de arquitetura", None),
        (bd_ctr, "documento", "Dicionário de dados", None),
        (evt, "documento", "Esquema Avro do evento", None),
    ]
    for id_item, tipo_ev, titulo, url in evidencias:
        servicos.anexar_evidencia(con, id_item, tipo_ev, titulo, url, usuario=u)

    # ------------------------------------- publicação da base já governada
    publicados = [dom_ctr, sub_orig, sub_manut, ctx_sim, ctx_gestao, cap_sim,
                  dom_gar, sub_imob, ctx_imob, cap_aval, sis_legado, sis_digital,
                  app_sim, app_ctr, app_gar, repo_sim, repo_gar, api_sim, api_gar,
                  bd_ctr, obj_ctr, evt, end_sim]
    for id_item in publicados:
        resultado = servicos.submeter(con, id_item, "Carga inicial do piloto", u)
        if not resultado["aprovado"]:
            continue
        for val in con.execute(
            "SELECT id_validacao FROM validacao WHERE id_item = ? AND situacao = 'pendente'",
            (id_item,)).fetchall():
            servicos.decidir_validacao(con, val["id_validacao"], True,
                                       "Aprovado na carga assistida", u)

    # ------------------------------------------- fila de validação em aberto
    servicos.submeter(con, api_ctr, "Publicação da versão 3.0 do contrato", u)
    servicos.submeter(con, cap_port, "Nova capacidade de portabilidade", u)
    # repositório legado fica em rascunho com pendências reais
    servicos.submeter(con, repo_legado, "Inclusão do core legado", u)

    # ------------------------------------------------ snapshots de tendência
    hoje = date.today().replace(day=1)
    for i in range(5, 0, -1):
        mes = (hoje - timedelta(days=30 * i)).strftime("%Y-%m")
        base = 58 + (5 - i) * 4
        con.execute(
            "INSERT OR REPLACE INTO snapshot_indicador (competencia, indicador, valor) "
            "VALUES (?,?,?)", (mes, "cobertura", float(base)))
        con.execute(
            "INSERT OR REPLACE INTO snapshot_indicador (competencia, indicador, valor) "
            "VALUES (?,?,?)", (mes, "qualidade_media", float(base - 6)))
    con.commit()
    servicos.gerar_snapshot(con)

    total = con.execute("SELECT COUNT(*) c FROM item_catalogo").fetchone()["c"]
    pendentes = con.execute(
        "SELECT COUNT(*) c FROM validacao WHERE situacao = 'pendente'").fetchone()["c"]
    return {"ativos": total, "validacoes_pendentes": pendentes,
            "squads": len(SQUADS), "pessoas": len(PESSOAS)}
