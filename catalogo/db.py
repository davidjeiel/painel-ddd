"""Acesso ao banco SQLite do catálogo."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA = Path(__file__).with_name("schema.sql")


def conectar(caminho: str) -> sqlite3.Connection:
    con = sqlite3.connect(caminho)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = conectar(current_app.config["DATABASE"])
    return g.db


def fechar_db(_exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


# Colunas acrescentadas depois da primeira versão do schema. `CREATE TABLE IF NOT
# EXISTS` não altera tabela existente, então bancos antigos precisam do ALTER.
MIGRACOES = [
    ("validacao", "atribuido_a", "TEXT"),
    ("item_catalogo", "origem", "TEXT NOT NULL DEFAULT 'manual'"),
    ("pessoa", "login", "TEXT"),
    ("pessoa", "identidade_externa", "TEXT"),
    ("pessoa", "origem_identidade", "TEXT NOT NULL DEFAULT 'local'"),
    ("pessoa", "unidade", "TEXT"),
]


def migrar(con: sqlite3.Connection) -> list[str]:
    """Aplica as colunas que faltam num banco já criado. Devolve o que mudou."""
    aplicadas = []
    for tabela, coluna, tipo in MIGRACOES:
        existentes = {l["name"] for l in con.execute(f"PRAGMA table_info({tabela})")}
        if existentes and coluna not in existentes:
            con.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
            aplicadas.append(f"{tabela}.{coluna}")
    if aplicadas:
        con.commit()
    return aplicadas


def criar_schema(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    con.commit()
    migrar(con)


def init_db() -> None:
    criar_schema(get_db())


def registrar(app) -> None:
    app.teardown_appcontext(fechar_db)
