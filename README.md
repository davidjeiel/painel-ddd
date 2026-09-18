# Catálogo Corporativo DDD

Implementação em Python + SQLite da proposta consolidada de catálogo corporativo DDD:
hierarquia de negócio governada, ativos técnicos desacoplados, ownership explícito,
validação em etapas, revisões imutáveis, qualidade cadastral e painel executivo.

O objetivo é o MVP descrito no roadmap da proposta (fases 1 e 2), pronto para o piloto
de dois domínios, sem dependências além do Flask.

## Como rodar

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

flask --app catalogo seed --reset   # cria o banco e carrega os dois domínios piloto
python run.py                       # http://localhost:5000
```

Comandos disponíveis:

| Comando | O que faz |
| --- | --- |
| `flask --app catalogo init-db` | Cria o schema e as políticas padrão |
| `flask --app catalogo seed --reset` | Recria o banco com o cenário piloto |
| `flask --app catalogo qualidade` | Recalcula o score de todos os ativos |
| `flask --app catalogo snapshot` | Materializa os indicadores do mês |
| `flask --app catalogo notificar` | Despacha a outbox de notificações (idempotente) |
| `flask --app catalogo vigiar-sla` | Gera avisos de SLA vencendo e vencido |
| `flask --app catalogo conceder <login> <papel>` | Concede papel (use `--dominio` para escopo) |

O banco fica em `dados/catalogo.db` (configurável pela variável `CATALOGO_DB`).

Colunas acrescentadas depois da primeira versão do schema ficam em `db.MIGRACOES` e são
aplicadas automaticamente na abertura do banco — `CREATE TABLE IF NOT EXISTS` não altera
tabela existente, então um banco antigo recebe o `ALTER` sem precisar de recarga.

## Telas

Quatro experiências nucleares, como recomendado na proposta:

- **Visão executiva** (`/`) — KPIs clicáveis (cada número leva ao recorte que resume),
  variação contra a competência anterior, cobertura por domínio, qualidade cadastral,
  pendências prioritárias com drill-through e evolução mensal.
- **Catálogo de ativos** (`/catalogo`) — busca, filtros persistentes por sessão
  (retomados quando a tela é aberta sem parâmetros), chips de filtro ativo com
  remoção individual, recortes "somente sem responsável" e por origem do cadastro,
  ordenação por coluna e paginação com o total real.
- **Wizard de cadastro** (`/ativo/novo`) — campos dinâmicos por tipo de ativo,
  contexto herdado do pai e checklist do que a política exige.
- **Visão 360°** (`/ativo/<id>`) — abas de Resumo, Relações, Pessoas, Evidências e
  Histórico (`?aba=`), com os formulários de escrita dentro da aba a que pertencem, e o
  **caminho até a publicação**: cinco passos com o estado real derivado do pré-check,
  cada um levando à aba que resolve a pendência.
- **Grafo navegável** (`/ativo/<id>/grafo`) — vizinhança de 1 a 3 saltos sobre as relações
  transversais, em anéis por distância, com filtro por tipo e teto explícito: quando o
  recorte é cortado, a tela avisa em vez de mentir sobre o alcance da mudança.
- **Cadastro e pleito de acesso** (`/acesso/solicitar`) — a única tela de escrita aberta
  a quem ainda não tem papel: matrícula (uma letra e seis números), nome, e-mail,
  unidade (quatro números) e o papel pleiteado. O cadastro não concede nada.
- **Pleitos de acesso** (`/acessos`) — fila de quem pediu papel, para curador e
  administrador: conceder o papel pedido, conceder outro ou negar, sempre com resposta
  escrita, e com o alcance (global, um domínio ou uma squad) escolhido na concessão.
  Só administrador concede o papel de administrador.
- **Seu perfil** (`/perfil`) — quem assina as publicações e o modo de trabalho
  (edição ou leitura).
- **Notificações** (`/notificacoes`) — caixa e preferências por evento e canal.
- **Minha mesa** (`/meu-trabalho`) — análises que você assumiu, fila livre para assumir,
  seus rascunhos e seus ativos aguardando decisão de terceiros.
- **Central de validações** (`/validacoes`) — fila priorizada por criticidade e SLA, com
  o diff da revisão em análise, evidências e responsáveis no painel de decisão,
  atribuição da análise e "ir para a próxima da fila" depois de decidir.
- **Mapas** (`/mapa`) — as duas hierarquias do modelo, colapsáveis e com busca dentro da
  árvore: negócio (Domínio → Subdomínio → Contexto → Capacidade, com cobertura de
  implementação) e tecnologia (`?visao=tecnica`: Sistema → Aplicação → API → Endpoint,
  Base de dados → Objeto de dado).
- **Descobertas** (`/descobertas`) — importa contrato OpenAPI e inventário Git pela
  interface, com **prévia antes de gravar** e bandeja de triagem dos itens que a máquina
  trouxe: aceitar tira da bandeja sem mexer no cadastro, descartar arquiva.
- **Cartilha de uso** (`/cartilha`) — guia por perfil: o que cada papel faz, o que a
  ferramenta recusa e por quê, a rotina que resolve o dia e as tabelas de referência.
  A matriz de permissões é lida de `acesso.PERMISSOES` e a tabela de ritos, das
  políticas cadastradas — a página não consegue descrever regra que o sistema já não
  aplica. Alcançável do rodapé de qualquer tela e do atalho ao lado da identificação.

### Aparência

- **Tema noturno** com três estados: claro, escuro e o do sistema operacional. A escolha
  fica em `localStorage` e é aplicada por um script no `<head>`, antes do CSS, para a tela
  clara não piscar antes do escuro. Toda a paleta é token em `:root`, redefinida em
  `@media (prefers-color-scheme: dark)` (guardado por `:root:not([data-tema="claro"])`,
  para a escolha manual vencer o sistema) e em `:root[data-tema="escuro"]`. Nenhuma cor
  fixa fora da declaração dos tokens — há teste que garante isso.
- **Menu lateral recolhível**: de 224px para um trilho de 68px com as iniciais de cada
  item, mantendo `title` e o rótulo para leitor de tela. A preferência também persiste em
  `localStorage`. No celular o menu já é uma barra horizontal, e o controle some.

Em todas as telas: busca global no cabeçalho (`/` ou `Ctrl+K` para focar, sugestões
instantâneas por `/busca/sugestoes`), trilha hierárquica clicável nas telas de ativo e
destaque de menu por família de rota — abrir um ativo não apaga mais o "você está aqui".

## Modelo de dados

`ITEM_CATALOGO` é o núcleo comum: identidade, tipo, hierarquia, status de ciclo de vida,
criticidade, vigência, revisão corrente e `origem` (`manual` ou `automatica`, o que separa
o cadastro humano do que veio de uma integração). As particularidades de cada tipo ficam em
`atributos` (JSON) e são declaradas em `catalogo/tipos.py`, o que mantém a semântica das
entidades da proposta (Domínio, Subdomínio, Bounded Context, Capacidade, Sistema,
Aplicação, Repositório, API, Endpoint, Base de dados, Objeto de dado, Evento) sem
replicar a mecânica de governança em dezenas de tabelas.

Ao redor do núcleo:

- `RESPONSABILIDADE` — ownership por papel, com vigência.
- `RELACIONAMENTO_ATIVO` — grafo tipado (implementa, expõe, consome, produz, depende de,
  persiste em) com criticidade, mecanismo e origem da evidência. `tipos.DESTINOS_SUGERIDOS`
  orienta o formulário sobre quais tipos fazem sentido em cada relação — é sugestão que
  filtra a lista, não proibição: quem cadastra pode pedir todos os tipos.
- `POLITICA_GOVERNANCA` — etapas de validação, evidência mínima, score mínimo, SLA e
  periodicidade de revisão por tipo e criticidade.
- `REVISAO_CATALOGO` — snapshot imutável com hash SHA-256 por publicação.
- `VALIDACAO` — etapas abertas por revisão, com `atribuido_a` (quem assumiu a análise) e
  `responsavel` (quem decidiu). `EVIDENCIA`, `AUDITORIA_EVENTO`, `QUALIDADE_CATALOGO`.
- `SNAPSHOT_INDICADOR` e as visões `vw_item_qualidade` e `vw_cobertura_capacidade`,
  para a camada analítica consumir sem bater no modelo operacional.

Detalhes em [`docs/MODELO.md`](docs/MODELO.md).

## Acesso e papéis

A fonte de identidade ainda é o cadastro local — a pessoa da sessão é escolhida em
`/perfil`. Quando a decisão corporativa sair, o SSO troca apenas *de onde* ela vem:
`pessoa.identidade_externa` e `origem_identidade` já existem para receber o `sub` do
provedor, e papéis, escopos e regras não mudam.

- `atribuicao_papel` guarda papel × escopo (`global`, `dominio` ou `squad`). O escopo do
  item sai da própria trilha hierárquica: quem responde "Domínio › Contexto" responde
  também por qual domínio autoriza.
- `acesso.pode(con, pessoa, acao, item)` é o ponto único de decisão; o decorador
  `@exige(acao)` aplica nas rotas de escrita. **Esconder o botão não é autorização** — a
  rota recusa o formulário enviado direto.
- Cada etapa de validação exige o papel correspondente (`negocial` → negócio, `tecnica` →
  tech lead, `arquitetural` → arquiteto), ou que a pessoa seja o responsável formal do
  ativo. E quem submeteu a revisão não decide sobre ela.

## Notificações

Padrão **outbox**: o caso de uso grava a notificação na mesma transação do fato que a
gerou, e `flask --app catalogo notificar` despacha depois. Sem broker, sem serviço
auxiliar, testável com o mesmo banco dos testes; se o volume crescer, o mesmo contrato
migra para uma fila real sem reescrever caso de uso nenhum.

Eventos: revisão submetida (para quem pode decidir aquela etapa), SLA vencendo e vencido,
revisão rejeitada (para o autor) e ativo publicado (para quem responde pelos
consumidores). Os canais de e-mail e Teams ficam declarados e desligados até a fonte de
identidade ser decidida — sem ela não há endereço confiável para onde mandar.

## Regras de governança implementadas

- **Ciclo de vida**: rascunho → em validação → publicado → em revisão →
  descontinuado → arquivado, com transições validadas.
- **Versão publicada é imutável**: alterar exige abrir revisão; cada publicação gera
  uma nova revisão com hash e trilha de auditoria.
- **Pré-check antes da submissão**: campos obrigatórios, hierarquia, ownership exigido,
  duplicidade de nome, dependência circular, evidência mínima, relações com ativos fora
  de vigência e score mínimo.
- **Governança proporcional**: as etapas de validação vêm da política do tipo e da
  criticidade — um endpoint não passa pelo mesmo rito de um contexto crítico.
- **Rejeição devolve ao autor**: as demais etapas da revisão são canceladas.
- **Descontinuação com impacto**: bloqueada quando há consumidores ativos de alta
  criticidade, salvo confirmação de plano de migração.
- **Qualidade cadastral**: score ponderado de completude, consistência, ownership,
  evidência e temporalidade, com pendências acionáveis.

## API interna

```
GET  /api/v1/itens?termo=&tipo_item=&status=
POST /api/v1/itens
GET  /api/v1/itens/<id>                 visão 360° completa
GET  /api/v1/itens/<id>/vizinhanca?saltos=&tipo=
GET  /api/v1/itens/<id>/qualidade
GET  /api/v1/itens/<id>/precheck
POST /api/v1/itens/<id>/submeter
POST /api/v1/itens/<id>/relacoes
GET  /api/v1/validacoes?etapa=
POST /api/v1/validacoes/<id>
GET  /api/v1/indicadores
POST /api/v1/snapshots
```

## Descoberta automática

`catalogo/integracoes.py` importa contratos OpenAPI (cria a API e seus endpoints) e
inventários Git em JSON. Os itens descobertos nascem em rascunho com `origem = 'automatica'`
e evidência de procedência: a máquina traz o que é observável, a pessoa valida a semântica.

Cada importador tem um par — `plano_*` diz o que aconteceria sem escrever nada e
`importar_*` executa. É o que sustenta a prévia da tela `/descobertas`.

```python
from catalogo.integracoes import plano_openapi, importar_openapi, importar_repositorios
plano_openapi(con, "contratos/simulacao.json", id_aplicacao=13)      # só simula
importar_openapi(con, "contratos/simulacao.json", id_aplicacao=13)   # grava
importar_repositorios(con, "inventario-git.json", id_aplicacao=13)
```

Pela interface é o mesmo caminho: cole o JSON, gere a prévia, confirme — e triar a bandeja
depois. Nada é publicado automaticamente.

## Testes

```bash
pip install pytest
pytest -q
```

`tests/test_governanca.py` cobre hierarquia inválida, duplicidade, pré-check sem owner,
fluxo completo até a publicação, imutabilidade do publicado, rejeição, dependência
circular, bloqueio de descontinuação e evolução do score.

`tests/test_jornada.py` cobre a navegação: trilha hierárquica, destaque de menu dentro de
um ativo, sugestões da busca global, filtros retomados e limpos, recorte sem responsável,
KPIs que levam ao recorte, leitura da variação mensal e o formulário de cadastro que
devolve tudo o que foi digitado depois de um erro de regra de negócio.

`tests/test_fluxo.py` cobre o fluxo de trabalho: abas da visão 360°, o checklist de
publicação (inclusive a garantia de que nenhum bloqueio do pré-check fica de fora dele),
o diff resumido da revisão em análise, o loop de decisão do validador, atribuição da
análise, a mesa pessoal, a migração do banco antigo e o registro de relações com mecanismo.

`tests/test_acesso.py` cobre a fase 4: papel com escopo, etapa que exige papel,
segregação de função, recusa na rota mesmo sem passar pela tela, modo de leitura,
confirmação da descontinuação, outbox idempotente, vigia de SLA que não repete alerta e a
vizinhança do grafo com teto e filtro.

`tests/test_escala.py` cobre a escala: prévia que não escreve, importação marcando a
origem, bandeja de triagem (e a garantia de que ela não toca em cadastro humano), relações
em lote sem duplicar as existentes, paginação com total real, ordenação por coluna, as duas
árvores do mapa e o agrupamento da análise de impacto.

## Estrutura

```
catalogo/
  __init__.py      fábrica Flask e comandos de CLI
  db.py            conexão e schema
  schema.sql       modelo físico, visões e índices
  tipos.py         taxonomia dos tipos de ativo e campos do wizard
  qualidade.py     score de qualidade cadastral
  governanca.py    políticas, pré-check, ciclo de vida e fila
  servicos.py      casos de uso e consultas
  integracoes.py   descoberta automática (OpenAPI, Git)
  acesso.py        identidade, papéis com escopo e autorização
  notificacoes.py  outbox, preferências e vigia de SLA
  web.py           telas
  api.py           API JSON
  seed.py          carga dos dois domínios piloto
docs/MODELO.md     modelo de dados e decisões
tests/             regras de governança (test_governanca) e navegação (test_jornada)
```

## O que ficou fora do MVP

Integrações com CMDB/CI-CD/backlog e o modelo estrela completo para Power BI — previstos
para a fase 5 e dependentes das decisões abertas (granularidade mínima e sistema de
registro operacional). O grafo, o RBAC e as notificações foram entregues na fase 4, com a
ressalva de que a identidade ainda é local: a autenticação corporativa espera a decisão
12.1-a. As decisões abertas listadas na seção 12.1 da
proposta (fonte de identidade de pessoas, granularidade mínima, sistema de registro
operacional) continuam valendo antes da expansão corporativa.
