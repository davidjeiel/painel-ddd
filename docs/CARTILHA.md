# Cartilha do Catálogo Corporativo DDD

Guia de uso por papel. Cada papel tem um trabalho, e a ferramenta só mostra o seu.

O catálogo não é um formulário que todo mundo preenche igual. Ele distribui o trabalho:
quem conhece o negócio nomeia o significado, quem conhece a tecnologia registra a
realidade, e ninguém aprova o que escreveu. Esta cartilha mostra, para cada papel, o que
você consegue fazer, o que a ferramenta vai recusar e por quê — e a rotina que resolve o
seu dia.

> **Esta cartilha também está dentro da ferramenta**, em `/cartilha` — link no rodapé de
> qualquer tela e ao lado do seu nome, no topo. Lá a matriz de permissões é lida de
> `catalogo/acesso.py` e a tabela de ritos, das políticas cadastradas, então a página
> nunca descreve uma regra que o sistema já não aplica. Este arquivo é a cópia
> versionada: se a ferramenta mudar, ele precisa mudar junto.

| Papel | Você responde por |
| --- | --- |
| [Negócio](#negócio) | o significado |
| [Tech lead](#tech-lead) | a realidade técnica |
| [Arquiteto](#arquiteto) | a coerência do todo |
| [Curador](#curador) | manter o cadastro vivo |
| [Administrador](#administrador) | operar a ferramenta e conceder acesso |
| [Consulta](#consulta) | ler, sem alterar nada |

---

## Os primeiros cinco minutos

Vale para qualquer papel. Faça isto uma vez e o resto da cartilha faz sentido.

### 1. Diga quem você é

Abra **Seu perfil** no menu e escolha o seu nome. Isso não é formalidade: é esse nome que
assina as publicações que você fizer, e cada publicação gera um registro imutável com hash
e trilha de auditoria. Enquanto você não se identificar, a ferramenta recusa qualquer
escrita e te manda de volta para essa tela.

Na mesma tela você vê **seus papéis**. Se a lista estiver vazia, você consegue consultar o
catálogo mas não escrever nele — peça a um administrador.

### 2. Escolha o modo de trabalho

**Edição** mostra as ações que o seu papel permite. **Leitura** esconde todos os
formulários de escrita — útil quando você está só consultando, apresentando a tela para
alguém ou com medo de clicar errado. Dá para alternar quando quiser.

### 3. Aprenda três atalhos que economizam o dia

- **Busca global** no topo de qualquer tela: tecle `/` ou `Ctrl+K`, digite parte do nome ou
  do código, e vá direto ao ativo.
- **Minha mesa** no menu: tudo o que está esperando por você, em um lugar só — o que você
  assumiu, o que pode assumir, seus rascunhos.
- **Notificações**: o sino no topo avisa quando algo entra na sua fila ou quando um prazo
  está vencendo. Em *Preferências* você desliga o que for ruído.

### Duas regras que valem para todo mundo

**Quem submete não aprova.** Se você enviou uma revisão para validação, a ferramenta não
deixa você mesmo decidir sobre ela — nem se o seu papel permitir aquela etapa. É
segregação de função, e não tem exceção.

**Versão publicada não se edita.** Para mudar um ativo publicado é preciso abrir uma
revisão. A versão antiga continua vigente para quem consome, até a nova ser aprovada. Nada
é sobrescrito: cada publicação vira uma revisão numerada, com hash.

---

## Negócio

`negocio`

Você responde pelo **significado**: que domínios a empresa tem, que capacidades eles
entregam, e o que é crítico de verdade. A tecnologia entra depois; sem o seu nome nas
coisas, ela não tem onde se apoiar.

**O que você faz**

- Cadastrar e editar Domínio, Subdomínio, Bounded Context e Capacidade
- Ser owner negocial de um ativo
- Enviar para validação e abrir revisão
- Decidir a etapa **negocial** das validações

**O que a ferramenta recusa**

- Registrar relações entre ativos — quem implementa o quê é informação técnica: peça ao
  tech lead
- Importar descobertas e triar a bandeja — é o caminho do time técnico
- Descontinuar um ativo publicado — fica com curador, arquiteto ou admin

**Sua rotina**

1. Abra **Minha mesa** e veja as análises que já são suas. *(Menu › Trabalhar › Minha mesa)*
2. Não tendo nada, pegue uma da fila livre — **assuma** para os outros saberem que está com você.
3. No painel de decisão, leia **o que mudou** na revisão. O sistema mostra o antes e o
   depois, já resumido, sem o ruído dos campos automáticos. *(Validações › Analisar)*
4. Confira as evidências e o checklist de governança ao lado.
5. Aprove ou rejeite **sempre com parecer**. Rejeição devolve o ativo ao autor como
   rascunho e o avisa — o parecer é o que ele vai ler.
6. Deixe marcado "ir para a próxima da fila" e despache tudo de uma sentada.

> **Cadastrando uma capacidade?** Comece pelo contexto delimitado a que ela pertence — a
> ferramenta exige o pai. E preencha o *resultado esperado*: é campo obrigatório e sem ele
> a publicação trava no primeiro passo do checklist.

---

## Tech lead

`tech_lead`

Você responde pela **realidade técnica**: o que existe de fato, onde roda, e o que conversa
com o quê. É o seu registro que transforma "acho que essa API é usada por alguém" em uma
resposta.

**O que você faz**

- Cadastrar Sistema, Aplicação, Repositório, API, Endpoint, Base de dados, Objeto de dado e Evento
- Registrar relações, inclusive em lote
- Importar descobertas de OpenAPI e inventário Git
- Triar a bandeja do que a máquina trouxe
- Decidir a etapa **técnica** das validações

**O que a ferramenta recusa**

- Descontinuar um ativo publicado — a saída de uso passa por curador, arquiteto ou admin
- Decidir etapas negocial e arquitetural — a menos que você seja o responsável formal
  daquele ativo

**Sua rotina: trazer um sistema inteiro para o catálogo**

1. Cadastre o **Sistema** e as **Aplicações** na mão — são poucos e ninguém descobre
   sozinho. *(Menu › Trabalhar › Novo ativo)*
2. Vá em **Descobertas**, cole o contrato OpenAPI, escolha a aplicação de destino e clique
   em **Gerar prévia**. Nada é gravado ainda: você vê exatamente o que será criado.
   *(Menu › Trabalhar › Descobertas)*
3. Confirme a importação. A API e um endpoint por operação entram como rascunho, marcados
   como *descoberta automática*.
4. Na **bandeja de triagem**, aceite o que faz sentido e descarte o que não deveria estar
   no catálogo. Aceitar não muda o cadastro — só marca que uma pessoa olhou.
5. Abra cada rascunho e complete a semântica: descrição, criticidade, squad. A máquina
   trouxe o observável; o significado é seu.
6. Use **Registrar várias de uma vez** na aba Relações para ligar a aplicação a tudo o que
   ela expõe ou consome, com o mecanismo (síncrono, assíncrono, batch) aplicado ao
   conjunto. *(Visão 360° › Relações › Registrar várias de uma vez)*
7. Envie para validação. O checklist mostra o que ainda falta antes de deixar.

> **O campo mecanismo importa.** É ele que responde depois "essa dependência é uma chamada
> síncrona que derruba a aplicação, ou um batch noturno que pode esperar?". Preencher custa
> um clique e poupa uma reunião.

---

## Arquiteto

`arquiteto`

Você responde pela **coerência do todo**: se os limites entre contextos fazem sentido, se
um contrato novo não cria um acoplamento que ninguém vai conseguir desfazer, e o que quebra
quando algo muda.

**O que você faz**

- Decidir a etapa **arquitetural** — a última barreira antes de publicar contratos e contextos
- Registrar relações entre ativos
- Cadastrar e editar qualquer tipo de ativo
- Descontinuar ativos que saem de uso

**O que a ferramenta recusa**

- Importar descobertas e triar a bandeja — é operação do time técnico e da curadoria
- Decidir sobre uma revisão que você mesmo submeteu

**Sua rotina: decidir com o impacto à vista**

1. Na fila, filtre pela aba **Arquitetural** — só o que exige o seu olhar.
   *(Menu › Trabalhar › Validações › Arquitetural)*
2. Leia o diff da revisão. Mudança de contrato aparece em "Campos do tipo" e em "Relações".
3. Antes de aprovar, abra o **grafo** do ativo e suba para 2 saltos: você vê quem depende
   dele além dos vizinhos diretos. *(Visão 360° › Relações › Ver como grafo)*
4. O cartão **Quem depende deste ativo** lista os consumidores vigentes e destaca os de
   alta criticidade. É a lista que vai sentir a mudança.
5. Decida com parecer. Se rejeitar, diga o que precisa mudar — o autor recebe o seu texto.

> **Quando o grafo avisa que foi cortado**, é porque a vizinhança passou do teto de ativos.
> Reduza a distância ou filtre por tipo de relação: o que ficou de fora continua existindo,
> e a ferramenta prefere avisar a mentir sobre o alcance.

---

## Curador

`curador`

Você **mantém o cadastro vivo**. Catálogo desatualizado vira ficção em dois trimestres, e é
o seu trabalho que impede isso: achar o que está órfão, incompleto ou velho, e fazer alguém
resolver.

**O que você faz**

- Cadastrar e editar qualquer tipo de ativo
- Registrar relações, inclusive em lote
- Importar descobertas e triar a bandeja
- Enviar para validação e abrir revisão
- Descontinuar ativos que saem de uso

**O que a ferramenta recusa**

- Decidir validações — por desenho: quem cuida do cadastro não é quem o aprova. Você
  prepara, outra pessoa valida

**Sua rotina: caçar o que está apodrecendo**

1. Comece pelo **painel executivo**. Todo número ali é clicável e leva ao recorte que ele
   resume. *(Menu › Visão executiva)*
2. Clique em **Sem responsável**: são ativos publicados que ninguém responde. Cada um é um
   dono a descobrir.
3. Em **Pendências prioritárias**, ataque "capacidade sem owner" e "API sem capacidade
   vinculada" — são os que quebram o painel de cobertura.
4. No catálogo, filtre por **origem: descoberta automática** para ver o que a máquina
   trouxe e ninguém revisou. *(Catálogo › Origem do cadastro)*
5. Ordene por **Qualidade crescente**: os piores scores primeiro. Abra cada um e siga o
   **caminho até a publicação** — cinco passos, e cada um leva à aba que resolve a
   pendência.
6. Complete, submeta, e deixe a validação com quem valida.

> **Você não decide validação, e isso é de propósito.** Se a mesma pessoa preenchesse e
> aprovasse, o rito seria decorativo. Quando precisar destravar uma fila parada, chame quem
> tem o papel da etapa — não peça o papel para si.

---

## Administrador

`admin`

Você faz tudo o que os outros fazem, concede os papéis e mantém a máquina rodando.
Justamente por isso, é o papel a distribuir com mais cuidado.

**O que você faz**

- Todas as ações de cadastro, relação, importação e descontinuação
- Decidir qualquer etapa de validação
- Conceder papéis a pessoas, global ou por domínio
- Operar os comandos de manutenção

**O que nem você escapa**

- Decidir sobre uma revisão que você mesmo submeteu — a segregação de função não tem
  exceção de papel
- Editar uma versão publicada sem abrir revisão

**Conceder um papel** — pela linha de comando, no servidor:

```bash
flask --app catalogo conceder ana.torres negocio              # papel global
flask --app catalogo conceder ana.torres negocio --dominio 3  # só no domínio de id 3
```

O escopo por domínio é o mais saudável em escala: a pessoa decide no que conhece. A
ferramenta resolve o domínio de qualquer ativo subindo a hierarquia, então um papel
concedido no domínio vale para os endpoints abaixo dele.

**Manutenção que precisa de agenda**

```bash
flask --app catalogo vigiar-sla   # de hora em hora: gera avisos de prazo vencendo/vencido
flask --app catalogo notificar    # logo depois: despacha a fila de envio (idempotente)
flask --app catalogo snapshot     # uma vez por mês: materializa os indicadores do painel
flask --app catalogo qualidade    # recalcula o score de todos os ativos
```

> **Sem os dois primeiros comandos agendados, o SLA não existe na prática.** A política
> define o prazo, mas é o vigia que avisa alguém. Notificação parada na fila de envio
> aparece marcada como tal na caixa — se você vir muitas assim, o despacho não está
> rodando.

---

## Consulta

`consulta`

Você lê tudo e não altera nada. É o papel da maior parte da empresa — e o catálogo só vale
a pena se essas perguntas forem fáceis de responder.

**O que o catálogo responde para você**

- *"Quem é dono disto?"* — abra o ativo, aba **Pessoas**.
- *"O que quebra se isso mudar?"* — aba **Relações**, cartão *Quem depende deste ativo*, ou
  o **grafo** para ver além dos vizinhos.
- *"Que capacidades esse domínio tem, e quais estão implementadas?"* — **Mapas**, visão de
  negócio: capacidade sem implementação vem destacada.
- *"Que sistemas e APIs existem?"* — **Mapas**, visão de tecnologia.
- *"Esta API é oficial?"* — o **status** no topo do ativo. Só *publicado* e *em revisão* são
  consumíveis; *rascunho* não é promessa de nada.
- *"Quando isso foi revisado pela última vez, e por quem?"* — aba **Histórico**: revisões
  numeradas com hash, e a trilha de auditoria abaixo.

> **Não achou pela busca?** Ela procura em nome, código e descrição. Se o ativo não aparece,
> ou ele não está cadastrado — e vale avisar um curador — ou está arquivado. O filtro de
> status no catálogo mostra os dois casos.

---

## Tabela de referência

A matriz completa, do jeito que o sistema aplica. Se um botão não aparece para você, a
resposta está aqui — ou no modo de leitura.

### Quem pode fazer o quê

| Ação | Negócio | Tech lead | Arquiteto | Curador | Admin | Consulta |
| --- | :---: | :---: | :---: | :---: | :---: | :---: |
| Cadastrar ativos | sim | sim | sim | sim | sim | — |
| Editar rascunho | sim | sim | sim | sim | sim | — |
| Registrar relação | — | sim | sim | sim | sim | — |
| Enviar para validação | sim | sim | sim | sim | sim | — |
| Abrir revisão | sim | sim | sim | sim | sim | — |
| Decidir validação | sim | sim | sim | — | sim | — |
| Importar descobertas | — | sim | — | sim | sim | — |
| Triar a bandeja | — | sim | — | sim | sim | — |
| Descontinuar ativo | — | — | sim | sim | sim | — |
| Conceder papéis | — | — | — | — | sim | — |

"Decidir validação" é permissão para **entrar na fila** — qual etapa você decide depende do
papel: *negocial* exige negócio, *técnica* exige tech lead, *arquitetural* exige arquiteto.
Admin decide qualquer uma. E em qualquer caso, o **responsável formal** do ativo pode
decidir a etapa correspondente ao papel que exerce sobre ele.

### O rito de cada tipo de ativo

Governança proporcional: um endpoint não passa pelo mesmo rito de um contexto delimitado.
Quem define é a política do tipo e da criticidade.

| Tipo | Etapas de validação | Evidências | Score mínimo | Prazo por etapa | Revisar a cada |
| --- | --- | :---: | :---: | :---: | :---: |
| Domínio | negocial → arquitetural | 1 | 70% | 72h | 365 dias |
| Subdomínio | negocial | — | 65% | 72h | 365 dias |
| Bounded Context | negocial → técnica → arquitetural | 1 | 75% | 48h | 180 dias |
| Capacidade | negocial → técnica | 1 | 70% | 48h | 180 dias |
| Capacidade **crítica** | negocial → técnica → arquitetural | 2 | 80% | 24h | 90 dias |
| Sistema | técnica | — | 60% | 72h | 365 dias |
| Aplicação | técnica | 1 | 65% | 48h | 180 dias |
| Repositório | técnica | 1 | 60% | 72h | 180 dias |
| API | técnica → arquitetural | 1 | 70% | 48h | 120 dias |
| API **crítica** | negocial → técnica → arquitetural | 2 | 80% | 24h | 90 dias |
| Endpoint | técnica | — | 55% | 72h | 180 dias |
| Base de dados | técnica | — | 60% | 72h | 365 dias |
| Objeto de dado | técnica | — | 55% | 72h | 365 dias |
| Evento de integração | técnica → arquitetural | 1 | 70% | 48h | 120 dias |

> **Marcar um ativo como crítico aperta o rito de verdade**: mais uma etapa, mais uma
> evidência, score mais alto e metade do prazo. Use a criticidade pelo risco real, não por
> importância percebida.

---

## Quando algo não funciona

As cinco confusões mais prováveis, e o que fazer com cada uma.

**"O botão que eu usava sumiu"**
Três causas, nesta ordem: você está em **modo de leitura** (troque em *Seu perfil*); o seu
**papel** não permite aquela ação (veja a tabela acima); ou o ativo está **publicado** e
precisa de uma revisão aberta antes de aceitar mudanças.

**"Não consigo aprovar esta validação"**
Ou a **etapa exige um papel** que você não tem — a mensagem diz qual —, ou **você submeteu**
essa revisão. No segundo caso não há o que ajustar: outra pessoa precisa decidir.

**"Meu ativo não publica"**
Abra ele e olhe o **caminho até a publicação**, no topo: cinco passos com o que falta em
cada um, e cada passo leva à aba que resolve. O mais comum é evidência faltando ou score
abaixo do mínimo do tipo — e o score sobe preenchendo descrição, campos obrigatórios e
responsáveis.

**"Não recebo notificação nenhuma"**
Confira *Notificações › Preferências*. Se estiver tudo ligado e mesmo assim nada chega,
provavelmente os comandos agendados não estão rodando no servidor — fale com um
administrador. E-mail e Teams ainda estão desligados por decisão pendente: hoje o aviso
aparece no sino, dentro da ferramenta.

**"Encontrei um ativo errado ou duplicado"**
Não apague nada — o catálogo não esquece de propósito, e o histórico é o que dá valor à
trilha de auditoria. Se for duplicata vinda de importação, use a **bandeja de triagem** para
descartar (ela arquiva, preservando o registro). Se já está publicado, o caminho é
**descontinuar**, com motivo — e a ferramenta vai listar quem depende dele antes de deixar.

---

*Versão correspondente ao commit da fase 4 — identidade e papéis, notificações, grafo
navegável.*
