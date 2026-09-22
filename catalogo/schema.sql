-- Catálogo Corporativo DDD - modelo físico SQL Server (T-SQL)
-- Núcleo comum de governança (ITEM_CATALOGO) + entidades específicas por tipo
-- + relações tipadas + histórico imutável + qualidade cadastral.
--
-- Duas decisões de tradução vindas do SQLite, ambas deliberadas:
--
-- 1. DATAS COMO TEXTO ISO. As colunas de data continuam NVARCHAR no formato
--    'AAAA-MM-DD' e 'AAAA-MM-DD HH:MM:SS'. A aplicação compara e exibe essas
--    colunas como texto em dezenas de pontos (inclusive nos templates), e a
--    ordenação lexicográfica do ISO-8601 coincide com a cronológica. Trocar para
--    DATE/DATETIME2 é correto e está no roadmap, mas é mudança de comportamento
--    em toda a superfície — merece passo próprio, com os testes rodando contra
--    o banco real. Use CONVERT(..., 120) e CONVERT(..., 23) para manter o formato.
--
-- 2. CASCADE ONDE O SQL SERVER PERMITE. O SQLite aceitava ON DELETE CASCADE em
--    todos os caminhos; o SQL Server recusa múltiplos caminhos de cascata para a
--    mesma tabela (erro 1785). Onde havia dois caminhos — item_catalogo alcança
--    relacionamento_ativo por origem e por destino, e alcança notificacao direto
--    e via validacao — a cascata virou NO ACTION. Na prática nada muda: o
--    catálogo não apaga pessoa nem ativo, encerra vigência. As duas únicas
--    exclusões do código são de linha folha (preferência e relação).

-- ---------------------------------------------------------------- organização
IF OBJECT_ID(N'squad', N'U') IS NULL
CREATE TABLE squad (
    id_squad     INT IDENTITY(1,1) CONSTRAINT pk_squad PRIMARY KEY,
    codigo       NVARCHAR(40)  NOT NULL CONSTRAINT uq_squad_codigo UNIQUE,
    nome         NVARCHAR(200) NOT NULL,
    tribo        NVARCHAR(200) NULL,
    descricao    NVARCHAR(MAX) NOT NULL CONSTRAINT df_squad_descricao DEFAULT '',
    ativo        BIT NOT NULL CONSTRAINT df_squad_ativo DEFAULT 1
);
GO

IF OBJECT_ID(N'pessoa', N'U') IS NULL
CREATE TABLE pessoa (
    id_pessoa    INT IDENTITY(1,1) CONSTRAINT pk_pessoa PRIMARY KEY,
    matricula    NVARCHAR(20)  NOT NULL CONSTRAINT uq_pessoa_matricula UNIQUE,
    nome         NVARCHAR(200) NOT NULL,
    email        NVARCHAR(200) NULL,
    perfil       NVARCHAR(30)  NOT NULL CONSTRAINT df_pessoa_perfil DEFAULT 'consulta',
    id_squad     INT NULL CONSTRAINT fk_pessoa_squad REFERENCES squad(id_squad),
    ativo        BIT NOT NULL CONSTRAINT df_pessoa_ativo DEFAULT 1,
    unidade      NVARCHAR(8) NULL,               -- código de 4 dígitos da unidade
    login             NVARCHAR(120) NULL,        -- assina a trilha de auditoria
    identidade_externa NVARCHAR(200) NULL,       -- 'sub' do provedor quando houver SSO
    origem_identidade  NVARCHAR(20) NOT NULL
        CONSTRAINT df_pessoa_origem_id DEFAULT 'local'   -- local|oidc|ldap
);
GO

-- Índices filtrados: o SQL Server suporta o mesmo "único quando não nulo" que o
-- SQLite fazia com índice parcial.
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ux_pessoa_login')
CREATE UNIQUE INDEX ux_pessoa_login ON pessoa(login) WHERE login IS NOT NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ux_pessoa_identidade')
CREATE UNIQUE INDEX ux_pessoa_identidade ON pessoa(identidade_externa)
    WHERE identidade_externa IS NOT NULL;
GO

