"""Catálogo Corporativo DDD - aplicação Flask sobre SQLite."""
from __future__ import annotations

import os
from pathlib import Path

import click
from flask import Flask

from . import db as banco

__version__ = "1.0.0"

RAIZ = Path(__file__).resolve().parent.parent
PADRAO_DB = str(RAIZ / "dados" / "catalogo.db")


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "catalogo-ddd-dev"),
        DATABASE=os.environ.get("CATALOGO_DB", PADRAO_DB),
        JSON_SORT_KEYS=False,
    )
    if config:
        app.config.update(config)
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)

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
        click.echo(f"Banco pronto em {app.config['DATABASE']}")

    @app.cli.command("seed")
    @click.option("--reset", is_flag=True, help="Recria o banco antes de carregar.")
    def seed_cmd(reset):
        """Carrega os dois domínios piloto com dados de exemplo."""
        if reset:
            Path(app.config["DATABASE"]).unlink(missing_ok=True)
        banco.init_db()
        con = banco.get_db()
        governanca.semear_politicas(con)
        resumo = seed.carregar(con)
        click.echo(f"Carga concluída: {resumo}")

    @app.cli.command("snapshot")
    @click.option("--competencia", default=None, help="AAAA-MM")
    def snapshot_cmd(competencia):
        """Materializa os indicadores do mês na camada analítica."""
        servicos.gerar_snapshot(banco.get_db(), competencia)
        click.echo("Snapshot gerado.")

    @app.cli.command("notificar")
    @click.option("--limite", default=200, help="Máximo de notificações por execução.")
    def notificar_cmd(limite):
        """Despacha a outbox de notificações (idempotente)."""
        from . import notificacoes
        resumo = notificacoes.despachar(banco.get_db(), limite)
        click.echo(f"Despachadas: {resumo['despachadas']} "
                   f"(sem canal disponível: {resumo['sem_canal_disponivel']})")

    @app.cli.command("vigiar-sla")
    def vigiar_sla_cmd():
        """Gera avisos de SLA vencendo e vencido para a fila pendente."""
        from . import notificacoes
        resumo = notificacoes.vigiar_sla(banco.get_db())
        click.echo(f"Vencendo: {resumo['sla_vencendo']} · "
                   f"vencidos: {resumo['sla_vencido']}")

    @app.cli.command("conceder")
    @click.argument("login")
    @click.argument("papel")
    @click.option("--dominio", default=None, type=int,
                  help="id_item do domínio; sem isso o papel é global.")
    def conceder_cmd(login, papel, dominio):
        """Concede um papel a uma pessoa (pelo login)."""
        from . import acesso
        con = banco.get_db()
        pessoa = acesso.pessoa_por_login(con, login)
        if pessoa is None:
            raise click.ClickException(f"pessoa com login '{login}' não encontrada")
        acesso.conceder(con, pessoa["id_pessoa"], papel,
                        "dominio" if dominio else "global", dominio, "cli")
        escopo = f"no domínio {dominio}" if dominio else "global"
        click.echo(f"{pessoa['nome']} agora é {papel} {escopo}.")

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
