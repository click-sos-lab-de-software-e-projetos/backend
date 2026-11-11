#!/usr/bin/env bash
# Sobe o Click S.O.S inteiro (backend, tela-consentimento e app Flutter) a partir de um único .env.
#
#   scripts/run.sh local [--sem-app] [--device ID]   tudo na máquina: PostGIS e Evolution no Docker
#   scripts/run.sh dev   [--sem-app] [--device ID]   backend local ligado no branch dev do Neon
#   scripts/run.sh shell local|dev|prod              abre um shell com as variáveis do perfil
#   scripts/run.sh verificar local|dev|prod          mostra o que o perfil usaria, sem segredos
#   scripts/run.sh parar                             para os containers do perfil local
#
# O .env tem cada variável com sufixo _LOCAL, _DEV e _PROD; o script exporta a do perfil com o
# nome sem sufixo, que é o que o código lê. Valores com & precisam de aspas.
# Os repositórios frontend e tela-consentimento ficam ao lado deste (../frontend e ../tela-consentimento).

set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
PROJETO="$(dirname "$RAIZ")"
FRONTEND="${CLICK_SOS_FRONTEND:-$PROJETO/frontend}"
TELA="${CLICK_SOS_TELA:-$PROJETO/tela-consentimento}"
ARQUIVO_ENV="${CLICK_SOS_ENV_FILE:-$RAIZ/.env}"
VENV="$RAIZ/.venv/bin"

POR_PERFIL="DATABASE_URL CORS_ORIGIN_REGEX CONSENTIMENTO_URL_BASE EVOLUTION_API_URL EVOLUTION_API_KEY EVOLUTION_INSTANCE API_BASE_URL"
REDE=clicksos
CONTAINER_DB=clicksos-db
CONTAINER_EVO_DB=clicksos-evolution-db
CONTAINER_EVO=clicksos-evolution
PORTA_WEB_FLUTTER=5600

PIDS=""

erro() { echo "run.sh: $*" >&2; exit 1; }
aviso() { echo "==> $*"; }

uso() {
  sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

# Lê um campo de uma URL sem passá-la na linha de comando (não aparece no ps).
campo_url() {
  URL_LIDA="$1" CAMPO="$2" python3 -c '
import os, urllib.parse as u
p = u.urlsplit(os.environ["URL_LIDA"])
print({"host": p.hostname, "porta": p.port, "usuario": p.username, "senha": p.password,
       "banco": p.path.lstrip("/")}[os.environ["CAMPO"]] or "")'
}

carregar_perfil() {
  local perfil="$1" sufixo nome valor
  case "$perfil" in
    local) sufixo=LOCAL ;; dev) sufixo=DEV ;; prod) sufixo=PROD ;;
    *) erro "perfil desconhecido: $perfil (use local, dev ou prod)" ;;
  esac
  [[ -f "$ARQUIVO_ENV" ]] || erro "não achei $ARQUIVO_ENV (copie o .env.example)"

  set -a
  # shellcheck disable=SC1090
  . "$ARQUIVO_ENV"
  set +a

  for nome in $POR_PERFIL; do
    valor="$(printenv "${nome}_${sufixo}" || true)"
    export "$nome=$valor"
  done
  export CLICK_SOS_PERFIL="$perfil"

  [[ -n "${DATABASE_URL:-}" ]] || erro "DATABASE_URL_${sufixo} está vazia no .env"
  [[ -n "${JWT_SECRET_KEY:-}" ]] || erro "JWT_SECRET_KEY está vazia no .env"

  if [[ "$perfil" == dev ]]; then
    local prod="${DATABASE_URL_PROD:-}"
    if [[ -n "$prod" ]] && { [[ "$DATABASE_URL" == "$prod" ]] ||
        [[ "$(campo_url "$DATABASE_URL" host)" == "$(campo_url "$prod" host)" ]]; }; then
      erro "DATABASE_URL_DEV aponta para o mesmo banco da produção; use a URL do branch dev do Neon"
    fi
  fi
}