-- Papel com escopo: a governança é por domínio, a autorização também.
IF OBJECT_ID(N'atribuicao_papel', N'U') IS NULL
CREATE TABLE atribuicao_papel (
    id_atribuicao   INT IDENTITY(1,1) CONSTRAINT pk_atribuicao PRIMARY KEY,
    id_pessoa       INT NOT NULL CONSTRAINT fk_atribuicao_pessoa
                        REFERENCES pessoa(id_pessoa) ON DELETE CASCADE,
    papel           NVARCHAR(30) NOT NULL,
    escopo_tipo     NVARCHAR(20) NOT NULL
        CONSTRAINT df_atribuicao_escopo DEFAULT 'global',   -- global|dominio|squad
    escopo_id       INT NULL,          -- id_item do domínio, ou id_squad
    inicio_vigencia NVARCHAR(10) NOT NULL
        CONSTRAINT df_atribuicao_inicio DEFAULT CONVERT(NVARCHAR(10), SYSUTCDATETIME(), 23),
    fim_vigencia    NVARCHAR(10) NULL,
    concedido_por   NVARCHAR(120) NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_papel_pessoa')
CREATE INDEX ix_papel_pessoa ON atribuicao_papel(id_pessoa, fim_vigencia);
GO

-- Pleito de acesso: a pessoa se cadastra e pede um papel; quem concede é outro.
IF OBJECT_ID(N'solicitacao_acesso', N'U') IS NULL
CREATE TABLE solicitacao_acesso (
    id_solicitacao  INT IDENTITY(1,1) CONSTRAINT pk_solicitacao PRIMARY KEY,
    id_pessoa       INT NOT NULL CONSTRAINT fk_solicitacao_pessoa
                        REFERENCES pessoa(id_pessoa) ON DELETE CASCADE,
    papel_pleiteado NVARCHAR(30) NOT NULL,
    justificativa   NVARCHAR(MAX) NULL,
    status          NVARCHAR(20) NOT NULL
        CONSTRAINT df_solicitacao_status DEFAULT 'pendente',
    criado_em       NVARCHAR(19) NOT NULL
        CONSTRAINT df_solicitacao_criado DEFAULT CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120),
    decidido_por    NVARCHAR(120) NULL,
    decidido_em     NVARCHAR(19) NULL,
    papel_concedido NVARCHAR(30) NULL,
    escopo_tipo     NVARCHAR(20) NULL,
    escopo_id       INT NULL,
    resposta        NVARCHAR(MAX) NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_solicitacao_status')
CREATE INDEX ix_solicitacao_status ON solicitacao_acesso(status, criado_em);
GO

-- ------------------------------------------------------------------- núcleo
IF OBJECT_ID(N'item_catalogo', N'U') IS NULL
CREATE TABLE item_catalogo (
    id_item          INT IDENTITY(1,1) CONSTRAINT pk_item PRIMARY KEY,
    tipo_item        NVARCHAR(40)  NOT NULL,
    codigo           NVARCHAR(40)  NOT NULL CONSTRAINT uq_item_codigo UNIQUE,
    nome             NVARCHAR(200) NOT NULL,
    descricao        NVARCHAR(MAX) NULL,
    -- auto-relação: a hierarquia mora na própria tabela. Cascata é proibida em
    -- auto-referência no SQL Server, e aqui nunca foi usada.
    id_pai           INT NULL CONSTRAINT fk_item_pai REFERENCES item_catalogo(id_item),
    id_squad         INT NULL CONSTRAINT fk_item_squad REFERENCES squad(id_squad),
    status_ciclo_vida NVARCHAR(30) NOT NULL
        CONSTRAINT df_item_status DEFAULT 'rascunho',
    criticidade      NVARCHAR(20) NOT NULL
        CONSTRAINT df_item_criticidade DEFAULT 'media',   -- baixa|media|alta|critica
    atributos        NVARCHAR(MAX) NOT NULL
        CONSTRAINT df_item_atributos DEFAULT '{}',        -- campos do tipo (JSON)
    origem           NVARCHAR(20) NOT NULL
        CONSTRAINT df_item_origem DEFAULT 'manual',       -- manual|automatica
    revisao_atual    INT NULL,
    inicio_vigencia  NVARCHAR(10) NULL,
    fim_vigencia     NVARCHAR(10) NULL,
    criado_por       NVARCHAR(120) NULL,
    criado_em        NVARCHAR(19) NOT NULL
        CONSTRAINT df_item_criado DEFAULT CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120),
    atualizado_em    NVARCHAR(19) NOT NULL
        CONSTRAINT df_item_atualizado DEFAULT CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120),
    -- coluna computada só para a unicidade sem diferenciar maiúscula: não
    -- depender da collation do servidor mantém a regra igual em qualquer
    -- instância, que era o que lower(nome) garantia no SQLite.
    nome_normalizado AS LOWER(nome) PERSISTED
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_item_tipo')
CREATE INDEX ix_item_tipo ON item_catalogo(tipo_item);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_item_status')
CREATE INDEX ix_item_status ON item_catalogo(status_ciclo_vida);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_item_pai')
CREATE INDEX ix_item_pai ON item_catalogo(id_pai);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ux_item_nome_tipo')
CREATE UNIQUE INDEX ux_item_nome_tipo ON item_catalogo(tipo_item, nome_normalizado);
GO

