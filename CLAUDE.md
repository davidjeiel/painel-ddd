# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Visão geral

Catálogo Corporativo DDD: aplicação Flask + SQLite (sem ORM, SQL cru via `sqlite3`)
que implementa um catálogo de ativos governado — hierarquia de negócio (Domínio →
Subdomínio → Contextos Delimitados → Capacidade) e hierarquia técnica (Sistema → Aplicação
→ API → Endpoint, Base de dados → Objeto de dado), com ciclo de vida, validação em
etapas, RBAC com escopo, qualidade cadastral e notificações via outbox.

Documentação de referência já existente no repo — leia antes de mexer no modelo ou
nas regras de governança:
- [README.md](README.md) — telas, comandos, API interna, regras de governança e o que ficou fora do MVP.
- [docs/MODELO.md](docs/MODELO.md) — decisão de modelagem (item genérico + `tipos.py`), tabelas, ciclo de vida e score de qualidade.
- [docs/CARTILHA.md](docs/CARTILHA.md) — uso por perfil de usuário.

## Comandos

```bash
python -m venv .venv && source .venv/bin/activate   # no Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pytest      # não está no requirements.txt, só é usado em dev/CI

flask --app catalogo init-db          # cria schema + políticas padrão em dados/catalogo.db
flask --app catalogo seed --reset     # recria o banco com o cenário piloto (2 domínios)
python run.py                         # serve em http://localhost:5000 (debug=True)

pytest -q                             # roda a suíte inteira
pytest -q tests/test_governanca.py    # um arquivo
pytest -q tests/test_governanca.py::test_nome_da_funcao   # um teste
```

Outros comandos de CLI (ver `catalogo/__init__.py::registrar_comandos`):
`flask --app catalogo qualidade`, `snapshot [--competencia AAAA-MM]`,
`notificar [--limite N]`, `vigiar-sla`, `conceder <login> <papel> [--dominio ID]`.

Banco em `dados/catalogo.db`, configurável via env var `CATALOGO_DB`. Não há
linter/formatter configurado no projeto. CI (`.github/workflows/testes.yml`) só roda
`pytest -q` em push/PR para `main`.

## Arquitetura

**App factory** (`catalogo/__init__.py`): `create_app()` monta o Flask, registra os
blueprints `web` (telas) e `api` (JSON) e os comandos de CLI. `catalogo/db.py` abre a
conexão SQLite por request (`g.db`, fechada no teardown) com `PRAGMA foreign_keys=ON`
e `journal_mode=WAL`.

**Schema evolutivo sem migration framework**: `catalogo/schema.sql` usa
`CREATE TABLE IF NOT EXISTS`, que não altera tabela já existente. Colunas adicionadas
depois da primeira versão do schema vivem em `db.MIGRACOES` (lista de
`(tabela, coluna, tipo)`) e são aplicadas com `ALTER TABLE` automaticamente na
abertura do banco (`db.criar_schema`/`db.migrar`). **Ao adicionar uma coluna nova,
acrescente uma entrada em `MIGRACOES`** em vez de só editar o `schema.sql`, senão
bancos já existentes (inclusive o dos testes) não recebem a coluna.

**Modelo central — item genérico, não uma tabela por tipo**: `ITEM_CATALOGO` é o
núcleo comum a todo ativo (identidade, tipo, hierarquia via `id_pai`, status de ciclo
de vida, criticidade, vigência, revisão corrente, `origem` manual/automática). Os
campos específicos de cada tipo (ex.: "linguagem ubíqua" de um Contextos Delimitados) ficam
em `atributos` (coluna JSON) e são **declarados em `catalogo/tipos.py`**
(`TIPOS: dict[str, TipoAtivo]`), não em colunas de schema. Adicionar um tipo de ativo é
uma entrada nesse dicionário, não uma migração. A validação de hierarquia (quem pode
ser pai de quem) é regra de aplicação, não constraint de banco — ver
`docs/MODELO.md`.

