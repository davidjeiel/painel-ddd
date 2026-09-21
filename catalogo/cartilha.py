"""Conteúdo da cartilha de uso, por perfil de usuário.

A prosa (rotina, avisos, dúvidas) mora aqui; as **tabelas de referência** não.
A matriz "quem pode fazer o quê" é derivada de :data:`acesso.PERMISSOES` e a
tabela de ritos, da tabela ``politica_governanca``. É de propósito: uma cartilha
que repete a regra à mão envelhece em silêncio na primeira mudança de política,
e uma cartilha errada é pior do que nenhuma.
"""
from __future__ import annotations

from . import acesso

# Colunas da matriz, na ordem em que aparecem na tela.
PAPEIS_ORDEM = ("negocio", "tech_lead", "arquiteto", "curador", "admin", "consulta")

PAPEL_CURTO = {
    "negocio": "Negócio",
    "tech_lead": "Time técnico",
    "arquiteto": "Arquiteto",
    "curador": "Curador",
    "admin": "Admin",
    "consulta": "Consulta",
}

# Rótulos legíveis do que está gravado em minúscula e sem acento no banco.
ETAPA_ROTULO = {"negocial": "Negocial", "tecnica": "Técnica",
                "arquitetural": "Arquitetural"}
# Classe CSS do badge de cada etapa na tabela de rito — três cores fixas,
# a mesma leitura em qualquer tipo de ativo.
ETAPA_CLASSE = {"negocial": "et-n", "tecnica": "et-t", "arquitetural": "et-a"}
CRITICIDADE_ROTULO = {"*": "todas", "critica": "crítica", "alta": "alta",
                      "media": "média", "baixa": "baixa"}

# Ação interna → rótulo na matriz. A ordem é a do dia de trabalho: cadastrar,
# relacionar, submeter, decidir, administrar.
ACOES_ROTULO = {
    "cadastrar": "Cadastrar ativos",
    "editar": "Editar rascunho",
    "relacionar": "Registrar relação",
    "submeter": "Enviar para validação",
    "revisar": "Abrir revisão",
    "decidir": "Decidir validação",
    "importar": "Importar descobertas",
    "triar": "Triar a bandeja",
    "descontinuar": "Descontinuar ativo",
    "conceder": "Conceder papéis",
    "administrar": "Administrar a ferramenta",
}

PRIMEIROS_PASSOS = [
    {
        "titulo": "Cadastre-se e pleiteie um papel",
        "texto": (
            "Em <strong>Seu perfil › Cadastre-se e pleiteie um papel</strong> você "
            "informa matrícula (uma letra e seis números, como C123456), nome, e-mail, "
            "unidade (quatro números) e o papel que pretende exercer. O cadastro entra "
            "na hora; o <strong>papel não</strong>."),
        "extra": (
            "Quem concede é outra pessoa — um curador ou um administrador — que pode "
            "conceder o papel pedido, conceder outro ou negar, sempre com uma resposta "
            "escrita. Ela chega no sino e fica em Seu perfil. Até lá, você consulta o "
            "catálogo inteiro e não escreve em nada."),
    },
    {
        "titulo": "Diga quem você é",
        "texto": (
            "Identificado, é o seu nome que assina as publicações que você fizer, e "
            "cada publicação gera um registro imutável com hash e trilha de auditoria. "
            "Enquanto você não se identificar, a ferramenta recusa qualquer escrita e "
            "te manda de volta para o perfil."),
        "extra": (
            "Na mesma tela você vê <strong>seus papéis</strong> e o andamento dos seus "
            "pleitos. Precisa de mais do que tem? Pleiteie outro papel — o pedido novo "
            "não apaga os que você já tem."),
    },
    {
        "titulo": "Escolha o modo de trabalho",
        "texto": (
            "<strong>Edição</strong> mostra as ações que o seu papel permite. "
            "<strong>Leitura</strong> esconde todos os formulários de escrita — útil "
            "quando você está só consultando, apresentando a tela para alguém ou com "
            "medo de clicar errado. Dá para alternar quando quiser."),
        "extra": "",
    },
    {
        "titulo": "Aprenda três atalhos que economizam o dia",
        "texto": (
            "<strong>Busca global</strong> no topo de qualquer tela: tecle <kbd>/</kbd> "
            "ou <kbd>Ctrl+K</kbd>, digite parte do nome ou do código, e vá direto ao "
            "ativo. <strong>Minha mesa</strong> no menu reúne tudo o que espera por "
            "você. E o <strong>sino</strong> avisa quando algo entra na sua fila ou "
            "quando um prazo está vencendo — em Preferências você desliga o ruído."),
        "extra": "",
    },
]

