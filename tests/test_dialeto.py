"""Testes que não precisam de banco: a camada de linha e a varredura de dialeto.

Estes rodam em qualquer máquina, inclusive sem SQL Server e sem o driver ODBC —
de propósito. A troca de SQLite para SQL Server foi uma varredura grande, e o
que quebra silenciosamente numa varredura dessas é justamente o que nenhum teste
de integração cobre: uma consulta rara com dialeto antigo, ou um acesso a linha
por uma forma que o novo tipo não suporta.

O módulo `db` importa pyodbc no topo. Onde o driver não estiver instalado, um
substituto mínimo entra no lugar — o que se quer exercitar aqui é a classe
:class:`db.Linha`, que é código nosso e não depende do driver.
"""
from __future__ import annotations

import subprocess
import sys
import types
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

try:                                     # pragma: no cover - depende do ambiente
    import pyodbc  # noqa: F401
except ImportError:                      # pragma: no cover
    falso = types.ModuleType("pyodbc")
    falso.IntegrityError = type("IntegrityError", (Exception,), {})
    falso.SQL_CHAR = 1
    falso.SQL_WCHAR = -8
    falso.connect = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("driver ausente: este teste não conecta"))
    sys.modules["pyodbc"] = falso

from catalogo import db as banco  # noqa: E402


# ------------------------------------------------------------------- Linha
@pytest.fixture()
def linha():
    return banco.Linha(("id_item", "nome", "score"), (7, "Crédito", None))


def test_linha_le_por_nome(linha):
    assert linha["nome"] == "Crédito"
    assert linha["id_item"] == 7


def test_linha_le_por_posicao(linha):
    """Há consultas de contagem no código que leem fetchone()[0]."""
    assert linha[0] == 7
    assert linha[1] == "Crédito"


def test_linha_vira_dicionario(linha):
    """`dict(linha)` é usado em dezenas de pontos — precisa continuar valendo."""
    assert dict(linha) == {"id_item": 7, "nome": "Crédito", "score": None}


def test_linha_responde_get_e_contains(linha):
    assert linha.get("nome") == "Crédito"
    assert linha.get("inexistente") is None
    assert linha.get("inexistente", "padrão") == "padrão"
    assert "nome" in linha
    assert "inexistente" not in linha


def test_linha_guarda_nulo_sem_confundir_com_ausente(linha):
    """Coluna nula existe; coluna ausente não. Os dois casos são diferentes."""
    assert linha["score"] is None
    assert "score" in linha
    with pytest.raises(KeyError):
        linha["nao_existe"]


def test_linha_preserva_a_ordem_das_colunas(linha):
    assert list(linha.keys()) == ["id_item", "nome", "score"]
    assert list(linha.values()) == [7, "Crédito", None]


def test_erro_de_coluna_ausente_diz_qual(linha):
    with pytest.raises(KeyError) as erro:
        linha["squad"]
    assert "squad" in str(erro.value)


# ----------------------------------------------------------- lotes do schema
def test_schema_e_dividido_por_go():
    """CREATE VIEW precisa ser a primeira instrução do lote — daí o GO."""
    import re
    script = banco.SCHEMA.read_text(encoding="utf-8")
    lotes = [l for l in re.split(r"(?im)^\s*GO\s*$", script) if l.strip()]
    assert len(lotes) > 20, "o schema deveria estar dividido em vários lotes"
    for lote in lotes:
        assert lote.upper().count("CREATE OR ALTER VIEW") <= 1
    vistas = [l for l in lotes if "CREATE OR ALTER VIEW" in l.upper()]
    assert len(vistas) == 2
    for lote in vistas:
        # comentário não é instrução: o que precisa vir primeiro é o CREATE
        sem_comentario = "\n".join(
            linha for linha in lote.splitlines() if not linha.strip().startswith("--"))
        assert sem_comentario.strip().upper().startswith("CREATE OR ALTER VIEW")


def test_ordem_de_limpeza_cobre_todas_as_tabelas():
    """Se uma tabela nova ficar fora da ordem, a limpeza entre testes falha."""
    import re
    script = banco.SCHEMA.read_text(encoding="utf-8")
    criadas = set(re.findall(r"CREATE TABLE (\w+)", script))
    assert criadas, "não achei tabelas no schema"
    assert criadas == set(banco.TABELAS_EM_ORDEM), (
        criadas.symmetric_difference(set(banco.TABELAS_EM_ORDEM)))


def test_migracoes_apontam_para_tabelas_que_existem():
    import re
    script = banco.SCHEMA.read_text(encoding="utf-8")
    criadas = set(re.findall(r"CREATE TABLE (\w+)", script))
    for tabela, _coluna, _tipo in banco.MIGRACOES:
        assert tabela in criadas, tabela


# ------------------------------------------------------- varredura de dialeto
def test_nenhuma_construcao_de_sqlite_restante():
    """A rede que se pode esticar sem ter um SQL Server à mão."""
    resultado = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "verificar_dialeto.py")],
        capture_output=True, text=True)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


# ----------------------------------------------------------- cadeia de conexão
def test_cadeia_montada_do_ambiente(monkeypatch):
    monkeypatch.delenv("CATALOGO_DB_DSN", raising=False)
    monkeypatch.setenv("CATALOGO_DB_SERVIDOR", "sql.interno,1433")
    monkeypatch.setenv("CATALOGO_DB_BASE", "catalogo")
    monkeypatch.setenv("CATALOGO_DB_USUARIO", "svc")
    monkeypatch.setenv("CATALOGO_DB_SENHA", "segredo")
    cadeia = banco.cadeia_de_conexao()
    assert "SERVER=sql.interno,1433" in cadeia
    assert "DATABASE=catalogo" in cadeia
    assert "UID=svc" in cadeia
    assert "Encrypt=yes" in cadeia           # o padrão não abre exceção


def test_dsn_pronto_vence_as_partes(monkeypatch):
    monkeypatch.setenv("CATALOGO_DB_DSN", "DRIVER={x};SERVER=y")
    monkeypatch.setenv("CATALOGO_DB_SERVIDOR", "ignorado")
    assert banco.cadeia_de_conexao() == "DRIVER={x};SERVER=y"


def test_autenticacao_integrada_nao_manda_senha(monkeypatch):
    monkeypatch.delenv("CATALOGO_DB_DSN", raising=False)
    monkeypatch.setenv("CATALOGO_DB_INTEGRADA", "sim")
    cadeia = banco.cadeia_de_conexao()
    assert "Trusted_Connection=yes" in cadeia
    assert "PWD=" not in cadeia
