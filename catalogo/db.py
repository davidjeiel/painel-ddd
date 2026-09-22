"""Acesso ao banco SQL Server do catálogo, via pyodbc.

Três coisas justificam este módulo existir em vez de usar o pyodbc cru:

1. **Linha com acesso por nome.** O código inteiro lê `linha["campo"]` e converte
   com `dict(linha)` — hábito herdado do driver anterior. O pyodbc devolve tuplas
   com atributos, sem acesso por chave. A classe :class:`Linha` preserva os dois
   modos: por nome e por posição, porque há consultas de contagem que leem
   `fetchone()[0]`.
2. **Identidade gerada.** O pyodbc não expõe o id da última inserção. O caminho
   confiável em
   T-SQL é a cláusula `OUTPUT INSERTED.<pk>` no próprio INSERT — `SCOPE_IDENTITY()`
   num segundo lote pode devolver nulo, porque é outro escopo.
3. **Lotes do schema.** T-SQL exige que `CREATE VIEW` seja a primeira instrução do
   lote, então o schema é dividido por `GO` antes de executar.
"""
from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path

import pyodbc
from flask import current_app, g

SCHEMA = Path(__file__).with_name("schema.sql")

# Erro de violação de unicidade/chave, para quem precisa distinguir de erro de
# regra de negócio. O pyodbc expõe a família DB-API; o código chama por este nome.
ErroIntegridade = pyodbc.IntegrityError


# --------------------------------------------------------------------- linha
class Linha(Mapping):
    """Uma linha de resultado, legível por nome e por posição.

    `dict(linha)` funciona porque a classe implementa o protocolo de mapeamento —
    `keys()` mais `__getitem__` são o que `dict()` procura primeiro.
    """

    __slots__ = ("_colunas", "_valores", "_indice")

    def __init__(self, colunas: tuple[str, ...], valores: tuple):
        self._colunas = colunas
        self._valores = tuple(valores)
        self._indice = {nome: i for i, nome in enumerate(colunas)}

    def __getitem__(self, chave):
        if isinstance(chave, int):
            return self._valores[chave]
        try:
            return self._valores[self._indice[chave]]
        except KeyError:
            raise KeyError(f"coluna ausente no resultado: {chave}") from None

    def get(self, chave, padrao=None):
        i = self._indice.get(chave)
        return padrao if i is None else self._valores[i]

    def keys(self):
        return self._colunas

    def values(self):
        return self._valores

    def __iter__(self):
        return iter(self._colunas)

    def __len__(self):
        return len(self._colunas)

    def __contains__(self, chave):
        return chave in self._indice

    def __repr__(self):
        return f"Linha({dict(zip(self._colunas, self._valores))!r})"


class Cursor:
    """Cursor que devolve :class:`Linha` em vez de tupla."""

    __slots__ = ("_cur", "_colunas")

    def __init__(self, cur):
        self._cur = cur
        self._colunas = (tuple(c[0] for c in cur.description)
                         if cur.description else ())

    def _envolver(self, bruta):
        return None if bruta is None else Linha(self._colunas, tuple(bruta))

    def fetchone(self):
        return self._envolver(self._cur.fetchone())

    def fetchall(self):
        return [Linha(self._colunas, tuple(l)) for l in self._cur.fetchall()]

    def __iter__(self):
        for bruta in self._cur:
            yield Linha(self._colunas, tuple(bruta))

    @property
    def rowcount(self):
        return self._cur.rowcount

    def close(self):
        self._cur.close()


class Conexao:
    """Conexão com a mesma superfície que o código já usava."""

    __slots__ = ("_con",)

    def __init__(self, bruta):
        self._con = bruta

    def execute(self, sql: str, params=()) -> Cursor:
        return Cursor(self._con.execute(sql, tuple(params)))

    def executemany(self, sql: str, seq) -> None:
        cur = self._con.cursor()
        cur.fast_executemany = True
        cur.executemany(sql, [tuple(p) for p in seq])
        cur.close()

    def inserir(self, sql: str, params=()) -> int:
        """INSERT que devolve a identidade gerada.

        O SQL precisa trazer a cláusula `OUTPUT INSERTED.<pk>` — explícita no
        ponto de uso, para quem lê a consulta saber de onde vem o id.
        """
        linha = self.execute(sql, params).fetchone()
        return int(linha[0])

    def executar_lotes(self, script: str) -> None:
        """Executa um script T-SQL dividido por `GO`."""
        for lote in re.split(r"(?im)^\s*GO\s*$", script):
            if lote.strip():
                self._con.execute(lote)
        self._con.commit()

    def commit(self):
        self._con.commit()

    def rollback(self):
        self._con.rollback()

    def close(self):
        self._con.close()

    @property
    def bruta(self):
        """A conexão pyodbc, para o que precisar de recurso fora deste contrato."""
        return self._con


