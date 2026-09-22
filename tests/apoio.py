"""Apoio comum aos testes: sessão autenticada e concessão de papéis.

Depois da F4.1 as rotas de escrita exigem uma pessoa na sessão com papel para a
ação. Os testes que exercitam a interface precisam, portanto, entrar — como
qualquer pessoa precisaria.
"""
from __future__ import annotations

from catalogo import acesso


def criar_pessoa(con, nome: str, login: str, papel: str = "admin",
                 escopo_tipo: str = "global", escopo_id: int | None = None,
                 perfil: str = "curador") -> int:
    id_pessoa = con.execute(
        "INSERT INTO pessoa (matricula, nome, perfil, login) "
        "OUTPUT INSERTED.id_pessoa VALUES (?,?,?,?)",
        (login.upper(), nome, perfil, login)).fetchone()[0]
    con.commit()
    if papel:
        acesso.conceder(con, id_pessoa, papel, escopo_tipo, escopo_id, "teste")
    return id_pessoa


def entrar(cliente, id_pessoa: int, modo: str = "edicao") -> None:
    with cliente.session_transaction() as sessao:
        sessao["id_pessoa"] = id_pessoa
        sessao["modo"] = modo


def sair(cliente) -> None:
    with cliente.session_transaction() as sessao:
        sessao.pop("id_pessoa", None)
