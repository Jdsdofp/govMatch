# Render Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configurar o deploy da API govMatch no Render com banco PostgreSQL, usando render.yaml declarativo.

**Architecture:** O Render constrói a imagem Docker a partir do `Dockerfile` existente, cria o banco PostgreSQL gerenciado e injeta a `DATABASE_URL` automaticamente no web service. O `config.py` já converte a URL para o formato `asyncpg`. As migrations do Alembic rodam automaticamente no start via o CMD do Dockerfile.

**Tech Stack:** Python 3.13, FastAPI, Uvicorn, SQLAlchemy async, Alembic, PostgreSQL (asyncpg), Playwright/Chromium, Render Blueprint (render.yaml)

## Global Constraints

- Python 3.13 (fixado no Dockerfile)
- O `render.yaml` deve usar `apiVersion: render/v1`
- O web service deve usar `type: web` e `runtime: docker`
- O banco deve usar `type: pgsql` com `plan: free`
- `DATABASE_URL` é injetada via `fromDatabase` — não definir manualmente
- Não commitar `.env`, `venv/`, `govmatch.db`, `tmp/`, `cache/`

---

### Task 1: Corrigir .gitignore

**Files:**
- Modify: `.gitignore`

**Interfaces:**
- Produces: `.gitignore` protegendo arquivos sensíveis e artefatos locais

- [ ] **Step 1: Substituir o conteúdo do .gitignore**

O `.gitignore` atual só tem `__pycache__/`, `*.pyc`, `*.pyo`, `*.zip`. Precisa incluir os artefatos locais que não devem ir para o repositório:

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
*.zip
*.egg-info/
dist/
build/

# Ambiente virtual
venv/
.venv/
env/

# Variáveis de ambiente
.env
.env.local

# Banco SQLite local
*.db
*.db-shm
*.db-wal

# Artefatos de scraping
tmp/
cache/

# Playwright
.playwright-mcp/

# Testes
.pytest_cache/
htmlcov/
.coverage

# IDEs
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 2: Verificar se govmatch.db está rastreado pelo git**

```bash
git ls-files govmatch.db
```

Se retornar `govmatch.db`, remover do rastreamento sem apagar o arquivo local:

```bash
git rm --cached govmatch.db
```

- [ ] **Step 3: Commitar**

```bash
git add .gitignore
git commit -m "chore: expand .gitignore for venv, .env, db, tmp, cache"
```

---

### Task 2: Criar render.yaml

**Files:**
- Create: `render.yaml`

**Interfaces:**
- Consumes: `Dockerfile` na raiz do repositório
- Produces: Blueprint do Render com serviço web + banco PostgreSQL

- [ ] **Step 1: Criar render.yaml na raiz do projeto**

```yaml
apiVersion: render/v1

services:
  - type: web
    name: govmatch-api
    runtime: docker
    plan: free
    healthCheckPath: /health
    envVars:
      - key: LOG_LEVEL
        value: INFO
      - key: PLAYWRIGHT_BROWSERS_PATH
        value: /usr/lib/chromium
      - key: PYTHONUNBUFFERED
        value: "1"
      - key: DATABASE_URL
        fromDatabase:
          name: govmatch-db
          property: connectionString

databases:
  - name: govmatch-db
    plan: free
    databaseName: govmatch
    user: govmatch
```

> **Nota:** O `healthCheckPath: /health` exige que a API tenha a rota `/health`. Verifique na Task 3 se ela existe.

- [ ] **Step 2: Commitar**

```bash
git add render.yaml
git commit -m "feat: add render.yaml for Render Blueprint deploy"
```

---

### Task 3: Verificar/criar rota /health

**Files:**
- Modify ou Create: `main.py` ou arquivo de rotas existente

**Interfaces:**
- Produces: `GET /health` retornando `{"status": "ok"}` com HTTP 200

- [ ] **Step 1: Verificar se a rota /health já existe**

```bash
grep -r "health" main.py api/
```

- [ ] **Step 2: Se não existir, adicionar em main.py**

Abrir `main.py` e adicionar após as importações e antes do primeiro router:

```python
@app.get("/health")
async def health_check():
    return {"status": "ok"}
```

- [ ] **Step 3: Testar localmente**

```bash
uvicorn main:app --reload
# Em outro terminal:
curl http://localhost:8000/health
```

Esperado: `{"status":"ok"}`

- [ ] **Step 4: Commitar (se houve alteração)**

```bash
git add main.py
git commit -m "feat: add /health endpoint for Render health check"
```

---

### Task 4: Push e deploy no Render

**Files:** nenhum — ações no terminal e no painel do Render

**Interfaces:**
- Consumes: `render.yaml` commitado no repositório GitHub

- [ ] **Step 1: Fazer push de todos os commits para o GitHub**

```bash
git push origin main
```

Confirme que os 3 commits das tasks anteriores estão no repositório remoto:

```bash
git log --oneline -5
```

- [ ] **Step 2: Acessar o painel do Render e criar o Blueprint**

1. Acesse [render.com](https://render.com) e faça login
2. Clique em **"New +"** → **"Blueprint"**
3. Conecte o repositório GitHub `govMatch/api` (ou o nome correto do repositório)
4. O Render detecta automaticamente o `render.yaml` — clique em **"Apply"**

- [ ] **Step 3: Aguardar o build e verificar os logs**

O Render irá:
1. Criar o banco `govmatch-db` (PostgreSQL)
2. Construir a imagem Docker (pode levar 5-10 minutos na primeira vez, pois instala Chromium e Tesseract)
3. Rodar `alembic upgrade head`
4. Subir o servidor com `uvicorn`

Acompanhe em **"Logs"** no painel. O deploy foi bem-sucedido quando aparecer:

```
INFO:     Application startup complete.
```

- [ ] **Step 4: Testar o health check**

Após o deploy, o Render exibe a URL pública (ex: `https://govmatch-api.onrender.com`). Teste:

```bash
curl https://govmatch-api.onrender.com/health
```

Esperado: `{"status":"ok"}`

- [ ] **Step 5: Testar a API**

```bash
curl https://govmatch-api.onrender.com/docs
```

A documentação Swagger deve carregar normalmente.

---

## Possíveis problemas e soluções

| Problema | Causa provável | Solução |
|---|---|---|
| Build falha em `playwright install` | Timeout no free tier | O Dockerfile já tem `|| true` — ignorar |
| `alembic upgrade head` falha | `DATABASE_URL` não injetada ainda | Verificar se o banco foi criado antes do web service nos logs |
| Container reinicia em loop | Health check falhando | Verificar se `/health` está acessível e retorna 200 |
| `OperationalError: asyncpg` | URL ainda no formato `postgresql://` | O `config.py` já converte — verificar se a variável foi injetada |
| Timeout no primeiro request | Chromium demorando para inicializar | Normal no free tier — o container "adormece" após 15 min de inatividade |
