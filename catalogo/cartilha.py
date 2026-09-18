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
    "tech_lead": "Tech lead",
    "arquiteto": "Arquiteto",
    "curador": "Curador",
    "admin": "Admin",
    "consulta": "Consulta",
}

# Rótulos legíveis do que está gravado em minúscula e sem acento no banco.
ETAPA_ROTULO = {"negocial": "Negocial", "tecnica": "Técnica",
                "arquitetural": "Arquitetural"}
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
    "administrar": "Conceder papéis",
}

PRIMEIROS_PASSOS = [
    {
        "titulo": "Diga quem você é",
        "texto": (
            "Abra <strong>Seu perfil</strong> no menu e escolha o seu nome. Isso não é "
            "formalidade: é esse nome que assina as publicações que você fizer, e cada "
            "publicação gera um registro imutável com hash e trilha de auditoria. "
            "Enquanto você não se identificar, a ferramenta recusa qualquer escrita e "
            "te manda de volta para essa tela."),
        "extra": (
            "Na mesma tela você vê <strong>seus papéis</strong>. Se a lista estiver "
            "vazia, você consegue consultar o catálogo mas não escrever nele — peça a "
            "um administrador."),
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
            "Cadastrar e editar Domínio, Subdomínio, Bounded Context e Capacidade",
            "Ser owner negocial de um ativo",
            "Enviar para validação e abrir revisão",
            "Decidir a etapa <strong>negocial</strong> das validações",
        ],
        "recusa": [
            ("Registrar relações entre ativos",
             "quem implementa o quê é informação técnica: peça ao tech lead"),
            ("Importar descobertas e triar a bandeja", "é o caminho do time técnico"),
            ("Descontinuar um ativo publicado", "fica com curador, arquiteto ou admin"),
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
        "rotulo": "Tech lead",
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
        ],
        "recusa": [
            ("Decidir validações",
             "por desenho: quem cuida do cadastro não é quem o aprova. Você prepara, "
             "outra pessoa valida"),
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
            ("Conceda papéis pela linha de comando, no servidor: "
             "<code>flask --app catalogo conceder ana.torres negocio</code> para papel "
             "global, ou <code>--dominio 3</code> para restringir a um domínio.", ""),
            ("Prefira o escopo por domínio: a pessoa decide no que conhece. A ferramenta "
             "resolve o domínio de qualquer ativo subindo a hierarquia, então o papel "
             "vale para os endpoints abaixo dele.", ""),
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

DUVIDAS = [
    ("O botão que eu usava sumiu",
     "Três causas, nesta ordem: você está em <strong>modo de leitura</strong> (troque em "
     "Seu perfil); o seu <strong>papel</strong> não permite aquela ação (veja a matriz "
     "acima); ou o ativo está <strong>publicado</strong> e precisa de uma revisão aberta "
     "antes de aceitar mudanças."),
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
