-- Catálogo Corporativo DDD - modelo físico SQLite
-- Núcleo comum de governança (ITEM_CATALOGO) + entidades específicas por tipo
-- + relações tipadas + histórico imutável + qualidade cadastral.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- organização
CREATE TABLE IF NOT EXISTS squad (
    id_squad     INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo       TEXT NOT NULL UNIQUE,
    nome         TEXT NOT NULL,
    tribo        TEXT,
    ativo        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS pessoa (
    id_pessoa    INTEGER PRIMARY KEY AUTOINCREMENT,
    matricula    TEXT NOT NULL UNIQUE,
    nome         TEXT NOT NULL,
    email        TEXT,
    perfil       TEXT NOT NULL DEFAULT 'consulta',  -- curador|arquiteto|tech_lead|negocio|consulta
    id_squad     INTEGER REFERENCES squad(id_squad),
    ativo        INTEGER NOT NULL DEFAULT 1
);

-- ------------------------------------------------------------------- núcleo
CREATE TABLE IF NOT EXISTS item_catalogo (
    id_item          INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_item        TEXT NOT NULL,
    codigo           TEXT NOT NULL UNIQUE,
    nome             TEXT NOT NULL,
    descricao        TEXT,
    id_pai           INTEGER REFERENCES item_catalogo(id_item),
    id_squad         INTEGER REFERENCES squad(id_squad),
    status_ciclo_vida TEXT NOT NULL DEFAULT 'rascunho',
    criticidade      TEXT NOT NULL DEFAULT 'media',   -- baixa|media|alta|critica
    atributos        TEXT NOT NULL DEFAULT '{}',      -- campos específicos do tipo (JSON)
    revisao_atual    INTEGER,
    inicio_vigencia  TEXT,
    fim_vigencia     TEXT,
    criado_por       TEXT,
    criado_em        TEXT NOT NULL DEFAULT (datetime('now')),
    atualizado_em    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS ix_item_tipo   ON item_catalogo(tipo_item);
CREATE INDEX IF NOT EXISTS ix_item_status ON item_catalogo(status_ciclo_vida);
CREATE INDEX IF NOT EXISTS ix_item_pai    ON item_catalogo(id_pai);
CREATE UNIQUE INDEX IF NOT EXISTS ux_item_nome_tipo
    ON item_catalogo(tipo_item, lower(nome));

-- --------------------------------------------------------------- ownership
CREATE TABLE IF NOT EXISTS responsabilidade (
    id_responsabilidade INTEGER PRIMARY KEY AUTOINCREMENT,
    id_item      INTEGER NOT NULL REFERENCES item_catalogo(id_item) ON DELETE CASCADE,
    id_pessoa    INTEGER NOT NULL REFERENCES pessoa(id_pessoa),
    papel        TEXT NOT NULL,               -- owner_negocial|owner_tecnico|arquiteto|mantenedor
    inicio_vigencia TEXT NOT NULL DEFAULT (date('now')),
    fim_vigencia TEXT
);
CREATE INDEX IF NOT EXISTS ix_resp_item ON responsabilidade(id_item);

-- --------------------------------------------------------- relações tipadas
CREATE TABLE IF NOT EXISTS relacionamento_ativo (
    id_relacao   INTEGER PRIMARY KEY AUTOINCREMENT,
    id_origem    INTEGER NOT NULL REFERENCES item_catalogo(id_item) ON DELETE CASCADE,
    id_destino   INTEGER NOT NULL REFERENCES item_catalogo(id_item) ON DELETE CASCADE,
    tipo_relacao TEXT NOT NULL,   -- implementa|expoe|consome|produz|depende_de|persiste_em
    criticidade  TEXT NOT NULL DEFAULT 'media',
    mecanismo    TEXT,            -- sincrono|assincrono|batch
    origem_evidencia TEXT,        -- manual|git|openapi|cmdb|cicd
    inicio_vigencia TEXT NOT NULL DEFAULT (date('now')),
    fim_vigencia TEXT,
    UNIQUE (id_origem, id_destino, tipo_relacao)
);
CREATE INDEX IF NOT EXISTS ix_rel_origem  ON relacionamento_ativo(id_origem);
CREATE INDEX IF NOT EXISTS ix_rel_destino ON relacionamento_ativo(id_destino);

-- ----------------------------------------------------------------- governança
CREATE TABLE IF NOT EXISTS politica_governanca (
    id_politica     INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_item       TEXT NOT NULL,
    criticidade     TEXT NOT NULL DEFAULT '*',
    etapas          TEXT NOT NULL,          -- JSON: ["negocial","tecnica","arquitetural"]
    evidencia_minima INTEGER NOT NULL DEFAULT 0,
    score_minimo    INTEGER NOT NULL DEFAULT 60,
    sla_horas       INTEGER NOT NULL DEFAULT 48,
    periodicidade_revisao_dias INTEGER NOT NULL DEFAULT 180,
    UNIQUE (tipo_item, criticidade)
);

CREATE TABLE IF NOT EXISTS revisao_catalogo (
    id_revisao     INTEGER PRIMARY KEY AUTOINCREMENT,
    id_item        INTEGER NOT NULL REFERENCES item_catalogo(id_item) ON DELETE CASCADE,
    numero_revisao INTEGER NOT NULL,
    payload        TEXT NOT NULL,           -- snapshot JSON imutável
    payload_hash   TEXT NOT NULL,
    motivo         TEXT,
    criado_por     TEXT,
    criado_em      TEXT NOT NULL DEFAULT (datetime('now')),
    publicada_em   TEXT,
    UNIQUE (id_item, numero_revisao)
);

CREATE TABLE IF NOT EXISTS validacao (
    id_validacao INTEGER PRIMARY KEY AUTOINCREMENT,
    id_item      INTEGER NOT NULL REFERENCES item_catalogo(id_item) ON DELETE CASCADE,
    id_revisao   INTEGER REFERENCES revisao_catalogo(id_revisao),
    etapa        TEXT NOT NULL,            -- negocial|tecnica|arquitetural
    situacao     TEXT NOT NULL DEFAULT 'pendente', -- pendente|aprovada|rejeitada
    parecer      TEXT,
    responsavel  TEXT,
    prazo        TEXT,
    criado_em    TEXT NOT NULL DEFAULT (datetime('now')),
    concluido_em TEXT
);
CREATE INDEX IF NOT EXISTS ix_val_situacao ON validacao(situacao);

CREATE TABLE IF NOT EXISTS evidencia (
    id_evidencia INTEGER PRIMARY KEY AUTOINCREMENT,
    id_item      INTEGER NOT NULL REFERENCES item_catalogo(id_item) ON DELETE CASCADE,
    tipo         TEXT NOT NULL,            -- adr|openapi|repositorio|documento|link
    titulo       TEXT NOT NULL,
    url          TEXT,
    origem       TEXT NOT NULL DEFAULT 'manual',
    criado_em    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS auditoria_evento (
    id_evento   INTEGER PRIMARY KEY AUTOINCREMENT,
    id_item     INTEGER REFERENCES item_catalogo(id_item) ON DELETE CASCADE,
    acao        TEXT NOT NULL,
    usuario     TEXT,
    data_hora   TEXT NOT NULL DEFAULT (datetime('now')),
    origem      TEXT NOT NULL DEFAULT 'ui',
    antes       TEXT,
    depois      TEXT,
    correlacao  TEXT
);
CREATE INDEX IF NOT EXISTS ix_aud_item ON auditoria_evento(id_item);

CREATE TABLE IF NOT EXISTS qualidade_catalogo (
    id_qualidade  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_item       INTEGER NOT NULL REFERENCES item_catalogo(id_item) ON DELETE CASCADE,
    data_avaliacao TEXT NOT NULL DEFAULT (datetime('now')),
    completude    INTEGER NOT NULL,
    consistencia  INTEGER NOT NULL,
    ownership     INTEGER NOT NULL,
    evidencia     INTEGER NOT NULL,
    temporalidade INTEGER NOT NULL,
    score_total   INTEGER NOT NULL,
    pendencias    TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS ix_qual_item ON qualidade_catalogo(id_item);

-- ------------------------------------------------ camada analítica (snapshot)
CREATE TABLE IF NOT EXISTS snapshot_indicador (
    id_snapshot INTEGER PRIMARY KEY AUTOINCREMENT,
    competencia TEXT NOT NULL,          -- AAAA-MM
    indicador   TEXT NOT NULL,
    recorte     TEXT NOT NULL DEFAULT 'geral',
    valor       REAL NOT NULL,
    gerado_em   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (competencia, indicador, recorte)
);

-- --------------------------------------------------------------- visões (BI)
CREATE VIEW IF NOT EXISTS vw_item_qualidade AS
SELECT i.id_item, i.codigo, i.nome, i.tipo_item, i.status_ciclo_vida,
       i.criticidade, s.nome AS squad,
       (SELECT q.score_total FROM qualidade_catalogo q
         WHERE q.id_item = i.id_item ORDER BY q.id_qualidade DESC LIMIT 1) AS score
FROM item_catalogo i
LEFT JOIN squad s ON s.id_squad = i.id_squad;

CREATE VIEW IF NOT EXISTS vw_cobertura_capacidade AS
SELECT c.id_item, c.codigo, c.nome,
       (SELECT COUNT(*) FROM relacionamento_ativo r
         WHERE r.id_destino = c.id_item AND r.tipo_relacao = 'implementa'
           AND r.fim_vigencia IS NULL) AS implementacoes
FROM item_catalogo c
WHERE c.tipo_item = 'capacidade';
