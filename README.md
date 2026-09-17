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
  remoção individual, recorte "somente sem responsável", status, criticidade e score.
- **Wizard de cadastro** (`/ativo/novo`) — campos dinâmicos por tipo de ativo,
  contexto herdado do pai e checklist do que a política exige.
- **Visão 360°** (`/ativo/<id>`) — abas de Resumo, Relações, Pessoas, Evidências e
  Histórico (`?aba=`), com os formulários de escrita dentro da aba a que pertencem, e o
  **caminho até a publicação**: cinco passos com o estado real derivado do pré-check,
  cada um levando à aba que resolve a pendência.
- **Minha mesa** (`/meu-trabalho`) — análises que você assumiu, fila livre para assumir,
  seus rascunhos e seus ativos aguardando decisão de terceiros.
- **Central de validações** (`/validacoes`) — fila priorizada por criticidade e SLA, com
  o diff da revisão em análise, evidências e responsáveis no painel de decisão,
  atribuição da análise e "ir para a próxima da fila" depois de decidir.
- **Mapa DDD** (`/mapa`) — árvore Domínio → Subdomínio → Contexto → Capacidade com
  cobertura de implementação.

Em todas as telas: busca global no cabeçalho (`/` ou `Ctrl+K` para focar, sugestões
instantâneas por `/busca/sugestoes`), trilha hierárquica clicável nas telas de ativo e
destaque de menu por família de rota — abrir um ativo não apaga mais o "você está aqui".

## Modelo de dados

`ITEM_CATALOGO` é o núcleo comum: identidade, tipo, hierarquia, status de ciclo de vida,
criticidade, vigência e revisão corrente. As particularidades de cada tipo ficam em
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
inventários Git em JSON. Os itens descobertos nascem em rascunho com evidência de
origem: a máquina traz o que é observável, a pessoa valida a semântica.

```python
from catalogo.integracoes import importar_openapi, importar_repositorios
importar_openapi(con, "contratos/simulacao.json", id_aplicacao=13)
importar_repositorios(con, "inventario-git.json", id_aplicacao=13)
```

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
  web.py           telas
  api.py           API JSON
  seed.py          carga dos dois domínios piloto
docs/MODELO.md     modelo de dados e decisões
tests/             regras de governança (test_governanca) e navegação (test_jornada)
```

## O que ficou fora do MVP

Grafo navegável interativo, RBAC por perfil, notificações, importação assistida em massa,
integrações com CMDB/CI-CD/backlog e o modelo estrela completo para Power BI — todos
previstos para as fases 4 e 5 do roadmap. As decisões abertas listadas na seção 12.1 da
proposta (fonte de identidade de pessoas, granularidade mínima, sistema de registro
operacional) continuam valendo antes da expansão corporativa.