# ----------------------------------------------------------------- conexão
def cadeia_de_conexao() -> str:
    """Monta a cadeia ODBC a partir do ambiente.

    `CATALOGO_DB_DSN` vence tudo, para o caso de a área de banco entregar a
    cadeia pronta. Fora isso, monta-se a partir das partes — que é o que o
    manifesto do pod injeta.
    """
    pronta = os.environ.get("CATALOGO_DB_DSN")
    if pronta:
        return pronta

    partes = [
        f"DRIVER={{{os.environ.get('CATALOGO_DB_DRIVER', 'ODBC Driver 18 for SQL Server')}}}",
        f"SERVER={os.environ.get('CATALOGO_DB_SERVIDOR', 'localhost,1433')}",
        f"DATABASE={os.environ.get('CATALOGO_DB_BASE', 'catalogo')}",
        f"Encrypt={os.environ.get('CATALOGO_DB_CRIPTOGRAFIA', 'yes')}",
        f"TrustServerCertificate={os.environ.get('CATALOGO_DB_CONFIAR_CERT', 'no')}",
        f"Connection Timeout={os.environ.get('CATALOGO_DB_TIMEOUT', '15')}",
    ]
    if os.environ.get("CATALOGO_DB_INTEGRADA", "").lower() in ("1", "true", "sim"):
        partes.append("Trusted_Connection=yes")
    else:
        partes.append(f"UID={os.environ.get('CATALOGO_DB_USUARIO', 'sa')}")
        partes.append(f"PWD={os.environ.get('CATALOGO_DB_SENHA', '')}")
    return ";".join(partes)


def conectar(cadeia: str) -> Conexao:
    bruta = pyodbc.connect(cadeia, autocommit=False)
    # o catálogo guarda texto livre em português; sem isto o pyodbc devolve
    # acentuação corrompida em alguns drivers
    bruta.setdecoding(pyodbc.SQL_CHAR, encoding="utf-8")
    bruta.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8")
    bruta.setencoding(encoding="utf-8")
    return Conexao(bruta)


def get_db() -> Conexao:
    if "db" not in g:
        g.db = conectar(current_app.config["DATABASE"])
    return g.db


def fechar_db(_exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


# --------------------------------------------------------------- migrações
# Colunas acrescentadas depois da primeira versão do schema. O schema é
# idempotente por `IF NOT EXISTS`, o que não altera tabela já criada — então
# banco existente recebe a coluna por ALTER.
MIGRACOES = [
    ("validacao", "atribuido_a", "NVARCHAR(120) NULL"),
    ("item_catalogo", "origem", "NVARCHAR(20) NOT NULL CONSTRAINT df_item_origem DEFAULT 'manual'"),
    ("pessoa", "login", "NVARCHAR(120) NULL"),
    ("pessoa", "identidade_externa", "NVARCHAR(200) NULL"),
    ("pessoa", "origem_identidade", "NVARCHAR(20) NOT NULL CONSTRAINT df_pessoa_origem_id DEFAULT 'local'"),
    ("pessoa", "unidade", "NVARCHAR(8) NULL"),
    ("squad", "descricao", "NVARCHAR(MAX) NOT NULL CONSTRAINT df_squad_descricao DEFAULT ''"),
]

_SQL_COLUNAS = (
    "SELECT c.name AS nome FROM sys.columns c "
    "JOIN sys.tables t ON t.object_id = c.object_id WHERE t.name = ?"
)


def migrar(con: Conexao) -> list[str]:
    """Aplica as colunas que faltam num banco já criado. Devolve o que mudou."""
    aplicadas = []
    for tabela, coluna, tipo in MIGRACOES:
        existentes = {l["nome"] for l in con.execute(_SQL_COLUNAS, (tabela,))}
        if existentes and coluna not in existentes:
            con.execute(f"ALTER TABLE {tabela} ADD {coluna} {tipo}")
            aplicadas.append(f"{tabela}.{coluna}")
    if aplicadas:
        con.commit()
    return aplicadas


def criar_schema(con: Conexao) -> None:
    con.executar_lotes(SCHEMA.read_text(encoding="utf-8"))
    migrar(con)


# Ordem de dependência: filho antes do pai. Usada para esvaziar a base sem
# derrubar o schema — é o que substitui "apagar o arquivo .db" do SQLite, e é o
# que dá isolamento entre testes sem recriar 16 tabelas a cada um.
TABELAS_EM_ORDEM = (
    "notificacao", "preferencia_notificacao", "auditoria_evento",
    "qualidade_catalogo", "evidencia", "validacao", "revisao_catalogo",
    "relacionamento_ativo", "responsabilidade", "solicitacao_acesso",
    "atribuicao_papel", "item_catalogo", "pessoa", "squad",
    "politica_governanca", "snapshot_indicador",
)


def limpar_tudo(con: Conexao) -> None:
    """Esvazia a base e reinicia as identidades.

    O `id_pai` de item_catalogo aponta para a própria tabela, e o SQL Server
    confere a restrição linha a linha — por isso a hierarquia é desfeita antes
    do DELETE. As identidades voltam a zero porque o catálogo é lido por id em
    vários lugares, e teste que espera o primeiro registro no id 1 precisa
    continuar valendo.
    """
    con.execute("UPDATE item_catalogo SET id_pai = NULL")
    con.execute("UPDATE item_catalogo SET revisao_atual = NULL")
    for tabela in TABELAS_EM_ORDEM:
        con.execute(f"DELETE FROM {tabela}")
        con.execute(
            "IF EXISTS (SELECT 1 FROM sys.identity_columns c "
            " JOIN sys.tables t ON t.object_id = c.object_id WHERE t.name = ?) "
            f"DBCC CHECKIDENT ('{tabela}', RESEED, 0) WITH NO_INFOMSGS",
            (tabela,))
    con.commit()


def init_db() -> None:
    criar_schema(get_db())


def registrar(app) -> None:
    app.teardown_appcontext(fechar_db)