**Módulos de domínio** (`catalogo/`), por responsabilidade:
- `governanca.py` — políticas por tipo/criticidade (`POLITICAS_PADRAO`), pré-check de
  publicação (`pre_check`, com códigos de bloqueio reaproveitados pelo checklist
  `caminho_publicacao`), transições de ciclo de vida (`TRANSICOES`), detecção de
  dependência circular, fila de validação e o "assumir/liberar" análise.
- `qualidade.py` — score ponderado (completude, consistência, ownership, evidência,
  temporalidade) usado tanto na tela quanto como bloqueio no pré-check.
- `servicos.py` (maior módulo, ~1000 linhas) — casos de uso e consultas: CRUD de
  itens, trilha hierárquica (`trilha`, reaproveitada por `acesso._dominio_do_item`
  para achar o domínio-escopo de um item), relações, revisões/publicação (hash
  SHA-256 imutável), snapshots de indicadores.
- `acesso.py` — identidade (ainda local, via `pessoa.login`; `identidade_externa`/
  `origem_identidade` já existem para SSO futuro), papéis com escopo
  (`global`/`dominio`/`squad`), e o **ponto único de autorização**: `pode(con,
  pessoa, acao, item)`. Etapa de validação exige papel específico
  (`PAPEL_POR_ETAPA`) ou que a pessoa seja owner do ativo; quem submeteu a revisão
  não pode decidir sobre ela (`pode_decidir`, segregação de função).
- `notificacoes.py` — padrão outbox: grava na mesma transação do fato gerador,
  `notificar`/`vigiar-sla` despacham depois (idempotente).
- `integracoes.py` — descoberta automática (OpenAPI, inventário Git). Cada
  importador tem um par `plano_*` (simula, não escreve) / `importar_*` (grava),
  sustentando a prévia da tela `/descobertas`; itens descobertos nascem em
  rascunho com `origem='automatica'`.
- `web.py` (maior depois de servicos, ~800 linhas) — blueprint das telas
  server-rendered (Jinja em `catalogo/templates/`). Rotas de escrita usam o
  decorador `@exige(acao)` de `acesso` — **a rota recusa mesmo que o botão esteja
  escondido na tela**, então nunca confie só na UI para autorização.
- `api.py` — blueprint JSON (`/api/v1/...`), mesmas regras de negócio de `servicos`/
  `governanca`, sem estado de sessão de UI.
- `seed.py` — carga determinística dos dois domínios piloto, usada por
  `flask seed` e pelos testes.

**Autorização em duas camadas**: `acesso.pode()` decide a ação genérica (cadastrar,
editar, submeter, decidir, ...); `acesso.pode_decidir()` decide especificamente uma
etapa de validação, cruzando papel exigido pela etapa com ownership do ativo e
checando segregação de função. Ambas consultam papéis "efetivos" via
`papeis_efetivos`, que resolve escopo (`global` sempre conta; `dominio`/`squad`
só contam se o item pertencer àquele escopo).

**Testes** (`tests/`, pytest puro + `tests/apoio.py`): não há `conftest.py`; cada
teste cria seu próprio app com `create_app({"DATABASE": ":memory:" ou tmp_path})` e
chama `criar_pessoa`/`entrar` de `tests/apoio.py` para simular sessão autenticada,
já que rotas de escrita exigem pessoa + papel desde a fase 4. Arquivos organizados por
frente, não por módulo: `test_governanca` (regras de publicação/ciclo de vida),
`test_jornada` (navegação/UI), `test_fluxo` (fluxo de trabalho fim a fim),
`test_acesso` (RBAC/fase 4), `test_escala` (descoberta automática, paginação, mapas), `test_cartilha`
(a cartilha em `/cartilha`, e que suas tabelas continuam derivadas de `acesso.PERMISSOES`
e da tabela de políticas, não copiadas à mão).

## Front-end

Sem build step: HTML server-rendered (Jinja) + CSS puro em
`catalogo/static/estilo.css`, sem framework JS. Tema claro/escuro/sistema via tokens
CSS em `:root` (nunca cor fixa fora da declaração dos tokens — há teste que garante
isso) e preferência em `localStorage`, aplicada por script inline no `<head>` antes do
CSS para não piscar.
