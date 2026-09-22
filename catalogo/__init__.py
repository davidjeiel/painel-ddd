"""Catálogo Corporativo DDD - aplicação Flask sobre SQL Server."""
from __future__ import annotations

import os
from pathlib import Path

import click
from flask import Flask

from . import db as banco

__version__ = "1.0.0"

RAIZ = Path(__file__).resolve().parent.parent


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "catalogo-ddd-dev"),
        # cadeia ODBC, montada do ambiente — ver db.cadeia_de_conexao()
        DATABASE=banco.cadeia_de_conexao(),
        JSON_SORT_KEYS=False,
    )
    if config:
        app.config.update(config)

    banco.registrar(app)

    with app.app_context():
        banco.init_db()

    from . import api, web
    app.register_blueprint(web.bp)
    app.register_blueprint(api.bp)
    registrar_comandos(app)
    return app


def registrar_comandos(app: Flask) -> None:
    from . import governanca, seed, servicos

    @app.cli.command("init-db")
    def init_db_cmd():
        """Cria o schema do banco."""
        banco.init_db()
        governanca.semear_politicas(banco.get_db())
        click.echo("Schema e políticas aplicados.")

    @app.cli.command("seed")
    @click.option("--reset", is_flag=True, help="Recria o banco antes de carregar.")
    def seed_cmd(reset):
        """Carrega os dois domínios piloto com dados de exemplo."""
        banco.init_db()
        con = banco.get_db()
        if reset:
            # não se apaga o banco: esvazia-se. O schema e as permissões da
            # base em produção não pertencem à aplicação.
            banco.limpar_tudo(con)
        governanca.semear_politicas(con)
        resumo = seed.carregar(con)
        click.echo(f"Carga concluída: {resumo}")

    @app.cli.command("snapshot")
    @click.option("--competencia", default=None, help="AAAA-MM")
    def snapshot_cmd(competencia):
        """Materializa os indicadores do mês na camada analítica."""
        servicos.gerar_snapshot(banco.get_db(), competencia)
        click.echo("Snapshot gerado.")

    @app.cli.command("migrar-do-sqlite")
    @click.option("--origem", required=True, help="Caminho do arquivo .db do piloto.")
    @click.option("--limpar/--sem-limpar", default=False,
                  help="Esvazia o destino antes de carregar.")
    def migrar_do_sqlite_cmd(origem, limpar):
        """Carrega a base SQLite do piloto no SQL Server, preservando os ids."""
        from . import migracao
        banco.init_db()
        con = banco.get_db()
        if limpar:
            banco.limpar_tudo(con)
        resumo = migracao.migrar_base(origem, con)
        for tabela, n in resumo.items():
            click.echo(f"  {tabela}: {n}")
        divergencias = migracao.conferir(origem, con)
        if divergencias:
            click.echo("Divergências na conferência:")
            for d in divergencias:
                click.echo(f"  {d}")
            raise click.ClickException("a carga não bateu linha a linha")
        click.echo(f"Carga conferida: {sum(resumo.values())} linhas.")

    @app.cli.command("qualidade")
    def qualidade_cmd():
        """Recalcula o score de qualidade de todos os ativos."""
        from . import qualidade as q
        con = banco.get_db()
        ids = [l["id_item"] for l in con.execute("SELECT id_item FROM item_catalogo")]
        for id_item in ids:
            q.registrar(con, id_item)
        con.commit()
        click.echo(f"{len(ids)} ativos reavaliados.")
