# GovMatch API

API RESTful para busca e processamento de editais de licitação pública.

## Stack

- **Python 3.11+** / **FastAPI** — framework assíncrono
- **Playwright** — scraping de portais com JavaScript dinâmico
- **pdfplumber** — extração de texto de PDFs digitais
- **pytesseract / easyocr** — OCR para PDFs escaneados
- **SQLAlchemy 2 (async)** — ORM com suporte a SQLite (MVP) e PostgreSQL
- **Tenacity** — retry automático com backoff exponencial

## Estrutura

```
api/
├── main.py                   # Entrypoint FastAPI
├── config.py                 # Settings com pydantic-settings
├── requirements.txt
├── .env.example
├── database/
│   ├── engine.py             # Engine assíncrona + session factory
│   └── models.py             # Modelos SQLAlchemy (Edital, Alerta, SyncLog)
├── api/
│   ├── schemas.py            # Schemas Pydantic de request/response
│   └── routes/
│       └── editais.py        # Todos os endpoints de editais
├── scraper/
│   ├── browser.py            # GovMatchScraper (Playwright async)
│   └── ocr_processor.py      # Pipeline PDF → texto + Regex
└── services/
    └── edital_service.py     # Orquestra scraper, OCR e banco
```

## Setup

```bash
# 1. Ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Dependências
pip install -r requirements.txt

# 3. Playwright browsers
playwright install chromium

# 4. Tesseract OCR (opcional — para PDFs escaneados)
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
# Linux:   sudo apt install tesseract-ocr tesseract-ocr-por

# 5. Variáveis de ambiente
cp .env.example .env
# Edite .env conforme necessário

# 6. Rodar
uvicorn main:app --reload --port 8000
```

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/api/v1/editais/sync` | Dispara crawler em background |
| `GET` | `/api/v1/editais` | Lista editais com filtros |
| `GET` | `/api/v1/editais/{id}` | Detalhe de um edital |
| `POST` | `/api/v1/editais/{id}/alerta` | Ativa monitoramento |
| `DELETE` | `/api/v1/editais/{id}/alerta` | Desativa monitoramento |
| `GET` | `/health` | Health check |

### Query Parameters — GET /editais

| Param | Tipo | Descrição |
|-------|------|-----------|
| `q` | string | Palavras-chave (busca em objeto e órgão) |
| `estado` | string | UF (ex: `SP`, `MG`) |
| `exclusivo_me` | bool | Filtrar ME/EPP |
| `modalidade` | string | Ex: `Pregão Eletrônico` |
| `status` | enum | `publicado`, `aberto`, `disputa_aberta`, ... |
| `pagina` | int | Página (padrão: 1) |
| `por_pagina` | int | Itens por página (padrão: 20, máx: 100) |

### Documentação interativa

Após rodar: [http://localhost:8000/docs](http://localhost:8000/docs)

## Banco de Dados

### SQLite (MVP — padrão)
```
DATABASE_URL=sqlite+aiosqlite:///./govmatch.db
```

### PostgreSQL (produção)
```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/govmatch
```

As tabelas são criadas automaticamente no startup da API.