verificar() {
  local nome valor
  echo "Perfil: $CLICK_SOS_PERFIL (arquivo: $ARQUIVO_ENV)"
  for nome in $POR_PERFIL; do
    valor="$(printenv "$nome" || true)"
    if [[ -z "$valor" ]]; then
      echo "  $nome: (vazia)"
    elif [[ "$nome" == *_KEY ]]; then
      echo "  $nome: definida"
    elif [[ "$valor" =~ ^[a-z+]+:// ]]; then
      local host porta
      host="$(campo_url "$valor" host)"; porta="$(campo_url "$valor" porta)"
      echo "  $nome: ${host}${porta:+:$porta}"
    else
      echo "  $nome: $valor"
    fi
  done
}

porta_livre() {
  ! lsof -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1 || erro "a porta $1 já está em uso ($2)"
}

garantir_docker() {
  command -v docker >/dev/null || erro "Docker não encontrado"
  if ! docker info >/dev/null 2>&1; then
    command -v colima >/dev/null || erro "Docker parado e Colima não encontrado"
    aviso "Iniciando o Colima"
    colima start >/dev/null
  fi
  docker network inspect "$REDE" >/dev/null 2>&1 || docker network create "$REDE" >/dev/null
}

# subir_container NOME ARGS_DO_DOCKER_RUN...: reaproveita o container se já existir.
subir_container() {
  local nome="$1"; shift
  if [[ "$(docker inspect -f '{{.State.Running}}' "$nome" 2>/dev/null)" == true ]]; then
    return
  elif docker inspect "$nome" >/dev/null 2>&1; then
    docker start "$nome" >/dev/null
  else
    docker run -d --name "$nome" --network "$REDE" "$@" >/dev/null
  fi
}

esperar_postgres() {
  local container="$1" usuario="$2" i
  for i in $(seq 1 60); do
    docker exec "$container" pg_isready -U "$usuario" >/dev/null 2>&1 && sleep 2 && return
    sleep 2
  done
  erro "o Postgres de $container não respondeu"
}

subir_banco_local() {
  local host porta usuario senha banco
  host="$(campo_url "$DATABASE_URL" host)"
  [[ "$host" == localhost || "$host" == 127.0.0.1 ]] || erro "DATABASE_URL_LOCAL precisa apontar para localhost"
  porta="$(campo_url "$DATABASE_URL" porta)"; porta="${porta:-5432}"
  usuario="$(campo_url "$DATABASE_URL" usuario)"
  senha="$(campo_url "$DATABASE_URL" senha)"
  banco="$(campo_url "$DATABASE_URL" banco)"

  aviso "PostGIS local em localhost:$porta ($CONTAINER_DB)"
  subir_container "$CONTAINER_DB" -p "$porta:5432" \
    -e POSTGRES_USER="$usuario" -e POSTGRES_PASSWORD="$senha" -e POSTGRES_DB="$banco" \
    -v clicksos-db-data:/var/lib/postgresql/data postgis/postgis:16-3.4
  esperar_postgres "$CONTAINER_DB" "$usuario"
}

subir_evolution_local() {
  if [[ -z "${EVOLUTION_API_URL:-}" || -z "${EVOLUTION_API_KEY:-}" ]]; then
    aviso "Sem EVOLUTION_API_URL_LOCAL/KEY: a Evolution não sobe e os alertas viram ERRO"
    return
  fi
  local porta
  porta="$(campo_url "$EVOLUTION_API_URL" porta)"; porta="${porta:-8080}"

  aviso "Evolution API em localhost:$porta ($CONTAINER_EVO)"
  subir_container "$CONTAINER_EVO_DB" \
    -e POSTGRES_USER=evolution -e POSTGRES_PASSWORD=evolution -e POSTGRES_DB=evolution \
    -v clicksos-evolution-db-data:/var/lib/postgresql/data postgres:16
  esperar_postgres "$CONTAINER_EVO_DB" evolution
  subir_container "$CONTAINER_EVO" -p "$porta:8080" \
    -e AUTHENTICATION_API_KEY="$EVOLUTION_API_KEY" \
    -e SERVER_URL="$EVOLUTION_API_URL" \
    -e DATABASE_PROVIDER=postgresql \
    -e DATABASE_CONNECTION_URI="postgresql://evolution:evolution@$CONTAINER_EVO_DB:5432/evolution" \
    -e DATABASE_SAVE_DATA_INSTANCE=true \
    -e CACHE_REDIS_ENABLED=false -e CACHE_LOCAL_ENABLED=true \
    evoapicloud/evolution-api:latest

  local i estado=""
  for i in $(seq 1 45); do
    curl -fs -o /dev/null "$EVOLUTION_API_URL/" && break
    sleep 2
  done
  estado="$(curl -s "$EVOLUTION_API_URL/instance/connectionState/$EVOLUTION_INSTANCE" \
    -H "apikey: $EVOLUTION_API_KEY" || true)"
  if [[ "$estado" != *'"state"'* ]]; then
    aviso "Criando a instância $EVOLUTION_INSTANCE"
    curl -s -o /dev/null -X POST "$EVOLUTION_API_URL/instance/create" -H "apikey: $EVOLUTION_API_KEY" \
      -H "Content-Type: application/json" \
      -d "{\"instanceName\": \"$EVOLUTION_INSTANCE\", \"integration\": \"WHATSAPP-BAILEYS\", \"qrcode\": true}" || true
  fi
  if [[ "$estado" != *'"open"'* ]]; then
    aviso "WhatsApp desconectado: leia o QR code em $EVOLUTION_API_URL/manager (WhatsApp → Aparelhos conectados)"
  fi
}

parar_processos() {
  trap - EXIT INT TERM
  if [[ -n "$PIDS" ]]; then
    aviso "Parando backend e tela-consentimento"
    # shellcheck disable=SC2086
    kill $PIDS 2>/dev/null || true
    wait 2>/dev/null || true
  fi
}

subir_backend() {
  [[ -x "$VENV/uvicorn" ]] || erro "crie o venv: python -m venv .venv && .venv/bin/pip install -e '.[dev]'"
  porta_livre 8000 "backend"
  aviso "Migrações (alembic upgrade head)"
  (cd "$RAIZ" && "$VENV/alembic" upgrade head)
  aviso "Backend em http://localhost:8000 (docs em /docs)"
  (cd "$RAIZ" && exec "$VENV/uvicorn" app.main:app --reload --app-dir src --host 0.0.0.0 --port 8000) &
  PIDS="$PIDS $!"
}

subir_tela() {
  [[ -d "$TELA" ]] || { aviso "tela-consentimento não encontrada em $TELA; pulando"; return; }
  local porta api
  porta="$(campo_url "${CONSENTIMENTO_URL_BASE:-http://localhost:5500/}" porta)"; porta="${porta:-5500}"
  porta_livre "$porta" "tela-consentimento"
  api="${API_BASE_URL%/api/v1}"
  printf '// Gerado por backend/scripts/run.sh; não versionar.\nglobalThis.CLICK_SOS_ENV = { API_BASE_URL: "%s" };\n' "$api" > "$TELA/env.js"
  aviso "tela-consentimento em http://localhost:$porta"
  (cd "$TELA" && exec python3 -m http.server "$porta" >/dev/null 2>&1) &
  PIDS="$PIDS $!"
}

esperar_backend() {
  local i
  for i in $(seq 1 30); do
    curl -fs -o /dev/null http://localhost:8000/health && return
    sleep 1
  done
  erro "o backend não respondeu em /health"
}

subir_app() {
  local device="$1" api="$API_BASE_URL"
  [[ -d "$FRONTEND" ]] || erro "frontend não encontrado em $FRONTEND"
  command -v flutter >/dev/null || erro "flutter não encontrado"
  local extras=()
  case "$device" in
    emulator-*) api="${api/localhost/10.0.2.2}" ;;
    chrome|web-server) extras=(--web-port "$PORTA_WEB_FLUTTER") ;;
  esac
  aviso "App Flutter ($device) usando $api"
  (cd "$FRONTEND" && flutter run -d "$device" ${extras[@]+"${extras[@]}"} \
    --dart-define=USE_FAKE_API="${USE_FAKE_API:-false}" --dart-define=API_BASE_URL="$api")
}

subir_tudo() {
  local perfil="$1"; shift
  local sem_app=false device=chrome
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --sem-app) sem_app=true ;;
      --device) shift; device="${1:?--device precisa de um id (veja flutter devices)}" ;;
      *) erro "opção desconhecida: $1" ;;
    esac
    shift
  done

  carregar_perfil "$perfil"
  verificar
  if [[ "$perfil" == local ]]; then
    garantir_docker
    subir_banco_local
    subir_evolution_local
  fi

  trap parar_processos EXIT INT TERM
  subir_backend
  esperar_backend
  subir_tela

  if [[ "$sem_app" == true ]]; then
    aviso "Tudo no ar. Ctrl+C para parar."
    wait
  else
    subir_app "$device"
  fi
}

parar_containers() {
  local nome
  for nome in "$CONTAINER_EVO" "$CONTAINER_EVO_DB" "$CONTAINER_DB"; do
    docker stop "$nome" >/dev/null 2>&1 && aviso "Parado: $nome" || true
  done
  aviso "Os dados ficam nos volumes do Docker. Para desligar o Colima: colima stop"
}

[[ $# -ge 1 ]] || uso 1
comando="$1"; shift
case "$comando" in
  local|dev) subir_tudo "$comando" "$@" ;;
  shell)
    [[ $# -eq 1 ]] || uso 1
    carregar_perfil "$1"
    [[ "$1" != prod ]] || aviso "ATENÇÃO: perfil prod, comandos aqui mexem nos dados reais"
    aviso "Shell com o perfil $1. Saia com exit."
    cd "$RAIZ" && exec "${SHELL:-bash}"
    ;;
  verificar) [[ $# -eq 1 ]] || uso 1; carregar_perfil "$1"; verificar ;;
  parar) parar_containers ;;
  -h|--help|ajuda) uso 0 ;;
  *) uso 1 ;;
esac