-- --------------------------------------------------------------- ownership
IF OBJECT_ID(N'responsabilidade', N'U') IS NULL
CREATE TABLE responsabilidade (
    id_responsabilidade INT IDENTITY(1,1) CONSTRAINT pk_responsabilidade PRIMARY KEY,
    id_item      INT NOT NULL CONSTRAINT fk_resp_item
                     REFERENCES item_catalogo(id_item) ON DELETE CASCADE,
    id_pessoa    INT NOT NULL CONSTRAINT fk_resp_pessoa REFERENCES pessoa(id_pessoa),
    papel        NVARCHAR(30) NOT NULL,   -- owner_negocial|owner_tecnico|arquiteto|mantenedor
    inicio_vigencia NVARCHAR(10) NOT NULL
        CONSTRAINT df_resp_inicio DEFAULT CONVERT(NVARCHAR(10), SYSUTCDATETIME(), 23),
    fim_vigencia NVARCHAR(10) NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_resp_item')
CREATE INDEX ix_resp_item ON responsabilidade(id_item);
GO

-- --------------------------------------------------------- relações tipadas
-- Dois caminhos de cascata para a mesma tabela (origem e destino) são recusados
-- pelo SQL Server: ambas as chaves ficam sem cascata.
IF OBJECT_ID(N'relacionamento_ativo', N'U') IS NULL
CREATE TABLE relacionamento_ativo (
    id_relacao   INT IDENTITY(1,1) CONSTRAINT pk_relacao PRIMARY KEY,
    id_origem    INT NOT NULL CONSTRAINT fk_rel_origem REFERENCES item_catalogo(id_item),
    id_destino   INT NOT NULL CONSTRAINT fk_rel_destino REFERENCES item_catalogo(id_item),
    tipo_relacao NVARCHAR(40) NOT NULL,   -- implementa|expoe|consome|produz|depende_de|persiste_em
    criticidade  NVARCHAR(20) NOT NULL CONSTRAINT df_rel_criticidade DEFAULT 'media',
    mecanismo    NVARCHAR(20) NULL,       -- sincrono|assincrono|batch
    origem_evidencia NVARCHAR(20) NULL,   -- manual|git|openapi|cmdb|cicd
    inicio_vigencia NVARCHAR(10) NOT NULL
        CONSTRAINT df_rel_inicio DEFAULT CONVERT(NVARCHAR(10), SYSUTCDATETIME(), 23),
    fim_vigencia NVARCHAR(10) NULL,
    CONSTRAINT uq_relacao UNIQUE (id_origem, id_destino, tipo_relacao)
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_rel_origem')
CREATE INDEX ix_rel_origem ON relacionamento_ativo(id_origem);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_rel_destino')
CREATE INDEX ix_rel_destino ON relacionamento_ativo(id_destino);
GO

-- ----------------------------------------------------------------- governança
IF OBJECT_ID(N'politica_governanca', N'U') IS NULL
CREATE TABLE politica_governanca (
    id_politica     INT IDENTITY(1,1) CONSTRAINT pk_politica PRIMARY KEY,
    tipo_item       NVARCHAR(40) NOT NULL,
    criticidade     NVARCHAR(20) NOT NULL CONSTRAINT df_politica_crit DEFAULT '*',
    etapas          NVARCHAR(MAX) NOT NULL,   -- JSON
    evidencia_minima INT NOT NULL CONSTRAINT df_politica_evid DEFAULT 0,
    score_minimo    INT NOT NULL CONSTRAINT df_politica_score DEFAULT 60,
    sla_horas       INT NOT NULL CONSTRAINT df_politica_sla DEFAULT 48,
    periodicidade_revisao_dias INT NOT NULL CONSTRAINT df_politica_revisao DEFAULT 180,
    CONSTRAINT uq_politica UNIQUE (tipo_item, criticidade)
);
GO

IF OBJECT_ID(N'revisao_catalogo', N'U') IS NULL
CREATE TABLE revisao_catalogo (
    id_revisao     INT IDENTITY(1,1) CONSTRAINT pk_revisao PRIMARY KEY,
    id_item        INT NOT NULL CONSTRAINT fk_revisao_item
                       REFERENCES item_catalogo(id_item) ON DELETE CASCADE,
    numero_revisao INT NOT NULL,
    payload        NVARCHAR(MAX) NOT NULL,   -- snapshot JSON imutável
    payload_hash   NVARCHAR(64) NOT NULL,
    motivo         NVARCHAR(MAX) NULL,
    criado_por     NVARCHAR(120) NULL,
    criado_em      NVARCHAR(19) NOT NULL
        CONSTRAINT df_revisao_criado DEFAULT CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120),
    publicada_em   NVARCHAR(19) NULL,
    CONSTRAINT uq_revisao UNIQUE (id_item, numero_revisao)
);
GO

-- id_revisao sem cascata: item_catalogo já alcança validacao diretamente, e
-- pela revisão seria um segundo caminho.
IF OBJECT_ID(N'validacao', N'U') IS NULL
CREATE TABLE validacao (
    id_validacao INT IDENTITY(1,1) CONSTRAINT pk_validacao PRIMARY KEY,
    id_item      INT NOT NULL CONSTRAINT fk_validacao_item
                     REFERENCES item_catalogo(id_item) ON DELETE CASCADE,
    id_revisao   INT NULL CONSTRAINT fk_validacao_revisao
                     REFERENCES revisao_catalogo(id_revisao),
    etapa        NVARCHAR(30) NOT NULL,   -- negocial|tecnica|arquitetural
    situacao     NVARCHAR(20) NOT NULL
        CONSTRAINT df_validacao_situacao DEFAULT 'pendente',
    parecer      NVARCHAR(MAX) NULL,
    atribuido_a  NVARCHAR(120) NULL,      -- quem assumiu a análise (fila)
    responsavel  NVARCHAR(120) NULL,      -- quem decidiu
    prazo        NVARCHAR(19) NULL,
    criado_em    NVARCHAR(19) NOT NULL
        CONSTRAINT df_validacao_criado DEFAULT CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120),
    concluido_em NVARCHAR(19) NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_val_situacao')
CREATE INDEX ix_val_situacao ON validacao(situacao);
GO

IF OBJECT_ID(N'evidencia', N'U') IS NULL
CREATE TABLE evidencia (
    id_evidencia INT IDENTITY(1,1) CONSTRAINT pk_evidencia PRIMARY KEY,
    id_item      INT NOT NULL CONSTRAINT fk_evidencia_item
                     REFERENCES item_catalogo(id_item) ON DELETE CASCADE,
    tipo         NVARCHAR(40) NOT NULL,   -- adr|openapi|repositorio|documento|link
    titulo       NVARCHAR(300) NOT NULL,
    url          NVARCHAR(500) NULL,
    origem       NVARCHAR(20) NOT NULL CONSTRAINT df_evidencia_origem DEFAULT 'manual',
    criado_em    NVARCHAR(19) NOT NULL
        CONSTRAINT df_evidencia_criado DEFAULT CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120)
);
GO