REGRAS = [
    ("O papel autoriza a ação e o objeto",
     "Quem responde pelo negócio escreve na Estrutura DDD — domínio, subdomínio, "
     "contexto, capacidade. Quem responde pela técnica escreve nos ativos técnicos. "
     "Arquiteto, curador e admin atravessam os dois. Fora do seu bloco, o catálogo é "
     "consulta, e a rota recusa mesmo que você chegue nela pelo endereço."),
    ("Quem submete não aprova",
     "Se você enviou uma revisão para validação, a ferramenta não deixa você mesmo "
     "decidir sobre ela — nem se o seu papel permitir aquela etapa. É segregação de "
     "função, e não tem exceção."),
    ("Versão publicada não se edita",
     "Para mudar um ativo publicado é preciso abrir uma revisão. A versão antiga "
     "continua vigente para quem consome, até a nova ser aprovada. Nada é sobrescrito: "
     "cada publicação vira uma revisão numerada, com hash."),
]

PERFIS = [
    {
        "chave": "negocio",
        "papel": "negocio",
        "rotulo": "Negócio",
        "lema": "Você responde pelo significado",
        "resumo": (
            "Que domínios a empresa tem, que capacidades eles entregam, e o que é "
            "crítico de verdade. A tecnologia entra depois; sem o seu nome nas coisas, "
            "ela não tem onde se apoiar."),
        "faz": [
            "Cadastrar e editar Domínio, Subdomínio, Contextos Delimitados e Capacidade",
            "Ser owner negocial de um ativo",
            "Enviar para validação e abrir revisão",
            "Decidir a etapa <strong>negocial</strong> das validações",
        ],
        "recusa": [
            ("Registrar relações entre ativos",
             "quem implementa o quê é informação técnica: peça ao time técnico"),
            ("Importar descobertas e triar a bandeja", "é o caminho do time técnico"),
            ("Descontinuar um ativo publicado", "fica com curador, arquiteto ou admin"),
            ("Cadastrar ou editar ativo técnico",
             "sistema, aplicação, API, endpoint e base de dados são do outro bloco: "
             "para você eles são consulta"),
        ],
        "rotina_titulo": "Sua rotina",
        "rotina": [
            ("Abra <strong>Minha mesa</strong> e veja as análises que já são suas.",
             "Menu › Trabalhar › Minha mesa"),
            ("Não tendo nada, pegue uma da fila livre — <strong>assuma</strong> para os "
             "outros saberem que está com você.", ""),
            ("No painel de decisão, leia <strong>o que mudou</strong> na revisão. O "
             "sistema mostra o antes e o depois, já resumido, sem o ruído dos campos "
             "automáticos.", "Validações › Analisar"),
            ("Confira as evidências e o checklist de governança ao lado.", ""),
            ("Aprove ou rejeite <strong>sempre com parecer</strong>. Rejeição devolve o "
             "ativo ao autor como rascunho e o avisa — o parecer é o que ele vai ler.", ""),
            ("Deixe marcado “ir para a próxima da fila” e despache tudo de uma sentada.", ""),
        ],
        "nota": (
            "<strong>Cadastrando uma capacidade?</strong> Comece pelo contexto delimitado "
            "a que ela pertence — a ferramenta exige o pai. E preencha o "
            "<em>resultado esperado</em>: é campo obrigatório e sem ele a publicação "
            "trava no primeiro passo do checklist."),
    },
    {
        "chave": "tech",
        "papel": "tech_lead",
        "rotulo": "Time técnico",
        "lema": "Você responde pela realidade técnica",
        "resumo": (
            "O que existe de fato, onde roda, e o que conversa com o quê. É o seu "
            "registro que transforma “acho que essa API é usada por alguém” em uma "
            "resposta."),
        "faz": [
            "Cadastrar Sistema, Aplicação, Repositório, API, Endpoint, Base de dados, "
            "Objeto de dado e Evento",
            "Registrar relações, inclusive em lote",
            "Importar descobertas de OpenAPI e inventário Git",
            "Triar a bandeja do que a máquina trouxe",
            "Decidir a etapa <strong>técnica</strong> das validações",
        ],
        "recusa": [
            ("Descontinuar um ativo publicado",
             "a saída de uso passa por curador, arquiteto ou admin"),
            ("Decidir etapas negocial e arquitetural",
             "a menos que você seja o responsável formal daquele ativo"),
            ("Cadastrar ou editar a hierarquia de negócio",
             "domínio, subdomínio, contexto e capacidade são do bloco de negócio: "
             "para você eles são consulta"),
        ],
        "rotina_titulo": "Sua rotina: trazer um sistema inteiro para o catálogo",
        "rotina": [
            ("Cadastre o <strong>Sistema</strong> e as <strong>Aplicações</strong> na "
             "mão — são poucos e ninguém descobre sozinho.",
             "Menu › Trabalhar › Novo ativo"),
            ("Vá em <strong>Descobertas</strong>, cole o contrato OpenAPI, escolha a "
             "aplicação de destino e clique em <strong>Gerar prévia</strong>. Nada é "
             "gravado ainda: você vê exatamente o que será criado.",
             "Menu › Trabalhar › Descobertas"),
            ("Confirme a importação. A API e um endpoint por operação entram como "
             "rascunho, marcados como <em>descoberta automática</em>.", ""),
            ("Na <strong>bandeja de triagem</strong>, aceite o que faz sentido e "
             "descarte o que não deveria estar no catálogo. Aceitar não muda o "
             "cadastro — só marca que uma pessoa olhou.", ""),
            ("Abra cada rascunho e complete a semântica: descrição, criticidade, squad. "
             "A máquina trouxe o observável; o significado é seu.", ""),
            ("Use <strong>Registrar várias de uma vez</strong> na aba Relações para "
             "ligar a aplicação a tudo o que ela expõe ou consome, com o mecanismo "
             "aplicado ao conjunto.",
             "Visão 360° › Relações › Registrar várias de uma vez"),
            ("Envie para validação. O checklist mostra o que ainda falta antes de deixar.", ""),
        ],
        "nota": (
            "<strong>O campo mecanismo importa.</strong> É ele que responde depois “essa "
            "dependência é uma chamada síncrona que derruba a aplicação, ou um batch "
            "noturno que pode esperar?”. Preencher custa um clique e poupa uma reunião."),
    },
    {
        "chave": "arquiteto",
        "papel": "arquiteto",
        "rotulo": "Arquiteto",
        "lema": "Você responde pela coerência do todo",
        "resumo": (
            "Se os limites entre contextos fazem sentido, se um contrato novo não cria "
            "um acoplamento que ninguém vai conseguir desfazer, e o que quebra quando "
            "algo muda."),
        "faz": [
            "Decidir a etapa <strong>arquitetural</strong> — a última barreira antes de "
            "publicar contratos e contextos",
            "Registrar relações entre ativos",
            "Cadastrar e editar qualquer tipo de ativo",
            "Descontinuar ativos que saem de uso",
        ],
        "recusa": [
            ("Importar descobertas e triar a bandeja",
             "é operação do time técnico e da curadoria"),
            ("Decidir sobre uma revisão que você mesmo submeteu", ""),
        ],
        "rotina_titulo": "Sua rotina: decidir com o impacto à vista",
        "rotina": [
            ("Na fila, filtre pela aba <strong>Arquitetural</strong> — só o que exige o "
             "seu olhar.", "Menu › Trabalhar › Validações › Arquitetural"),
            ("Leia o diff da revisão. Mudança de contrato aparece em “Campos do tipo” e "
             "em “Relações”.", ""),
            ("Antes de aprovar, abra o <strong>grafo</strong> do ativo e suba para 2 "
             "saltos: você vê quem depende dele além dos vizinhos diretos.",
             "Visão 360° › Relações › Ver como grafo"),
            ("O cartão <strong>Quem depende deste ativo</strong> lista os consumidores "
             "vigentes e destaca os de alta criticidade. É a lista que vai sentir a "
             "mudança.", ""),
            ("Decida com parecer. Se rejeitar, diga o que precisa mudar — o autor recebe "
             "o seu texto.", ""),
        ],
        "nota": (
            "<strong>Quando o grafo avisa que foi cortado</strong>, é porque a vizinhança "
            "passou do teto de ativos. Reduza a distância ou filtre por tipo de relação: "
            "o que ficou de fora continua existindo, e a ferramenta prefere avisar a "
            "mentir sobre o alcance."),
    },
    {
        "chave": "curador",
        "papel": "curador",
        "rotulo": "Curador",
        "lema": "Você mantém o cadastro vivo",
        "resumo": (
            "Catálogo desatualizado vira ficção em dois trimestres, e é o seu trabalho "
            "que impede isso: achar o que está órfão, incompleto ou velho, e fazer "
            "alguém resolver."),
        "faz": [
            "Cadastrar e editar qualquer tipo de ativo",
            "Registrar relações, inclusive em lote",
            "Importar descobertas e triar a bandeja",
            "Enviar para validação e abrir revisão",
            "Descontinuar ativos que saem de uso",
            "<strong>Conceder papéis</strong> pleiteados, com o alcance que decidir",
        ],
        "recusa": [
            ("Decidir validações",
             "por desenho: quem cuida do cadastro não é quem o aprova. Você prepara, "
             "outra pessoa valida"),
            ("Conceder o papel de administrador",
             "só um administrador cria outro; sem esse teto, administrar a ferramenta "
             "se espalharia por concessão lateral"),
        ],
        "rotina_titulo": "Sua rotina: caçar o que está apodrecendo",
        "rotina": [
            ("Comece pelo <strong>painel executivo</strong>. Todo número ali é clicável "
             "e leva ao recorte que ele resume.", "Menu › Visão executiva"),
            ("Clique em <strong>Sem responsável</strong>: são ativos publicados que "
             "ninguém responde. Cada um é um dono a descobrir.", ""),
            ("Em <strong>Pendências prioritárias</strong>, ataque “capacidade sem owner” "
             "e “API sem capacidade vinculada” — são os que quebram o painel de "
             "cobertura.", ""),
            ("No catálogo, filtre por <strong>origem: descoberta automática</strong> "
             "para ver o que a máquina trouxe e ninguém revisou.",
             "Catálogo › Origem do cadastro"),
            ("Ordene por <strong>Qualidade crescente</strong>: os piores scores "
             "primeiro. Abra cada um e siga o <strong>caminho até a publicação</strong> "
             "— cinco passos, e cada um leva à aba que resolve a pendência.", ""),
            ("Complete, submeta, e deixe a validação com quem valida.", ""),
            ("Antes de sair, passe em <strong>Pleitos de acesso</strong>: cada pleito "
             "parado é alguém que não consegue trabalhar. Conceda o papel pedido, "
             "conceda um menor ou negue — mas responda.",
             "Menu › Administração › Pleitos de acesso"),
        ],
        "nota": (
            "<strong>Você não decide validação, e isso é de propósito.</strong> Se a "
            "mesma pessoa preenchesse e aprovasse, o rito seria decorativo. Quando "
            "precisar destravar uma fila parada, chame quem tem o papel da etapa — não "
            "peça o papel para si."),
    },
    {
        "chave": "admin",
        "papel": "admin",
        "rotulo": "Administrador",
        "lema": "Você opera a ferramenta e concede acesso",
        "resumo": (
            "Você faz tudo o que os outros fazem, concede os papéis e mantém a máquina "
            "rodando. Justamente por isso, é o papel a distribuir com mais cuidado."),
        "faz": [
            "Todas as ações de cadastro, relação, importação e descontinuação",
            "Decidir qualquer etapa de validação",
            "Conceder papéis a pessoas, global ou por domínio",
            "Operar os comandos de manutenção",
        ],
        "recusa": [
            ("Decidir sobre uma revisão que você mesmo submeteu",
             "a segregação de função não tem exceção de papel"),
            ("Editar uma versão publicada sem abrir revisão", ""),
        ],
        "rotina_titulo": "Sua rotina: conceder papel e manter o relógio andando",
        "rotina": [
            ("Despache os pleitos em <strong>Pleitos de acesso</strong>: escolha o papel, "
             "o alcance (global, um domínio ou uma squad) e escreva a resposta. Só você "
             "concede o papel de administrador.",
             "Menu › Administração › Pleitos de acesso"),
            ("Prefira o escopo por domínio: a pessoa decide no que conhece. A ferramenta "
             "resolve o domínio de qualquer ativo subindo a hierarquia, então o papel "
             "vale para os endpoints abaixo dele.", ""),
            ("Fora da tela, a linha de comando faz o mesmo: "
             "<code>flask --app catalogo conceder ana.torres negocio --dominio 3</code> "
             "— útil para semear o primeiro administrador de um ambiente novo.", ""),
            ("Agende <code>vigiar-sla</code> de hora em hora: é ele que gera os avisos "
             "de prazo vencendo e vencido.", ""),
            ("Agende <code>notificar</code> logo depois: despacha a fila de envio. "
             "Rodar duas vezes não duplica nada.", ""),
            ("Agende <code>snapshot</code> uma vez por mês: materializa os indicadores "
             "que alimentam a variação do painel.", ""),
            ("Rode <code>qualidade</code> depois de mudar políticas, para recalcular o "
             "score de todos os ativos.", ""),
        ],
        "nota": (
            "<strong>Sem os dois primeiros comandos agendados, o SLA não existe na "
            "prática.</strong> A política define o prazo, mas é o vigia que avisa "
            "alguém. Notificação parada na fila de envio aparece marcada como tal na "
            "caixa — se você vir muitas assim, o despacho não está rodando."),
    },
    {
        "chave": "consulta",
        "papel": "consulta",
        "rotulo": "Consulta",
        "lema": "Você lê e não altera nada",
        "resumo": (
            "É o papel da maior parte da empresa — e o catálogo só vale a pena se essas "
            "perguntas forem fáceis de responder."),
        "faz": [],
        "recusa": [],
        "rotina_titulo": "O que o catálogo responde para você",
        "rotina": [
            ("<strong>“Quem é dono disto?”</strong> — abra o ativo, aba Pessoas.", ""),
            ("<strong>“O que quebra se isso mudar?”</strong> — aba Relações, cartão "
             "<em>Quem depende deste ativo</em>, ou o grafo para ver além dos vizinhos.", ""),
            ("<strong>“Que capacidades esse domínio tem, e quais estão "
             "implementadas?”</strong> — Mapas, visão de negócio: capacidade sem "
             "implementação vem destacada.", ""),
            ("<strong>“Que sistemas e APIs existem?”</strong> — Mapas, visão de "
             "tecnologia.", ""),
            ("<strong>“Esta API é oficial?”</strong> — o status no topo do ativo. Só "
             "<em>publicado</em> e <em>em revisão</em> são consumíveis; "
             "<em>rascunho</em> não é promessa de nada.", ""),
            ("<strong>“Quando isso foi revisado, e por quem?”</strong> — aba Histórico: "
             "revisões numeradas com hash, e a trilha de auditoria abaixo.", ""),
        ],
        "nota": (
            "<strong>Não achou pela busca?</strong> Ela procura em nome, código e "
            "descrição. Se o ativo não aparece, ou ele não está cadastrado — e vale "
            "avisar um curador — ou está arquivado. O filtro de status no catálogo "
            "mostra os dois casos."),
    },
]

