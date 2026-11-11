# Deploy da demo no Render (passo a passo)

Três serviços, todos no plano gratuito:

| Serviço | Tipo no Render | Origem |
|---------|----------------|--------|
| `click-sos-backend` | Web Service (Python) | este repositório, via `render.yaml` |
| `click-sos-evolution` | Web Service (Docker image) | `evoapicloud/evolution-api:latest` |
| `click-sos-consentimento` | Static Site | repositório `tela-consentimento` |

Os nomes acima viram as URLs `https://<nome>.onrender.com`. Se o Render acrescentar um sufixo
(nome já usado), use a URL que ele mostrar em todos os passos abaixo.

Faça na ordem: Neon → Evolution → backend → página de consentimento → app.

## 1. Neon: banco separado para a Evolution

A Evolution guarda a sessão do WhatsApp no Postgres dela. **Nunca** use o `neondb`.

1. No console do Neon, abra o projeto do Click S.O.S → **Databases** → **New database**, nome `evolution`.
2. Em **Connection details**, escolha o banco `evolution` e copie a URL (`postgresql://...?sslmode=require`).
   Ela será o `DATABASE_CONNECTION_URI` do passo 2.
3. Copie também a URL do `neondb` (banco do backend), para o `DATABASE_URL` do passo 3.

## 2. Evolution API

1. Gere uma chave longa: `openssl rand -hex 32`. Ela é o `AUTHENTICATION_API_KEY` aqui e o `EVOLUTION_API_KEY` no backend.
2. Render → **New** → **Web Service** → **Existing image** → `evoapicloud/evolution-api:latest`.
3. Nome `click-sos-evolution`, região a mesma do backend, plano **Free**.
4. Variáveis de ambiente:

   | Chave | Valor |
   |-------|-------|
   | `PORT` | `8080` |
   | `SERVER_URL` | `https://click-sos-evolution.onrender.com` |
   | `AUTHENTICATION_API_KEY` | a chave do item 1 |
   | `DATABASE_PROVIDER` | `postgresql` |
   | `DATABASE_CONNECTION_URI` | URL do banco `evolution` (passo 1) |
   | `DATABASE_SAVE_DATA_INSTANCE` | `true` (a sessão sobrevive a reinícios, sem novo QR code) |
   | `CACHE_REDIS_ENABLED` | `false` |
   | `CACHE_LOCAL_ENABLED` | `true` |

5. Depois do deploy, crie a instância e conecte o número (com `EVOLUTION_API_URL` e `EVOLUTION_API_KEY` exportados no terminal):

   ```bash
   export EVOLUTION_API_URL=https://click-sos-evolution.onrender.com
   export EVOLUTION_API_KEY=<a chave do item 1>
   curl -X POST "$EVOLUTION_API_URL/instance/create" -H "apikey: $EVOLUTION_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"instanceName": "click-sos-demo", "integration": "WHATSAPP-BAILEYS", "qrcode": true}'
   ```

   Leia o QR code em `$EVOLUTION_API_URL/manager` (WhatsApp → *Aparelhos conectados*) e confira:

   ```bash
   curl "$EVOLUTION_API_URL/instance/connectionState/click-sos-demo" -H "apikey: $EVOLUTION_API_KEY"
   ```

   O estado deve ser `open`.

## 3. Backend

1. Render → **New** → **Blueprint** → escolha este repositório. O Render lê o `render.yaml` e cria `click-sos-backend`.
2. Preencha as variáveis `sync: false`:

   | Chave | Valor |
   |-------|-------|
   | `DATABASE_URL` | URL do `neondb` (passo 1) |
   | `CORS_ORIGIN_REGEX` | `https://click-sos-consentimento\.onrender\.com` |
   | `CONSENTIMENTO_URL_BASE` | `https://click-sos-consentimento.onrender.com/` |
   | `EVOLUTION_API_URL` | `https://click-sos-evolution.onrender.com` |
   | `EVOLUTION_API_KEY` | a chave do passo 2 |
   | `EVOLUTION_INSTANCE` | `click-sos-demo` |

   `JWT_SECRET_KEY` é gerada pelo Render. Cada deploy roda `alembic upgrade head` antes do `uvicorn`.
3. Confira: `curl https://click-sos-backend.onrender.com/health` e abra `/docs`.

## 4. Página de consentimento

1. No repositório `tela-consentimento`, troque em `src/config.js`:

   ```js
   export const API_BASE_URL = "https://click-sos-backend.onrender.com";
   ```

   Faça commit e push.
2. Render → **New** → **Static Site** → repositório `tela-consentimento`.
   Nome `click-sos-consentimento`, **Build command** vazio, **Publish directory** `.`.
3. Confira: abra a URL; sem `#token=...`, a página mostra a tela de link inválido.

## 5. App Flutter (build da demo)

```bash
flutter build apk --dart-define=USE_FAKE_API=false \
  --dart-define=API_BASE_URL=https://click-sos-backend.onrender.com/api/v1
```

## 6. Teste de ponta a ponta

1. No app: cadastrar, entrar, adicionar um contato com o **seu** número e enviar o pedido de consentimento.
2. Abrir o link recebido e tocar em "Aceito".
3. Acionar o S.O.S e conferir que o status chega a `ENVIADO` e a mensagem chega no WhatsApp.

## 7. Dia da apresentação

O plano gratuito dorme depois de ~15 minutos sem requisições.

1. Uns 30 minutos antes, acorde os dois serviços:
   `curl https://click-sos-backend.onrender.com/health` e `curl https://click-sos-evolution.onrender.com/`.
2. Confira `connectionState` (passo 2.5). Se não estiver `open`, leia o QR code de novo.
3. Mantenha os dois acordados durante a apresentação:

   ```bash
   while sleep 600; do
     curl -s -o /dev/null https://click-sos-backend.onrender.com/health
     curl -s -o /dev/null https://click-sos-evolution.onrender.com/
   done
   ```

4. Mande um S.O.S de teste para o seu número antes de começar. Desligue o ping (Ctrl+C) depois.
