"""Configuração comum da suíte, agora que o banco é SQL Server.

A decisão de projeto foi paridade total com produção: os testes rodam contra uma
instância SQL Server real, não contra um substituto. Isso traz um problema que o
SQLite resolvia de graça — isolamento entre testes. Criar um banco por teste é
inviável (`CREATE DATABASE` custa segundos) e recriar dezesseis tabelas por teste
também. A saída: **o schema nasce uma vez por sessão e os dados são esvaziados
entre um teste e outro**, com as identidades reiniciadas, para que um teste que
espera o primeiro registro no id 1 continue valendo.

Aponte `CATALOGO_TESTE_DSN` para uma base **descartável**: a suíte apaga todos os
dados dela a cada teste. Sem a variável, a suíte não roda — cair na cadeia padrão
apagaria dados de verdade, e esse é exatamente o tipo de acidente que não se
conserta depois.

    export CATALOGO_TESTE_DSN="DRIVER={ODBC Driver 18 for SQL Server};\\
    SERVER=localhost,1433;DATABASE=catalogo_teste;UID=sa;PWD=...;\\
    Encrypt=yes;TrustServerCertificate=yes"
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from catalogo import create_app, db as banco  # noqa: E402

DSN = os.environ.get("CATALOGO_TESTE_DSN", "")

MOTIVO = ("defina CATALOGO_TESTE_DSN apontando para uma base SQL Server "
          "descartável — a suíte apaga os dados dela a cada teste")


@pytest.fixture(scope="session")
def base_de_testes() -> str:
    """Garante o schema uma vez por sessão e devolve a cadeia de conexão."""
    if not DSN:
        pytest.skip(MOTIVO)
    aplicacao = create_app({"DATABASE": DSN, "TESTING": True, "SECRET_KEY": "teste"})
    with aplicacao.app_context():
        banco.init_db()
    return DSN
