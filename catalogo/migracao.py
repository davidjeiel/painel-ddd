"""Carga da base SQLite do piloto para o SQL Server.

O catálogo é lido por id em vários lugares — revisão aponta item, validação
aponta revisão, notificação aponta validação —, então a migração **preserva os
ids**. Isso exige `SET IDENTITY_INSERT`, que o SQL Server só aceita numa tabela
por vez e por sessão, e obriga a percorrer as tabelas na ordem de dependência.

O que este módulo deliberadamente não faz: converter, corrigir ou completar
dado. Se o piloto tem um ativo sem responsável, ele chega assim do outro lado —
a migração não é o lugar de melhorar cadastro, e um registro alterado em trânsito
quebraria o hash das revisões, que é o que dá valor à trilha de auditoria.

    flask --app catalogo migrar-do-sqlite --origem dados/catalogo.db
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .db import TABELAS_EM_ORDEM, Conexao

# Ordem de inserção: pai antes do filho — o inverso da ordem de limpeza.
ORDEM_DE_CARGA = tuple(reversed(TABELAS_EM_ORDEM))

# Colunas que existem só no destino (computadas) e não podem ser inseridas.
COLUNAS_IGNORADAS = {"item_catalogo": {"nome_normalizado"}}

# Colunas booleanas: o SQLite guardava 0/1 em INTEGER, o destino é BIT. O
# pyodbc aceita int, mas normalizar aqui evita surpresa com valores como 2.
COLUNAS_BOOLEANAS = {
    "squad": {"ativo"},
    "pessoa": {"ativo"},
    "preferencia_notificacao": {"ativo"},
}


def _colunas_do_destino(destino: Conexao, tabela: str) -> list[str]:
    return [l["nome"] for l in destino.execute(
        "SELECT c.name AS nome FROM sys.columns c "
        "JOIN sys.tables t ON t.object_id = c.object_id "
        "WHERE t.name = ? ORDER BY c.column_id", (tabela,))]


def _colunas_da_origem(origem: sqlite3.Connection, tabela: str) -> list[str]:
    return [l["name"] for l in origem.execute(f"PRAGMA table_info({tabela})")]


def _tem_identidade(destino: Conexao, tabela: str) -> bool:
    return destino.execute(
        "SELECT COUNT(*) FROM sys.identity_columns c "
        "JOIN sys.tables t ON t.object_id = c.object_id WHERE t.name = ?",
        (tabela,)).fetchone()[0] > 0


def migrar_base(caminho_sqlite: str, destino: Conexao,
                lote: int = 500) -> dict[str, int]:
    """Copia todas as tabelas. Devolve quantas linhas foram para cada uma."""
    arquivo = Path(caminho_sqlite)
    if not arquivo.exists():
        raise FileNotFoundError(f"base de origem não encontrada: {arquivo}")

    origem = sqlite3.connect(str(arquivo))
    origem.row_factory = sqlite3.Row
    resumo: dict[str, int] = {}

    try:
        for tabela in ORDEM_DE_CARGA:
            existentes = set(_colunas_do_destino(destino, tabela))
            if not existentes:
                continue
            try:
                na_origem = _colunas_da_origem(origem, tabela)
            except sqlite3.OperationalError:
                continue            # tabela não existia na versão do piloto
            if not na_origem:
                continue

            ignorar = COLUNAS_IGNORADAS.get(tabela, set())
            colunas = [c for c in na_origem if c in existentes and c not in ignorar]
            if not colunas:
                continue

            linhas = origem.execute(
                f"SELECT {', '.join(colunas)} FROM {tabela}").fetchall()
            if not linhas:
                resumo[tabela] = 0
                continue

            booleanas = COLUNAS_BOOLEANAS.get(tabela, set())
            valores = [
                tuple(int(bool(l[c])) if c in booleanas else l[c] for c in colunas)
                for l in linhas
            ]

            identidade = _tem_identidade(destino, tabela)
            alvo = f"{', '.join(colunas)}"
            marcas = ", ".join("?" * len(colunas))
            sql = f"INSERT INTO {tabela} ({alvo}) VALUES ({marcas})"

            # IDENTITY_INSERT vale para uma tabela por vez na sessão: liga,
            # carrega, desliga — antes de tocar na próxima.
            if identidade:
                destino.execute(f"SET IDENTITY_INSERT {tabela} ON")
            for i in range(0, len(valores), lote):
                destino.executemany(sql, valores[i:i + lote])
            if identidade:
                destino.execute(f"SET IDENTITY_INSERT {tabela} OFF")
            destino.commit()
            resumo[tabela] = len(valores)

        _realinhar_identidades(destino)
        destino.commit()
    finally:
        origem.close()
    return resumo


def _realinhar_identidades(destino: Conexao) -> None:
    """Reposiciona o contador de identidade depois de inserir ids explícitos.

    Sem isto, o próximo cadastro tentaria o id 1 e esbarraria na chave primária.
    """
    for tabela in ORDEM_DE_CARGA:
        if _tem_identidade(destino, tabela):
            destino.execute(
                f"DBCC CHECKIDENT ('{tabela}', RESEED) WITH NO_INFOMSGS")


def conferir(caminho_sqlite: str, destino: Conexao) -> list[str]:
    """Compara a contagem de linhas nos dois lados. Devolve as divergências."""
    origem = sqlite3.connect(caminho_sqlite)
    origem.row_factory = sqlite3.Row
    divergencias = []
    try:
        for tabela in ORDEM_DE_CARGA:
            try:
                antes = origem.execute(f"SELECT COUNT(*) c FROM {tabela}").fetchone()["c"]
            except sqlite3.OperationalError:
                continue
            depois = destino.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
            if antes != depois:
                divergencias.append(f"{tabela}: origem {antes}, destino {depois}")
    finally:
        origem.close()
    return divergencias
