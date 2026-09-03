#!/usr/bin/env bash
# Publica este repositório no GitHub.
# Uso:  ./scripts/publicar-no-github.sh <usuario> [nome-do-repo]
set -euo pipefail

USUARIO="${1:?informe seu usuário do GitHub}"
REPO="${2:-catalogo-ddd}"

if command -v gh >/dev/null 2>&1; then
  gh repo create "$USUARIO/$REPO" --public --source=. --remote=origin --push
else
  echo "GitHub CLI não encontrado. Crie o repositório vazio em github.com/new e rode:"
  echo "  git remote add origin git@github.com:$USUARIO/$REPO.git"
  echo "  git push -u origin main"
fi