-- ------------------------------------------------------------- notificações
-- Padrão outbox: o caso de uso grava aqui dentro da própria transação e um
-- comando agendado despacha. As chaves para item e validação ficam sem cascata
-- (seriam caminhos concorrentes a partir de item_catalogo).
IF OBJECT_ID(N'notificacao', N'U') IS NULL
CREATE TABLE notificacao (
    id_notificacao INT IDENTITY(1,1) CONSTRAINT pk_notificacao PRIMARY KEY,
    id_pessoa      INT NOT NULL CONSTRAINT fk_notif_pessoa
                       REFERENCES pessoa(id_pessoa) ON DELETE CASCADE,
    tipo           NVARCHAR(40) NOT NULL,
    id_item        INT NULL CONSTRAINT fk_notif_item REFERENCES item_catalogo(id_item),
    id_validacao   INT NULL CONSTRAINT fk_notif_validacao REFERENCES validacao(id_validacao),
    titulo         NVARCHAR(300) NOT NULL,
    corpo          NVARCHAR(MAX) NULL,
    url            NVARCHAR(500) NULL,
    chave_unica    NVARCHAR(200) NULL,    -- impede alerta repetido do mesmo fato
    criado_em      NVARCHAR(19) NOT NULL
        CONSTRAINT df_notif_criado DEFAULT CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120),
    lido_em        NVARCHAR(19) NULL,
    enviado_em     NVARCHAR(19) NULL,     -- nulo = ainda na outbox
    canal          NVARCHAR(20) NOT NULL CONSTRAINT df_notif_canal DEFAULT 'app'
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_notif_pendente')
CREATE INDEX ix_notif_pendente ON notificacao(enviado_em);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_notif_pessoa')
CREATE INDEX ix_notif_pessoa ON notificacao(id_pessoa, lido_em);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ux_notif_chave')
CREATE UNIQUE INDEX ux_notif_chave ON notificacao(chave_unica) WHERE chave_unica IS NOT NULL;
GO

