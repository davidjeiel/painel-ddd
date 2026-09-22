#!/bin/bash
set -e

python - <<'PY'
import os
import time

import pyodbc

host = os.environ.get('CATALOGO_DB_SERVIDOR', 'catalogo-db')
port = os.environ.get('CATALOGO_DB_PORT', '1433')
user = os.environ.get('CATALOGO_DB_USUARIO', 'sa')
password = os.environ.get('CATALOGO_DB_SENHA', 'YourStrong!Passw0rd')
driver = os.environ.get('CATALOGO_DB_DRIVER', 'ODBC Driver 18 for SQL Server')

for attempt in range(1, 61):
    try:
        conn = pyodbc.connect(
            f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE=master;UID={user};PWD={password};Encrypt=no;TrustServerCertificate=yes;Timeout=5;",
            autocommit=True,
        )
        conn.close()
        print('SQL Server pronto')
        break
    except Exception as exc:
        print(f'Aguardando SQL Server ({attempt}/60): {exc}')
        time.sleep(5)
else:
    raise SystemExit('SQL Server não ficou disponível em tempo hábil')
PY

python - <<'PY'
import os
import pyodbc

host = os.environ.get('CATALOGO_DB_SERVIDOR', 'catalogo-db')
port = os.environ.get('CATALOGO_DB_PORT', '1433')
user = os.environ.get('CATALOGO_DB_USUARIO', 'sa')
password = os.environ.get('CATALOGO_DB_SENHA', 'YourStrong!Passw0rd')
driver = os.environ.get('CATALOGO_DB_DRIVER', 'ODBC Driver 18 for SQL Server')
database = os.environ.get('CATALOGO_DB_BASE', 'catalogo')

conn = pyodbc.connect(
    f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE=master;UID={user};PWD={password};Encrypt=no;TrustServerCertificate=yes;Timeout=10;",
    autocommit=True,
)
cur = conn.cursor()
cur.execute(f"SELECT 1 FROM sys.databases WHERE name = '{database}'")
if not cur.fetchone():
    cur.execute(f"CREATE DATABASE [{database}]")
    print(f'Banco {database} criado com sucesso')
else:
    print(f'Banco {database} já existe')
conn.close()
PY

flask --app catalogo init-db
flask --app catalogo seed --reset
exec flask --app catalogo run --host 0.0.0.0 --port 5000
