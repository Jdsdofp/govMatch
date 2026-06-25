# Deploy da API govMatch no Render

**Data:** 2026-06-25  
**Escopo:** Configurar deploy da API FastAPI no Render usando Docker, PostgreSQL gerenciado e render.yaml.

---

## Contexto

A API govMatch é uma aplicação FastAPI (Python 3.13) com:
- Playwright/Chromium para scraping
- Tesseract OCR para extração de PDF
- SQLAlchemy async + Alembic para banco de dados
- Dockerfile já existente e funcional

O repositório já está no GitHub. O objetivo é subir a API no Render com banco PostgreSQL.

---

## Arquitetura no Render

Dois serviços criados via `render.yaml`:

1. **PostgreSQL** — banco gerenciado pelo Render (plano free: 1 GB)
2. **Web Service** — container Docker construído a partir do `Dockerfile`

O comando de start já definido no Dockerfile executa as migrations do Alembic antes de subir o servidor:
```
alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

## render.yaml

Arquivo declarativo na raiz do repositório que define ambos os serviços. O Render injeta automaticamente a `DATABASE_URL` do banco PostgreSQL no web service via `fromDatabase`.

O `config.py` já converte `postgresql://` → `postgresql+asyncpg://` automaticamente — nenhuma mudança de código necessária.

---

## Variáveis de ambiente

| Variável | Origem |
|---|---|
| `DATABASE_URL` | Injetada automaticamente via `fromDatabase` no render.yaml |
| `LOG_LEVEL` | Definida no render.yaml como `INFO` |
| `PLAYWRIGHT_BROWSERS_PATH` | Definida no render.yaml como `/usr/lib/chromium` |
| `PYTHONUNBUFFERED` | Definida no render.yaml como `1` |

---

## .gitignore

Verificar que os seguintes itens estão ignorados antes do deploy:
- `venv/`
- `.env`
- `govmatch.db`
- `tmp/`
- `cache/`

---

## O que não muda

- `Dockerfile` — já pronto e funcional
- `config.py` — já trata conversão da URL
- `requirements.txt` — já inclui `asyncpg` e `psycopg2-binary` para produção
- Migrations Alembic — rodam automaticamente no start

---

## Passos de implementação

1. Verificar/ajustar `.gitignore`
2. Criar `render.yaml` na raiz do projeto
3. Commitar e fazer push para o GitHub
4. No painel do Render: conectar o repositório GitHub e clicar em "Apply" no Blueprint (render.yaml)
5. Aguardar o build e verificar os logs