IF OBJECT_ID(N'preferencia_notificacao', N'U') IS NULL
CREATE TABLE preferencia_notificacao (
    id_pessoa INT NOT NULL CONSTRAINT fk_pref_pessoa
                  REFERENCES pessoa(id_pessoa) ON DELETE CASCADE,
    tipo      NVARCHAR(40) NOT NULL,
    canal     NVARCHAR(20) NOT NULL CONSTRAINT df_pref_canal DEFAULT 'app',
    ativo     BIT NOT NULL CONSTRAINT df_pref_ativo DEFAULT 1,
    CONSTRAINT pk_preferencia PRIMARY KEY (id_pessoa, tipo, canal)
);
GO

IF OBJECT_ID(N'auditoria_evento', N'U') IS NULL
CREATE TABLE auditoria_evento (
    id_evento   INT IDENTITY(1,1) CONSTRAINT pk_auditoria PRIMARY KEY,
    id_item     INT NULL CONSTRAINT fk_auditoria_item
                    REFERENCES item_catalogo(id_item) ON DELETE CASCADE,
    acao        NVARCHAR(60) NOT NULL,
    usuario     NVARCHAR(120) NULL,
    data_hora   NVARCHAR(19) NOT NULL
        CONSTRAINT df_auditoria_data DEFAULT CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120),
    origem      NVARCHAR(20) NOT NULL CONSTRAINT df_auditoria_origem DEFAULT 'ui',
    antes       NVARCHAR(MAX) NULL,
    depois      NVARCHAR(MAX) NULL,
    correlacao  NVARCHAR(120) NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_aud_item')
CREATE INDEX ix_aud_item ON auditoria_evento(id_item);
GO

IF OBJECT_ID(N'qualidade_catalogo', N'U') IS NULL
CREATE TABLE qualidade_catalogo (
    id_qualidade  INT IDENTITY(1,1) CONSTRAINT pk_qualidade PRIMARY KEY,
    id_item       INT NOT NULL CONSTRAINT fk_qualidade_item
                      REFERENCES item_catalogo(id_item) ON DELETE CASCADE,
    data_avaliacao NVARCHAR(19) NOT NULL
        CONSTRAINT df_qualidade_data DEFAULT CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120),
    completude    INT NOT NULL,
    consistencia  INT NOT NULL,
    ownership     INT NOT NULL,
    evidencia     INT NOT NULL,
    temporalidade INT NOT NULL,
    score_total   INT NOT NULL,
    pendencias    NVARCHAR(MAX) NOT NULL CONSTRAINT df_qualidade_pend DEFAULT '[]'
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_qual_item')
CREATE INDEX ix_qual_item ON qualidade_catalogo(id_item);
GO

-- ------------------------------------------------ camada analítica (snapshot)
IF OBJECT_ID(N'snapshot_indicador', N'U') IS NULL
CREATE TABLE snapshot_indicador (
    id_snapshot INT IDENTITY(1,1) CONSTRAINT pk_snapshot PRIMARY KEY,
    competencia NVARCHAR(7)  NOT NULL,          -- AAAA-MM
    indicador   NVARCHAR(80) NOT NULL,
    recorte     NVARCHAR(80) NOT NULL CONSTRAINT df_snapshot_recorte DEFAULT 'geral',
    valor       FLOAT NOT NULL,
    gerado_em   NVARCHAR(19) NOT NULL
        CONSTRAINT df_snapshot_gerado DEFAULT CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120),
    CONSTRAINT uq_snapshot UNIQUE (competencia, indicador, recorte)
);
GO

-- --------------------------------------------------------------- visões (BI)
-- CREATE OR ALTER exige ser a primeira instrução do lote — daí o GO antes.
CREATE OR ALTER VIEW vw_item_qualidade AS
SELECT i.id_item, i.codigo, i.nome, i.tipo_item, i.status_ciclo_vida,
       i.criticidade, s.nome AS squad,
       (SELECT TOP 1 q.score_total FROM qualidade_catalogo q
         WHERE q.id_item = i.id_item ORDER BY q.id_qualidade DESC) AS score
FROM item_catalogo i
LEFT JOIN squad s ON s.id_squad = i.id_squad;
GO

CREATE OR ALTER VIEW vw_cobertura_capacidade AS
SELECT c.id_item, c.codigo, c.nome,
       (SELECT COUNT(*) FROM relacionamento_ativo r
         WHERE r.id_destino = c.id_item AND r.tipo_relacao = 'implementa'
           AND r.fim_vigencia IS NULL) AS implementacoes
FROM item_catalogo c
WHERE c.tipo_item = 'capacidade';
GO