# Trilha de trabalho por perfil, em etapas: o que o rito parece do cadastro à
# publicação para quem exerce aquele papel. Chave = PERFIS[n]["chave"].
FLUXOS: dict[str, list[dict]] = {
    "negocio": [
        {"etapa": "Cadastro", "papel": "Nomear o negócio",
         "acao": "Cadastra domínios, subdomínios, contextos delimitados e capacidades.",
         "detalhes": [
             "Cadastrar e editar os ativos da hierarquia de estrutura DDD: domínio, "
             "subdomínio, contextos delimitados e capacidade de negócio.",
             "Na internalização do software legado adquirido, esta é a etapa "
             "“as chaves”: antes de abrir o código, nomear o negócio que "
             "o sistema sustenta.",
             "A escrita é restrita ao bloco de tipos do papel — fora dele, o "
             "catálogo é consulta, e a recusa acontece no servidor, não apenas "
             "escondendo o botão."],
         "atencao": "Registrar relações entre ativos não é ação deste papel."},
        {"etapa": "Submissão", "papel": "Enviar para validação",
         "acao": "Fecha o checklist vivo e submete o ativo ao rito.",
         "detalhes": [
             "Enviar o ativo para validação quando o cadastro atingir a nota "
             "mínima de qualidade exigida pelo tipo.",
             "O checklist vivo acompanha o ativo até a publicação, mostrando o "
             "que ainda falta.",
             "Marcar o ativo como crítico aperta o rito de verdade: mais uma "
             "etapa, mais uma evidência, nota mais alta e metade do prazo."],
         "atencao": "Quem submete não aprova: a partir daqui, a decisão é de "
                    "outra pessoa."},
        {"etapa": "Decisão", "papel": "Decidir a etapa negocial",
         "acao": "Emite parecer na etapa que exige o papel de negócio.",
         "detalhes": [
             "Decidir a etapa negocial dos tipos cujo caminho a exige: domínio, "
             "subdomínio, contextos delimitados, capacidade de negócio, "
             "capacidade crítica e API crítica.",
             "Quem decide uma etapa precisa do papel daquela etapa, ou ser o "
             "responsável formal pelo ativo.",
             "O parecer é obrigatório e o prazo por etapa é acompanhado por "
             "aviso automático.",
             "Segregação de função sem exceção: não se decide sobre uma revisão "
             "que a própria pessoa enviou."]},
        {"etapa": "Ciclo de vida", "papel": "Revalidar o que envelhece",
         "acao": "Reconfirma o significado dentro da periodicidade do tipo.",
         "detalhes": [
             "Atender à revalidação periódica definida por tipo — de 90 a 365 "
             "dias, conforme a política vigente.",
             "Mudar um ativo publicado exige abrir uma revisão: a versão "
             "vigente continua valendo para quem consome até a nova ser "
             "aprovada.",
             "Cada publicação vira uma revisão numerada com hash, e a trilha "
             "registra quem fez o quê."]},
    ],
    "tech": [
        {"etapa": "Descoberta", "papel": "Importar e triar o observável",
         "acao": "Lê contratos OpenAPI e inventário Git e tria o que vira cadastro.",
         "detalhes": [
             "Rodar a descoberta automática sobre contratos OpenAPI e "
             "inventário Git, com prévia antes de gravar.",
             "Tudo o que a máquina traz nasce como rascunho marcado como "
             "automático — nada vira afirmação oficial sozinho.",
             "Triar a bandeja depois da importação: só uma pessoa transforma o "
             "achado em cadastro."]},
        {"etapa": "Cadastro", "papel": "Registrar a realidade construída",
         "acao": "Cadastra sistema, aplicação, API, endpoint, base, objeto, "
                 "repositório e evento.",
         "detalhes": [
             "Cadastrar e editar os ativos técnicos: sistema, aplicação, API, "
             "endpoint, base de dados, objeto de dado, repositório e evento de "
             "integração.",
             "A escrita é restrita ao bloco de tipos do papel; fora dele, o "
             "catálogo é consulta."]},
        {"etapa": "Relação", "papel": "Ligar o ativo à capacidade",
         "acao": "Registra as relações tipadas: implementa, expõe, consome.",
         "detalhes": [
             "Registrar as relações tipadas entre ativos técnicos e "
             "capacidades de negócio — é aqui que a internalização de fato "
             "acontece.",
             "Usar relações em lote quando o volume exigir.",
             "O que não se consegue ligar a capacidade nenhuma é código cuja "
             "razão de existir ninguém sabe explicar — e essa é a lista mais "
             "valiosa do processo."]},
        {"etapa": "Submissão", "papel": "Enviar para validação",
         "acao": "Submete o ativo técnico ao rito do seu tipo.",
         "detalhes": [
             "Enviar para validação observando a nota mínima do tipo — de 55% "
             "em endpoint e objeto de dado a 80% em API crítica.",
             "Anexar as evidências exigidas pela política do tipo e da "
             "criticidade."]},
        {"etapa": "Decisão", "papel": "Decidir a etapa técnica",
         "acao": "Emite parecer na etapa que exige o papel do time técnico.",
         "detalhes": [
             "Decidir a etapa técnica — presente no caminho de praticamente "
             "todos os tipos, do sistema ao evento de integração.",
             "Respeitar o prazo por etapa: 72 h nos tipos de menor risco, 48 h "
             "nos intermediários e 24 h nos críticos.",
             "Não decidir sobre a própria submissão."]},
        {"etapa": "Ciclo de vida", "papel": "Manter o ativo vivo",
         "acao": "Revalida e abre revisão quando algo muda.",
         "detalhes": [
             "Cumprir a revalidação periódica do tipo: 90 dias em API crítica, "
             "120 em API e evento, 180 em aplicação, repositório, endpoint e "
             "objeto, 365 em sistema e base de dados.",
             "Versão publicada não se edita: mudar exige abrir revisão, e nada "
             "é sobrescrito."]},
    ],
    "arquiteto": [
        {"etapa": "Cadastro", "papel": "Atravessar as duas hierarquias",
         "acao": "Cadastra e edita tanto estrutura DDD quanto ativos técnicos.",
         "detalhes": [
             "Cadastrar e editar ativos nos dois blocos — é o papel que "
             "atravessa a fronteira entre significado de negócio e realidade "
             "técnica.",
             "Registrar relações tipadas entre os ativos das duas hierarquias."]},
        {"etapa": "Análise", "papel": "Ler o impacto antes de decidir",
         "acao": "Usa o grafo navegável e a análise de impacto.",
         "detalhes": [
             "Consultar o grafo navegável de dependências para responder o que "
             "quebra se um ativo mudar.",
             "Usar a análise de impacto como insumo do parecer arquitetural.",
             "Acompanhar a cobertura técnica e a cobertura de negócio: "
             "capacidade sem implementação aparece destacada em vermelho no "
             "mapa de negócio."]},
        {"etapa": "Decisão", "papel": "Decidir a etapa arquitetural",
         "acao": "É a última etapa do caminho nos tipos de maior risco.",
         "detalhes": [
             "Decidir a etapa arquitetural nos tipos que a exigem: domínio, "
             "contextos delimitados, capacidade crítica, API, API crítica e "
             "evento de integração.",
             "A etapa arquitetural fecha o caminho de publicação — é o último "
             "parecer antes do ativo virar versão vigente.",
             "Segregação de função sem exceção de papel."]},
        {"etapa": "Fim de vida", "papel": "Descontinuar ativo",
         "acao": "Encerra o ciclo de vida do que não deve mais ser consumido.",
         "detalhes": [
             "Descontinuar ativos — ação reservada a arquiteto, curador e "
             "administrador.",
             "É o que permite responder “esta API é oficial?” com "
             "algo além de usar e torcer.",
             "A vigência substitui a exclusão: é o que permite responder quem "
             "respondia por um ativo numa data passada."],
         "atencao": "Importar e triar descobertas não é ação deste papel."},
    ],
    "curador": [
        {"etapa": "Acesso", "papel": "Conceder papéis",
         "acao": "Responde ao pleito de papel no rito de acesso.",
         "detalhes": [
             "Conceder papéis com alcance global, por domínio ou por squad.",
             "Responder ao solicitante que se cadastrou pleiteando um papel.",
             "A concessão define em que bloco de tipos a pessoa poderá "
             "escrever."]},
        {"etapa": "Preparo", "papel": "Preparar o acervo",
         "acao": "Cadastra, relaciona e tria as descobertas automáticas.",
         "detalhes": [
             "Cadastrar e editar ativos e registrar relações nos dois blocos.",
             "Importar e triar descobertas de contratos OpenAPI e inventário "
             "Git.",
             "Enviar ativos para validação depois de completar o cadastro."]},
        {"etapa": "Qualidade", "papel": "Caçar o que envelheceu",
         "acao": "Usa o painel executivo para achar ativo sem dono, incompleto "
                 "ou vencido.",
         "detalhes": [
             "Acompanhar no painel executivo o que está sem dono, incompleto "
             "ou com revalidação vencida.",
             "É o papel que existe para impedir que o catálogo envelheça e "
             "vire ficção em dois trimestres.",
             "Na internalização do sistema adquirido, recomenda-se um owner "
             "formal com o papel de curador no domínio do produto adquirido."]},
        {"etapa": "Fim de vida", "papel": "Descontinuar ativo",
         "acao": "Retira de circulação o que não deve mais ser consumido.",
         "detalhes": ["Descontinuar ativos, junto com arquiteto e "
                      "administrador."]},
        {"etapa": "Limite", "papel": "Não decidir a validação",
         "acao": "Prepara o cadastro, mas a decisão é de outra pessoa.",
         "detalhes": [
             "O curador prepara o cadastro mas não decide validação: se a "
             "mesma pessoa preenchesse e aprovasse, o rito seria decorativo.",
             "É exatamente esta restrição que separa um rito real de um "
             "carimbo."],
         "atencao": "Único papel de escrita ampla sem poder de decisão no "
                    "rito."},
    ],
    "admin": [
        {"etapa": "Acesso", "papel": "Sustentar o rito de acesso",
         "acao": "Concede papéis e responde aos pleitos de cadastro.",
         "detalhes": [
             "Conceder papéis com alcance global, por domínio ou por squad, "
             "junto com o curador.",
             "Responder ao solicitante no rito de acesso, definindo o bloco de "
             "tipos em que ele poderá escrever."]},
        {"etapa": "Operação", "papel": "Operar o catálogo de ponta a ponta",
         "acao": "Cadastra, relaciona, importa, tria e submete.",
         "detalhes": [
             "Cadastrar e editar ativos e registrar relações nos dois blocos.",
             "Importar e triar descobertas automáticas.",
             "Enviar ativos para validação."]},
        {"etapa": "Decisão", "papel": "Decidir validação",
         "acao": "Participa das decisões — sem exceção na segregação de "
                 "função.",
         "detalhes": [
             "Decidir validação de ativos submetidos por outras pessoas.",
             "Nem o administrador decide sobre uma revisão que ele mesmo "
             "enviou: a segregação de função não tem exceção de papel."]},
        {"etapa": "Fim de vida", "papel": "Descontinuar ativo",
         "acao": "Encerra o ciclo de vida quando necessário.",
         "detalhes": [
             "Descontinuar ativos, junto com arquiteto e curador.",
             "Nada é sobrescrito: cada publicação vira uma revisão numerada "
             "com hash, e a trilha registra quem fez o quê."]},
        {"etapa": "Implantação", "papel": "Garantir que o aviso chegue",
         "acao": "O despacho de notificações depende de comandos agendados.",
         "detalhes": [
             "O aviso por evento e por prazo depende de dois comandos "
             "agendados no servidor — item de implantação, não de "
             "desenvolvimento.",
             "A fila de envio é visível: notificação não despachada aparece "
             "marcada como tal."]},
    ],
    "consulta": [
        {"etapa": "Leitura", "papel": "Consultar o acervo",
         "acao": "Lê todo o catálogo, sem escrever em nenhum bloco.",
         "detalhes": [
             "Consultar ativos das duas hierarquias, com busca global, "
             "filtros que voltam na visita seguinte e visão 360° em abas.",
             "Nenhuma ação de escrita está disponível: cadastrar, relacionar, "
             "submeter, decidir, triar, descontinuar e conceder papéis estão "
             "fora deste perfil."]},
        {"etapa": "Navegação", "papel": "Responder as três perguntas",
         "acao": "Descobre quem responde, o que quebra e se a API é oficial.",
         "detalhes": [
             "Quem responde por este ativo — pelo responsável formal "
             "registrado.",
             "O que quebra se isto mudar — pelo grafo navegável de "
             "dependências e pela análise de impacto.",
             "Esta API é oficial — pelo estado do ciclo de vida e pela versão "
             "vigente publicada.",
             "Que capacidades este domínio entrega — pelos mapas das duas "
             "hierarquias."]},
        {"etapa": "Evolução", "papel": "Pleitear um papel",
         "acao": "Se precisar escrever, entra no rito de acesso.",
         "detalhes": [
             "Cadastrar-se com pleito de papel e aguardar a concessão por "
             "curador ou administrador, com resposta ao solicitante.",
             "A cartilha de uso por perfil está dentro da própria ferramenta, "
             "com a matriz de permissões lida do próprio código."]},
    ],
}

