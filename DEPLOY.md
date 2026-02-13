# 🚀 SuvFin — Guia Completo de Deploy

## Índice

1. [Pré-requisitos](#1-pré-requisitos)
2. [Configuração do WhatsApp Cloud API (Meta)](#2-configuração-do-whatsapp-cloud-api-meta)
3. [Configuração do Anthropic (Claude AI)](#3-configuração-do-anthropic-claude-ai)
4. [Opção A: Deploy no Railway (Recomendado)](#4-opção-a-deploy-no-railway-recomendado)
5. [Opção B: Deploy no Render](#5-opção-b-deploy-no-render)
6. [Opção C: Deploy em VPS com Docker](#6-opção-c-deploy-em-vps-com-docker)
7. [Configurar Webhook na Meta](#7-configurar-webhook-na-meta)
8. [Rodar Migrations do Banco](#8-rodar-migrations-do-banco)
9. [Verificação Final](#9-verificação-final)
10. [Monitoramento e Manutenção](#10-monitoramento-e-manutenção)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Pré-requisitos

Antes de começar, você vai precisar de:

| Item | Descrição | Link |
|------|-----------|------|
| **Python 3.12+** | Runtime da aplicação | [python.org](https://python.org) |
| **Git** | Controle de versão | [git-scm.com](https://git-scm.com) |
| **Docker** (opcional) | Para deploy com containers | [docker.com](https://docker.com) |
| **Conta Meta Developer** | Para a API do WhatsApp | [developers.facebook.com](https://developers.facebook.com) |
| **Conta Anthropic** | Para a IA Claude | [console.anthropic.com](https://console.anthropic.com) |
| **Conta em provedor de hospedagem** | Railway, Render ou VPS | Ver seções abaixo |

---

## 2. Configuração do WhatsApp Cloud API (Meta)

### 2.1 Criar App na Meta

1. Acesse [developers.facebook.com](https://developers.facebook.com)
2. Clique em **"Meus Apps"** → **"Criar App"**
3. Selecione **"Outro"** → **"Business"**
4. Dê o nome **"SuvFin"** e crie

### 2.2 Adicionar WhatsApp ao App

1. No painel do app, vá em **"Adicionar produtos"**
2. Encontre **"WhatsApp"** e clique **"Configurar"**
3. Você verá a tela do WhatsApp com um **número de teste** para desenvolvimento

### 2.3 Obter Credenciais

Na seção **WhatsApp > Configuração da API**, anote:

| Variável | Onde encontrar |
|----------|----------------|
| `WHATSAPP_ACCESS_TOKEN` | Token de acesso temporário (ou crie um permanente via System User) |
| `WHATSAPP_PHONE_NUMBER_ID` | ID do número de telefone (ex: `1234567890`) |
| `WHATSAPP_BUSINESS_ACCOUNT_ID` | ID da conta Business |

### 2.4 Token Permanente (Produção)

O token temporário expira em 24h. Para produção:

1. Vá em **Configurações do Negócio** → **Usuários do Sistema**
2. Crie um **System User** com role de Admin
3. Gere um token com as permissões:
   - `whatsapp_business_messaging`
   - `whatsapp_business_management`
4. Use este token no `WHATSAPP_ACCESS_TOKEN`

### 2.5 Número de Produção

Para usar em produção, você precisa:
1. Verificar seu negócio na Meta (enviar documentos)
2. Adicionar um número de telefone real
3. Concluir o processo de aprovação (pode levar alguns dias)

---

## 3. Configuração do Anthropic (Claude AI)

1. Acesse [console.anthropic.com](https://console.anthropic.com)
2. Crie uma conta e faça login
3. Vá em **"API Keys"** → **"Create Key"**
4. Copie a chave e salve como `ANTHROPIC_API_KEY`

> **Custo estimado:** ~$0.003 por mensagem processada (Claude Sonnet)

---

## 4. Opção A: Deploy no Railway (Recomendado)

O Railway é a opção mais simples — faz deploy direto do GitHub com banco e Redis inclusos.

### 4.1 Criar Conta

1. Acesse [railway.app](https://railway.app) e faça login com GitHub

### 4.2 Criar Projeto

1. Clique **"New Project"** → **"Deploy from GitHub Repo"**
2. Selecione o repositório **SuvFin**
3. Railway vai detectar o `Dockerfile` automaticamente

### 4.3 Adicionar PostgreSQL

1. No projeto, clique **"+ New"** → **"Database"** → **"PostgreSQL"**
2. Railway cria o banco e gera a variável `DATABASE_URL` automaticamente
3. Copie a URL no formato `postgresql+asyncpg://...` (mude o scheme de `postgresql://` para `postgresql+asyncpg://`)

### 4.4 Adicionar Redis

1. Clique **"+ New"** → **"Database"** → **"Redis"**
2. Railway gera a variável `REDIS_URL` automaticamente

### 4.5 Configurar Variáveis de Ambiente

No serviço do app, vá em **"Variables"** e adicione:

```env
# App
APP_ENV=production
APP_PORT=8000
APP_DEBUG=false

# Database (ajustar o scheme)
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/dbname

# Redis (copiar do serviço Redis)
REDIS_URL=redis://default:pass@host:port

# WhatsApp
WHATSAPP_API_VERSION=v21.0
WHATSAPP_ACCESS_TOKEN=seu_token
WHATSAPP_PHONE_NUMBER_ID=seu_phone_id
WHATSAPP_BUSINESS_ACCOUNT_ID=seu_business_id
WEBHOOK_VERIFY_TOKEN=crie_um_token_seguro_aleatorio

# Claude AI
ANTHROPIC_API_KEY=sk-ant-sua_chave
ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

### 4.6 Deploy

1. Railway faz deploy automático a cada push no `main`
2. Aguarde o build completar (~2-3 minutos)
3. Copie a **URL pública** gerada (ex: `suvfin-production.up.railway.app`)

### 4.7 Domínio Customizado (Opcional)

1. No serviço, vá em **"Settings"** → **"Networking"** → **"Custom Domain"**
2. Adicione `api.suvfin.com` (ou o domínio que preferir)
3. Configure o DNS CNAME no seu provedor de domínio

### 4.8 Custo

| Recurso | Custo Railway |
|---------|---------------|
| App (2 workers) | ~$5/mês |
| PostgreSQL | ~$5/mês |
| Redis | ~$5/mês |
| **Total** | **~$15/mês** |

---

## 5. Opção B: Deploy no Render

### 5.1 Criar Conta

1. Acesse [render.com](https://render.com) e faça login com GitHub

### 5.2 Criar Web Service

1. Clique **"New"** → **"Web Service"**
2. Conecte o repositório **SuvFin**
3. Configure:
   - **Environment:** Docker
   - **Region:** Ohio ou mais próxima
   - **Instance Type:** Starter ($7/mês)

### 5.3 Criar PostgreSQL

1. **"New"** → **"PostgreSQL"**
2. Nome: `suvfin-db`
3. Copie a **Internal Database URL** e altere scheme para `postgresql+asyncpg://`

### 5.4 Criar Redis

1. **"New"** → **"Redis"**
2. Nome: `suvfin-redis`
3. Copie a **Internal Redis URL**

### 5.5 Variáveis de Ambiente

Mesmas variáveis da Seção 4.5, ajustando as URLs do banco e Redis do Render.

### 5.6 Deploy Hook (para CI/CD)

1. Em **Settings** → **Deploy Hook**, copie a URL
2. Adicione como secret `RENDER_DEPLOY_HOOK` no GitHub

---

## 6. Opção C: Deploy em VPS com Docker

Para quem quer controle total (AWS EC2, DigitalOcean, Hetzner, etc.)

### 6.1 Criar VPS

1. Crie um servidor com:
   - **OS:** Ubuntu 22.04+ ou Debian 12+
   - **RAM:** 2GB mínimo
   - **Disco:** 20GB SSD
   - **CPU:** 1 vCPU
2. Provedores recomendados:
   - **Hetzner** (~€4/mês) — melhor custo-benefício
   - **DigitalOcean** ($6/mês)
   - **AWS EC2** t3.micro (free tier 12 meses)

### 6.2 Configurar Servidor

```bash
# Conectar via SSH
ssh root@SEU_IP_DO_SERVIDOR

# Atualizar sistema
apt update && apt upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com | sh

# Instalar Docker Compose
apt install docker-compose-plugin -y

# Instalar Nginx (reverse proxy)
apt install nginx certbot python3-certbot-nginx -y

# Criar diretório do projeto
mkdir -p /opt/suvfin
cd /opt/suvfin

# Clonar repositório
git clone https://github.com/SEU_USER/SuvFin.git .
```

### 6.3 Configurar .env

```bash
# Copiar template e editar
cp .env.example .env
nano .env

# Preencher todas as variáveis (ver Seção 4.5)
# Ajustar DATABASE_URL e REDIS_URL para os containers:
# DATABASE_URL=postgresql+asyncpg://postgres:SUA_SENHA_FORTE@postgres:5432/suvfin
# REDIS_URL=redis://redis:6379/0
```

### 6.4 Subir com Docker Compose

```bash
# Build e subir todos os serviços
docker compose up -d --build

# Verificar se está rodando
docker compose ps

# Ver logs
docker compose logs -f app
```

### 6.5 Rodar Migrations

```bash
docker compose exec app alembic upgrade head
```

### 6.6 Configurar Nginx (HTTPS)

Criar configuração do Nginx:

```bash
nano /etc/nginx/sites-available/suvfin
```

Conteúdo:

```nginx
server {
    listen 80;
    server_name api.suvfin.com;  # Ou seu domínio

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (se necessário)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Ativar e obter certificado SSL:

```bash
# Ativar site
ln -s /etc/nginx/sites-available/suvfin /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

# Gerar certificado SSL (Let's Encrypt)
certbot --nginx -d api.suvfin.com

# Auto-renovação (já configurado automaticamente pelo certbot)
```

### 6.7 Configurar Deploy Automático (Opcional)

No GitHub, adicione os secrets:
- `VPS_HOST` — IP do servidor
- `VPS_USER` — `root` ou seu usuário
- `VPS_SSH_KEY` — Chave SSH privada

O CI/CD vai fazer deploy automático a cada push no `main`.

---

## 7. Configurar Webhook na Meta

Esta é a etapa que conecta o WhatsApp ao seu servidor. **Faça DEPOIS do deploy.**

### 7.1 Configurar URL do Webhook

1. No [Meta Developer Dashboard](https://developers.facebook.com), vá para o seu app
2. Navegue até **WhatsApp** → **Configuração**
3. Na seção **Webhook**, clique **"Editar"**
4. Preencha:
   - **URL de callback:** `https://SEU_DOMINIO/webhook`
     - Railway: `https://suvfin-production.up.railway.app/webhook`
     - Render: `https://suvfin.onrender.com/webhook`
     - VPS: `https://api.suvfin.com/webhook`
   - **Token de verificação:** O mesmo valor que você colocou em `WEBHOOK_VERIFY_TOKEN`
5. Clique **"Verificar e salvar"**

### 7.2 Assinar Campos do Webhook

Após verificar, assine os campos:
- ✅ `messages` — Receber mensagens
- ✅ `message_deliveries` — Status de entrega (opcional)
- ✅ `message_reads` — Status de leitura (opcional)

### 7.3 Testar

1. Abra o WhatsApp no celular
2. Envie uma mensagem para o número configurado
3. Verifique os logs do servidor:
   ```bash
   # Railway
   railway logs

   # Render
   Ver na aba "Logs" do dashboard

   # VPS
   docker compose logs -f app
   ```

---

## 8. Rodar Migrations do Banco

### Gerar migration inicial

```bash
# Local (dev)
alembic revision --autogenerate -m "initial_tables"
alembic upgrade head

# No Railway
railway run alembic revision --autogenerate -m "initial_tables"
railway run alembic upgrade head

# No Docker (VPS)
docker compose exec app alembic revision --autogenerate -m "initial_tables"
docker compose exec app alembic upgrade head
```

### Futuras migrations

Sempre que alterar models:

```bash
alembic revision --autogenerate -m "descricao_da_mudanca"
alembic upgrade head
```

---

## 9. Verificação Final

### Checklist de Deploy

- [ ] Servidor rodando e acessível via HTTPS
- [ ] `GET /health` retorna `{"status": "healthy"}`
- [ ] `GET /webhook?hub.mode=subscribe&hub.verify_token=SEU_TOKEN&hub.challenge=test` retorna `test`
- [ ] Webhook verificado no painel da Meta
- [ ] Banco PostgreSQL conectado (migrations rodadas)
- [ ] Redis conectado
- [ ] Variáveis de ambiente configuradas
- [ ] Token do WhatsApp válido (não expirado)
- [ ] Chave da Anthropic válida
- [ ] Enviar mensagem de teste pelo WhatsApp → receber resposta

### Teste Rápido via cURL

```bash
# Health check
curl https://SEU_DOMINIO/health

# Simular webhook (dev only)
curl -X POST https://SEU_DOMINIO/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "object": "whatsapp_business_account",
    "entry": [{
      "id": "123",
      "changes": [{
        "field": "messages",
        "value": {
          "messaging_product": "whatsapp",
          "metadata": {
            "display_phone_number": "5511999999999",
            "phone_number_id": "123"
          },
          "contacts": [{"profile": {"name": "Teste"}, "wa_id": "5511999999999"}],
          "messages": [{
            "from": "5511999999999",
            "id": "msg_test_123",
            "timestamp": "1739480400",
            "type": "text",
            "text": {"body": "Oi"}
          }]
        }
      }]
    }]
  }'
```

---

## 10. Monitoramento e Manutenção

### 10.1 Logs

```bash
# Railway
railway logs --tail

# Docker/VPS
docker compose logs -f app --tail 100
```

### 10.2 Sentry (Erros)

1. Crie conta em [sentry.io](https://sentry.io)
2. Crie projeto Python/FastAPI
3. Copie o DSN e adicione como `SENTRY_DSN`
4. Todos os erros serão reportados automaticamente

### 10.3 Backup do Banco

```bash
# Backup manual
docker compose exec postgres pg_dump -U postgres suvfin > backup_$(date +%Y%m%d).sql

# Restore
docker compose exec -T postgres psql -U postgres suvfin < backup_20260213.sql
```

### 10.4 Atualização

```bash
# VPS
cd /opt/suvfin
git pull origin main
docker compose up -d --build
docker compose exec app alembic upgrade head

# Railway/Render: Automático via push no GitHub
```

---

## 11. Troubleshooting

### "Webhook verification failed"

- Verifique se o `WEBHOOK_VERIFY_TOKEN` é exatamente igual no `.env` e no painel da Meta
- Verifique se a URL está correta e acessível (HTTPS obrigatório)
- Teste manualmente: `curl "https://SEU_DOMINIO/webhook?hub.mode=subscribe&hub.verify_token=SEU_TOKEN&hub.challenge=test"`

### "Mensagens não chegam"

- Verifique se o webhook está verificado no painel Meta
- Verifique se assinou o campo `messages`
- Veja os logs do servidor
- Verifique se o token do WhatsApp não expirou

### "Erro ao enviar resposta"

- Verifique se o `WHATSAPP_ACCESS_TOKEN` é válido
- Verifique se o `WHATSAPP_PHONE_NUMBER_ID` está correto
- Para números de teste, o destinatário precisa estar na lista de números permitidos

### "Erro de conexão com banco"

- Verifique se o `DATABASE_URL` usa o scheme `postgresql+asyncpg://`
- Verifique se o banco está acessível (host, porta, credenciais)
- Rode `alembic upgrade head` para criar as tabelas

### "Erro na API da Anthropic"

- Verifique se a `ANTHROPIC_API_KEY` está correta
- Verifique se tem crédito na conta
- Verifique se o modelo `claude-sonnet-4-20250514` está disponível

### "Rate limit da Meta"

- A API tem limite de ~80 mensagens/segundo (conta Business)
- Para trial, o limite é 250 mensagens/24h
- Para produção, solicite aumento de limite no painel da Meta

---

## Resumo dos Custos Mensais Estimados

| Serviço | Custo |
|---------|-------|
| **Railway** (app + banco + redis) | ~$15/mês |
| **Anthropic Claude** (~1000 msgs/dia) | ~$10/mês |
| **Domínio** (.com) | ~$1/mês |
| **WhatsApp Business API** | Gratuito (1000 conversas/mês) |
| **Sentry** (free tier) | Gratuito |
| **Total estimado** | **~$26/mês** |

> 💡 Para começar barato: use Railway (tem $5 de crédito grátis) + trial gratuito do Anthropic.

---

**Pronto! 🎉 Seu SuvFin está no ar e respondendo pelo WhatsApp!**
