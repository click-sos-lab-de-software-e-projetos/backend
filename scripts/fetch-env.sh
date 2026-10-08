#!/usr/bin/env bash

set -euo pipefail

if [[ -z "${NEON_ENV_URL:-}" ]]; then
  echo "Defina NEON_ENV_URL com a URL segura fornecida pelo projeto antes de executar este script." >&2
  exit 1
fi

curl --fail --silent --show-error --location "$NEON_ENV_URL" --output .env
echo ".env baixado com sucesso. O arquivo permanece ignorado pelo Git."