DUVIDAS = [
    ("O botão que eu usava sumiu",
     "Quatro causas, nesta ordem: você está em <strong>modo de leitura</strong> (troque "
     "em Seu perfil); o seu <strong>papel</strong> não permite aquela ação (veja a matriz "
     "acima); o ativo é de um <strong>bloco que o seu papel não escreve</strong> — "
     "negócio não mexe em ativo técnico e vice-versa; ou o ativo está "
     "<strong>publicado</strong> e precisa de uma revisão aberta antes de aceitar "
     "mudanças."),
    ("Pedi um papel e não recebi nada",
     "O pleito fica em <strong>Seu perfil</strong> com o estado dele. Pendente significa "
     "que ninguém despachou ainda — um curador ou administrador precisa decidir, e você "
     "será avisado pelo sino. Negado ou concedido com papel menor, a resposta de quem "
     "decidiu está ali, escrita. Pleito sem justificativa costuma voltar com papel menor "
     "do que o pedido: diga o que você vai cadastrar ou decidir."),
    ("Não consigo aprovar esta validação",
     "Ou a <strong>etapa exige um papel</strong> que você não tem — a mensagem diz "
     "qual —, ou <strong>você submeteu</strong> essa revisão. No segundo caso não há o "
     "que ajustar: outra pessoa precisa decidir."),
    ("Meu ativo não publica",
     "Abra ele e olhe o <strong>caminho até a publicação</strong>, no topo: cinco passos "
     "com o que falta em cada um, e cada passo leva à aba que resolve. O mais comum é "
     "evidência faltando ou score abaixo do mínimo do tipo — e o score sobe preenchendo "
     "descrição, campos obrigatórios e responsáveis."),
    ("Não recebo notificação nenhuma",
     "Confira Notificações › Preferências. Se estiver tudo ligado e mesmo assim nada "
     "chega, provavelmente os comandos agendados não estão rodando no servidor — fale "
     "com um administrador. E-mail e Teams ainda estão desligados por decisão pendente: "
     "hoje o aviso aparece no sino, dentro da ferramenta."),
    ("Encontrei um ativo errado ou duplicado",
     "Não apague nada — o catálogo não esquece de propósito, e o histórico é o que dá "
     "valor à trilha de auditoria. Se for duplicata vinda de importação, use a "
     "<strong>bandeja de triagem</strong> para descartar (ela arquiva, preservando o "
     "registro). Se já está publicado, o caminho é <strong>descontinuar</strong>, com "
     "motivo — e a ferramenta vai listar quem depende dele antes de deixar."),
]


def matriz() -> list[dict]:
    """Linhas da matriz de permissões, lidas de :data:`acesso.PERMISSOES`."""
    linhas = []
    for acao, rotulo in ACOES_ROTULO.items():
        papeis = acesso.PERMISSOES.get(acao, set())
        linhas.append({
            "acao": acao,
            "rotulo": rotulo,
            "papeis": {p: (p in papeis) for p in PAPEIS_ORDEM},
        })
    return linhas


def etapas_por_papel() -> dict[str, list[str]]:
    """Papel → etapas que ele decide, lido de :data:`acesso.PAPEL_POR_ETAPA`."""
    saida: dict[str, list[str]] = {p: [] for p in PAPEIS_ORDEM}
    for etapa, papeis in acesso.PAPEL_POR_ETAPA.items():
        for papel in papeis:
            saida.setdefault(papel, []).append(etapa)
    return saida
