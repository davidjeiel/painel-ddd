#!/usr/bin/env python3
"""Falha se sobrar alguma construção de SQLite no código.

Esta verificação existe porque a migração para SQL Server foi uma varredura
grande e mecânica: quase oitenta pontos, em oito módulos. Um teste que roda
contra o banco prova que o que *é exercitado* funciona; esta varredura prova que
nada do dialeto antigo ficou para trás numa consulta que nenhum teste toca.

    python scripts/verificar_dialeto.py

Não substitui a suíte — é a rede que se pode estender sem ter um SQL Server à mão.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# token -> por que não pode mais aparecer
PROIBIDOS = {
    "datetime('now')": "data do SQLite; use CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120)",
    "date('now')": "data do SQLite; use CONVERT(NVARCHAR(10), SYSUTCDATETIME(), 23)",
    "LIMIT ": "paginação do SQLite; use TOP n ou OFFSET ... FETCH NEXT",
    "INSERT OR ": "upsert do SQLite; use WHERE NOT EXISTS ou UPDATE seguido de INSERT",
    "ON CONFLICT": "upsert do SQLite; use UPDATE seguido de INSERT",
    "lastrowid": "identidade do SQLite; use OUTPUT INSERTED.<pk>",
    "AUTOINCREMENT": "identidade do SQLite; use IDENTITY(1,1)",
    "PRAGMA": "pragma do SQLite; consulte sys.columns",
    "WITH RECURSIVE": "CTE do SQLite; em T-SQL é só WITH",
    "executescript": "API do sqlite3; use Conexao.executar_lotes",
    "sqlite3.Row": "API do sqlite3; a linha vem de db.Linha",
    "sqlite3.IntegrityError": "API do sqlite3; use db.ErroIntegridade",
}

# migracao.py lê a base antiga de propósito — é o único lugar onde o sqlite3
# continua legítimo, e por isso fica de fora da varredura.
ISENTOS = {"migracao.py"}


def varrer() -> list[str]:
    achados = []
    alvos = sorted(
        [p for p in (RAIZ / "catalogo").glob("*.py") if p.name not in ISENTOS]
        + [RAIZ / "catalogo" / "schema.sql"]
        + sorted((RAIZ / "tests").glob("*.py"))
    )
    for arquivo in alvos:
        texto = arquivo.read_text(encoding="utf-8")
        for token, motivo in PROIBIDOS.items():
            for achado in re.finditer(re.escape(token), texto):
                linha = texto[:achado.start()].count("\n") + 1
                achados.append(
                    f"{arquivo.relative_to(RAIZ)}:{linha}  {token!r} — {motivo}")
    return achados


def main() -> int:
    achados = varrer()
    if achados:
        print(f"{len(achados)} construção(ões) de SQLite ainda no código:\n")
        print("\n".join(f"  {a}" for a in achados))
        return 1
    print("Dialeto limpo: nenhuma construção de SQLite no código da aplicação.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
