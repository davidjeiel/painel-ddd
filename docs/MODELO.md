# Modelo de dados

## Decisão central

A proposta pede duas coisas que costumam brigar entre si: preservar as entidades
específicas do DDD e, ao mesmo tempo, não replicar ciclo de vida, versão, vigência e
auditoria em dezenas de tabelas.

A solução aqui: `ITEM_CATALOGO` carrega tudo o que é comum a qualquer ativo governado,
e cada tipo declara seus campos próprios em `catalogo/tipos.py`, gravados em
`atributos` (JSON). A hierarquia usa auto-relacionamento (`id_pai`) com o tipo do pai
validado na aplicação — Subdomínio só existe sob Domínio, Capacidade só sob Bounded
Context, Endpoint só sob API.

Consequências:

- adicionar um tipo de ativo é uma entrada em `TIPOS`, não uma migração de schema;
- workflow, qualidade, evidência e auditoria são genéricos e valem para todos;
- consultas por tipo continuam indexadas (`ix_item_tipo`);
- a validação de hierarquia sai do banco e vira regra de aplicação, testada em
  `tests/test_governanca.py`.

Se o piloto mostrar necessidade de consultas relacionais pesadas sobre campos
específicos (por exemplo, filtrar endpoints por método direto em SQL), o caminho é
promover esses campos a colunas ou criar views materializadas por tipo, sem mexer no
núcleo.

## Tabelas

| Tabela | Papel |
| --- | --- |
| `item_catalogo` | Núcleo: identidade, tipo, hierarquia, status, criticidade, vigência, revisão corrente |
| `squad`, `pessoa` | Organização; a fonte de identidade corporativa entra aqui na integração |
| `responsabilidade` | Ownership por papel com vigência (N:N pessoa × item) |
| `relacionamento_ativo` | Grafo tipado entre ativos, com criticidade, mecanismo e origem |
| `politica_governanca` | Rito por tipo e criticidade: etapas, evidência mínima, score, SLA, revisão |
| `revisao_catalogo` | Snapshot imutável com hash SHA-256 do payload publicado |
| `validacao` | Etapas abertas por revisão, com prazo, parecer e situação; `atribuido_a` é quem assumiu a análise e `responsavel`, quem decidiu |
| `evidencia` | ADR, OpenAPI, repositório, documento ou link |
| `auditoria_evento` | Quem, quando, de onde, o que antes e o que depois |
| `qualidade_catalogo` | Score materializado por dimensão, com pendências |
| `snapshot_indicador` | Série mensal para tendência na camada analítica |

## Relações estruturais fortes

Mantidas como no documento original:

```
DOMINIO → SUBDOMINIO → BOUNDED_CONTEXT → CAPACIDADE
SISTEMA → APLICACAO → API → ENDPOINT
SISTEMA → BASE_DADOS → OBJETO_DADO
APLICACAO → REPOSITORIO
BOUNDED_CONTEXT → EVENTO_INTEGRACAO
```

As relações transversais (implementa, expõe, consome, produz, depende de, persiste em)
ficam em `relacionamento_ativo`, o que permite responder às perguntas do painel sem
criar uma tabela nova por par de entidades: quem implementa a capacidade, quem consome
a API, qual contexto depende de qual.

## Ciclo de vida

| Status | Consumível oficialmente |
| --- | --- |
| rascunho | não |
| em validação | não |
| publicado | sim |
| em revisão | sim (a versão publicada continua vigente) |
| descontinuado | somente histórico |
| arquivado | somente histórico |

Transições permitidas em `governanca.TRANSICOES`. Publicar não sobrescreve: cria
revisão, marca `publicada_em` e aponta `revisao_atual`.

## Score de qualidade

| Dimensão | Peso | O que mede |
| --- | --- | --- |
| completude | 30% | Descrição e campos obrigatórios do tipo |
| consistência | 20% | Hierarquia válida, relações vigentes, capacidade com implementação |
| ownership | 20% | Papéis exigidos pelo tipo, vigentes |
| evidência | 15% | Evidências anexadas contra a mínima da política |
| temporalidade | 15% | Idade do cadastro contra a periodicidade de revisão |

O score entra no pré-check: abaixo do mínimo da política, a publicação é bloqueada.

## Camada analítica

`vw_item_qualidade` e `vw_cobertura_capacidade` servem consultas de leitura, e
`snapshot_indicador` guarda a série mensal. Para Power BI, o caminho recomendado
continua sendo o modelo estrela alimentado por ETL a partir dessas visões e dos
snapshots — não consulta direta ao modelo operacional.
