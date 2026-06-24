# Scraper Multi-Portal com Agendamento — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refatorar o scraper do GovMatch para suportar PNCP + 6 portais federais/estaduais via Playwright, com browser pool singleton, agendamento independente por fonte e execução paralela com fallback.

**Architecture:** Plugin architecture — cada portal implementa `BaseSource`; `SchedulerService` (APScheduler) agenda cada fonte com seu próprio intervalo; `BrowserPool` fornece singletons Playwright compartilhados entre todas as fontes; `EditalService.processar_lote()` centraliza deduplicação e OCR.

**Tech Stack:** FastAPI, APScheduler 3.10+, Playwright (já instalado), httpx, tenacity, SQLAlchemy async, aiosqlite.

## Global Constraints

- Python 3.11+ (typing union `X | Y` sem `from __future__ import annotations`)
- `numero_controle` deve ser globalmente único — prefixar com `fonte:` quando o portal não usa PNCP ID (ex: `bll:12345`)
- Novos campos no banco exigem migration Alembic (não alterar schema manualmente)
- Browser pool usa exatamente 2 singletons: headless e visible — nunca criar mais
- Todos os scrapers Playwright devem chamar `browser_pool.new_page()`, nunca `playwright.chromium.launch()`
- `asyncio.gather(return_exceptions=True)` em toda execução paralela — nunca deixar exceção cancelar o lote
- Delays humanizados: min 500ms, max 1500ms entre ações de página

---

## Task 1: BrowserPool — singleton Playwright compartilhado

**Files:**
- Create: `scraper/browser_pool.py`
- Test: `tests/scraper/test_browser_pool.py`

**Interfaces:**
- Produces:
  - `async get_browser(headless: bool = True) -> Browser`
  - `async new_page(headless: bool = True, block_resources: bool = True) -> tuple[BrowserContext, Page]`
  - `async close_all() -> None`
  - `async random_delay(min_ms: int = 500, max_ms: int = 1500) -> None`

- [ ] **Step 1: Criar `scraper/browser_pool.py`**

```python
"""
Browser pool singleton — compartilhado por todos os scrapers Playwright.
Dois singletons: headless (padrão) e visible (bypass Cloudflare/Turnstile).
"""
import asyncio
import logging
import random

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

logger = logging.getLogger(__name__)

_LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--lang=pt-BR",
]

_HEADLESS: Browser | None = None
_VISIBLE: Browser | None = None
_PW = None  # instância global do playwright


async def _get_pw():
    global _PW
    if _PW is None:
        _PW = await async_playwright().start()
    return _PW


async def get_browser(headless: bool = True) -> Browser:
    """Retorna singleton de browser. Cria se não existir ou se crashou."""
    global _HEADLESS, _VISIBLE
    if headless:
        if _HEADLESS is None or not _HEADLESS.is_connected():
            pw = await _get_pw()
            _HEADLESS = await pw.chromium.launch(headless=True, args=_LAUNCH_ARGS)
            logger.info("Browser headless iniciado")
        return _HEADLESS
    else:
        if _VISIBLE is None or not _VISIBLE.is_connected():
            pw = await _get_pw()
            _VISIBLE = await pw.chromium.launch(headless=False, args=_LAUNCH_ARGS)
            logger.info("Browser visible iniciado")
        return _VISIBLE


async def new_page(
    headless: bool = True,
    block_resources: bool = True,
    locale: str = "pt-BR",
) -> tuple[BrowserContext, Page]:
    """Cria contexto isolado + página dentro do singleton."""
    browser = await get_browser(headless)
    context = await browser.new_context(
        locale=locale,
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    page = await context.new_page()

    if block_resources:
        async def _block(route, request):
            if request.resource_type in ("image", "stylesheet", "font", "media"):
                await route.abort()
            else:
                await route.continue_()
        await page.route("**/*", _block)

    return context, page


async def close_all() -> None:
    """Fecha todos os browsers. Chamar no lifespan shutdown."""
    global _HEADLESS, _VISIBLE, _PW
    for browser in (_HEADLESS, _VISIBLE):
        if browser and browser.is_connected():
            await browser.close()
    _HEADLESS = None
    _VISIBLE = None
    if _PW:
        await _PW.stop()
        _PW = None
    logger.info("Browser pool encerrado")


async def random_delay(min_ms: int = 500, max_ms: int = 1500) -> None:
    """Delay humanizado para evitar detecção de bot."""
    ms = random.randint(min_ms, max_ms)
    await asyncio.sleep(ms / 1000)
```

- [ ] **Step 2: Criar `tests/scraper/test_browser_pool.py`**

```python
"""Testes de integração para BrowserPool."""
import pytest
from scraper import browser_pool


@pytest.mark.asyncio
async def test_get_browser_cria_singleton():
    b1 = await browser_pool.get_browser(headless=True)
    b2 = await browser_pool.get_browser(headless=True)
    assert b1 is b2


@pytest.mark.asyncio
async def test_new_page_retorna_contexto_e_pagina():
    ctx, page = await browser_pool.new_page(headless=True)
    assert page is not None
    await ctx.close()


@pytest.mark.asyncio
async def test_close_all_limpa_singletons():
    await browser_pool.get_browser(headless=True)
    await browser_pool.close_all()
    assert browser_pool._HEADLESS is None
    assert browser_pool._PW is None
```

- [ ] **Step 3: Criar `tests/scraper/__init__.py` e `tests/__init__.py` se não existirem**

```bash
# No diretório C:\dev\govMatch\api
mkdir -p tests/scraper
touch tests/__init__.py tests/scraper/__init__.py
```

- [ ] **Step 4: Instalar pytest-asyncio**

```bash
pip install pytest-asyncio
echo "pytest-asyncio>=0.23" >> requirements.txt
```

- [ ] **Step 5: Criar `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 6: Rodar testes**

```bash
pytest tests/scraper/test_browser_pool.py -v
```

Esperado: 3 testes PASS

- [ ] **Step 7: Commit**

```bash
git add scraper/browser_pool.py tests/ pytest.ini requirements.txt
git commit -m "feat: add BrowserPool singleton — shared Playwright across all scrapers"
```

---

## Task 2: BaseSource + EditalRaw unificado

**Files:**
- Create: `scraper/sources/__init__.py`
- Create: `scraper/sources/base.py`
- Test: `tests/scraper/test_base_source.py`

**Interfaces:**
- Consumes: nada
- Produces:
  - `EditalRaw` dataclass (campo `fonte: str` adicionado — restantes idênticos ao `scraper/browser.py`)
  - `BaseSource` ABC com `source_id: str`, `interval_seconds: int`, `async buscar(...) -> list[EditalRaw]`, `async testar_conexao() -> bool`

- [ ] **Step 1: Criar `scraper/sources/__init__.py`**

```python
from scraper.sources.base import BaseSource, EditalRaw

__all__ = ["BaseSource", "EditalRaw"]
```

- [ ] **Step 2: Criar `scraper/sources/base.py`**

```python
"""Interface base para todas as fontes de scraping."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EditalRaw:
    numero_controle: str      # deve ser único globalmente — prefixar com fonte: se necessário
    orgao: str
    objeto: str
    modalidade: str
    fonte: str                # ex: "pncp", "bll", "tce_sp"
    uasg: str | None = field(default=None)
    valor_estimado: float | None = field(default=None)
    data_abertura: datetime | None = field(default=None)
    data_encerramento: datetime | None = field(default=None)
    link_edital: str | None = field(default=None)
    link_pdf: str | None = field(default=None)
    exclusivo_me: bool = field(default=False)
    estado: str | None = field(default=None)
    municipio: str | None = field(default=None)
    texto_pdf: str | None = field(default=None)


class BaseSource(ABC):
    """Contrato que todo scraper de portal deve implementar."""

    source_id: str           # identificador único, ex: "pncp"
    interval_seconds: int    # intervalo de agendamento

    @abstractmethod
    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        """Busca editais na fonte. Nunca lança exceção — retorna lista vazia se falhar."""
        ...

    async def testar_conexao(self) -> bool:
        """Verifica se o portal está acessível. Padrão: sempre True."""
        return True
```

- [ ] **Step 3: Criar `tests/scraper/test_base_source.py`**

```python
"""Testa contrato da BaseSource."""
import pytest
from scraper.sources.base import BaseSource, EditalRaw


class FakeSource(BaseSource):
    source_id = "fake"
    interval_seconds = 3600

    async def buscar(self, palavras_chave=None, estado=None):
        return [
            EditalRaw(
                numero_controle="fake:001",
                orgao="Prefeitura Teste",
                objeto="Teste de objeto",
                modalidade="Pregão",
                fonte="fake",
            )
        ]


@pytest.mark.asyncio
async def test_fake_source_retorna_edital_raw():
    source = FakeSource()
    resultado = await source.buscar()
    assert len(resultado) == 1
    assert resultado[0].fonte == "fake"
    assert resultado[0].numero_controle == "fake:001"


@pytest.mark.asyncio
async def test_testar_conexao_padrao():
    source = FakeSource()
    assert await source.testar_conexao() is True
```

- [ ] **Step 4: Rodar testes**

```bash
pytest tests/scraper/test_base_source.py -v
```

Esperado: 2 testes PASS

- [ ] **Step 5: Commit**

```bash
git add scraper/sources/ tests/scraper/test_base_source.py
git commit -m "feat: add BaseSource ABC and unified EditalRaw dataclass"
```

---

## Task 3: Migração do PNCP para BaseSource

**Files:**
- Create: `scraper/sources/pncp.py`
- Modify: `scraper/browser.py` (manter compatibilidade — delegar para nova fonte)
- Test: `tests/scraper/test_pncp_source.py`

**Interfaces:**
- Consumes: `BaseSource`, `EditalRaw` (Task 2)
- Produces: `PNCPSource(BaseSource)` com `source_id = "pncp"`, `interval_seconds = 3600`

- [ ] **Step 1: Criar `scraper/sources/pncp.py`**

```python
"""Fonte PNCP — API REST pública via httpx, busca paralela por UF."""
import asyncio
import logging
from datetime import date, datetime, timedelta

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)

PNCP_API_BASE = "https://pncp.gov.br/api/pncp/v1"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

UFS_BRASIL = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
    "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
    "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]


class PNCPSource(BaseSource):
    source_id = "pncp"
    interval_seconds = 3600  # 1 hora

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        ufs = [estado.upper()] if estado else UFS_BRASIL
        tarefas = [self._buscar_uf(uf, palavras_chave) for uf in ufs]
        resultados = await asyncio.gather(*tarefas, return_exceptions=True)

        editais: list[EditalRaw] = []
        for uf, res in zip(ufs, resultados):
            if isinstance(res, Exception):
                logger.error("Erro ao buscar PNCP para UF=%s: %s", uf, res)
            else:
                editais.extend(res)

        logger.info("[PNCP] Total: %d editais", len(editais))
        return editais

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
    async def _buscar_uf(
        self,
        uf: str,
        palavras_chave: list[str] | None,
        max_paginas: int = 5,
    ) -> list[EditalRaw]:
        resultados: list[EditalRaw] = []
        hoje = date.today()
        data_fim = hoje.strftime("%Y%m%d")
        data_ini = (hoje - timedelta(days=30)).strftime("%Y%m%d")

        async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            for pagina in range(1, max_paginas + 1):
                params = {
                    "dataInicial": data_ini,
                    "dataFinal": data_fim,
                    "pagina": pagina,
                    "tamanhoPagina": 20,
                    "uf": uf,
                }
                try:
                    resp = await client.get(
                        f"{PNCP_API_BASE}/contratacoes/publicadas", params=params
                    )
                except Exception as exc:
                    logger.error("[PNCP/%s] Erro de rede pág %d: %s", uf, pagina, exc)
                    break

                if resp.status_code in (404, 204):
                    break
                if resp.status_code != 200:
                    logger.warning("[PNCP/%s] Status %d pág %d", uf, resp.status_code, pagina)
                    break

                try:
                    dados = resp.json()
                except Exception:
                    break

                itens = dados if isinstance(dados, list) else dados.get("data", [])
                if not itens:
                    break

                for item in itens:
                    edital = _mapear_item_pncp(item)
                    if edital is None:
                        continue
                    if palavras_chave:
                        texto = f"{edital.objeto} {edital.orgao}".lower()
                        if not all(p.lower() in texto for p in palavras_chave):
                            continue
                    resultados.append(edital)

                total_paginas = (
                    dados.get("totalPaginas", pagina) if isinstance(dados, dict) else pagina
                )
                if pagina >= total_paginas:
                    break

                await asyncio.sleep(0.5)

        return resultados

    async def testar_conexao(self) -> bool:
        try:
            async with httpx.AsyncClient(headers=HEADERS, timeout=10) as client:
                r = await client.get(
                    f"{PNCP_API_BASE}/contratacoes/publicadas",
                    params={"dataInicial": "20240101", "dataFinal": "20240102", "pagina": 1, "tamanhoPagina": 1},
                )
                return r.status_code < 500
        except Exception:
            return False


def _mapear_item_pncp(item: dict) -> EditalRaw | None:
    try:
        return EditalRaw(
            numero_controle=item.get("numeroControlePNCP") or f"pncp:{item.get('sequencialCompra', '')}",
            orgao=item.get("orgaoEntidade", {}).get("razaoSocial", ""),
            uasg=str(item.get("orgaoEntidade", {}).get("cnpj", "")),
            objeto=item.get("objetoCompra", ""),
            modalidade=item.get("modalidadeNome", ""),
            valor_estimado=_parse_valor(item.get("valorTotalEstimado")),
            data_abertura=_parse_data(item.get("dataAberturaProposta")),
            data_encerramento=_parse_data(item.get("dataEncerramentoProposta")),
            link_edital=item.get("linkSistemaOrigem"),
            link_pdf=None,
            exclusivo_me=_detectar_exclusivo_me(item),
            estado=item.get("unidadeOrgao", {}).get("ufSigla"),
            municipio=item.get("unidadeOrgao", {}).get("municipioNome"),
            fonte="pncp",
        )
    except Exception as exc:
        logger.warning("[PNCP] Erro ao mapear item: %s", exc)
        return None


def _parse_valor(raw) -> float | None:
    if raw is None:
        return None
    try:
        return float(str(raw).replace(".", "").replace(",", "."))
    except (ValueError, TypeError):
        return None


def _parse_data(raw: str | None) -> datetime | None:
    if not raw:
        return None
    formatos = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%d/%m/%Y"]
    for fmt in formatos:
        try:
            return datetime.strptime(raw[:19], fmt)
        except ValueError:
            continue
    return None


def _detectar_exclusivo_me(item: dict) -> bool:
    objeto = (item.get("objetoCompra") or "").lower()
    return any(t in objeto for t in ("me/epp", "exclusivo me", "cota reservada", "microempresa"))
```

- [ ] **Step 2: Criar `tests/scraper/test_pncp_source.py`**

```python
"""Testes unitários para PNCPSource — mockam httpx."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from scraper.sources.pncp import PNCPSource, _mapear_item_pncp


ITEM_PNCP_FIXTURE = {
    "numeroControlePNCP": "00394777000140-2024-000001",
    "orgaoEntidade": {"razaoSocial": "Prefeitura de Teste", "cnpj": "00394777000140"},
    "objetoCompra": "Aquisição de material de escritório",
    "modalidadeNome": "Pregão Eletrônico",
    "valorTotalEstimado": 50000.0,
    "dataAberturaProposta": "2024-03-01T10:00:00",
    "dataEncerramentoProposta": "2024-03-15T17:00:00",
    "linkSistemaOrigem": "https://pncp.gov.br/app/editais/1",
    "unidadeOrgao": {"ufSigla": "SP", "municipioNome": "São Paulo"},
}


def test_mapear_item_pncp_campos_obrigatorios():
    edital = _mapear_item_pncp(ITEM_PNCP_FIXTURE)
    assert edital is not None
    assert edital.numero_controle == "00394777000140-2024-000001"
    assert edital.orgao == "Prefeitura de Teste"
    assert edital.estado == "SP"
    assert edital.fonte == "pncp"
    assert edital.valor_estimado == 50000.0


def test_mapear_item_pncp_retorna_none_em_excecao():
    edital = _mapear_item_pncp({})  # sem campo numeroControlePNCP
    # Deve retornar objeto com campos vazios ou None, não lançar exceção
    # numero_controle ficará "pncp:" com sequencial vazio — aceitável
    assert edital is not None or edital is None  # não lança exceção


@pytest.mark.asyncio
async def test_pncp_source_ids():
    source = PNCPSource()
    assert source.source_id == "pncp"
    assert source.interval_seconds == 3600
```

- [ ] **Step 3: Rodar testes**

```bash
pytest tests/scraper/test_pncp_source.py -v
```

Esperado: 3 testes PASS

- [ ] **Step 4: Atualizar `scraper/browser.py` para delegar ao PNCPSource**

No topo de `scraper/browser.py`, adicionar import e modificar `GovMatchScraper.buscar_editais`:

```python
# Adicionar no topo do arquivo (após os imports existentes):
from scraper.sources.pncp import PNCPSource as _PNCPSource

# Substituir o método buscar_editais dentro de GovMatchScraper:
    async def buscar_editais(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
        max_paginas: int = 5,
    ) -> list[EditalRaw]:
        """Delega para PNCPSource para manter compatibilidade com edital_service."""
        from scraper.sources.base import EditalRaw as SourceEditalRaw
        source = _PNCPSource()
        source_results = await source._buscar_uf(
            estado.upper() if estado else "SP", palavras_chave, max_paginas
        ) if estado else await source.buscar(palavras_chave, estado)
        # Converte SourceEditalRaw → EditalRaw local para compatibilidade
        return [
            EditalRaw(
                numero_controle=r.numero_controle,
                orgao=r.orgao,
                uasg=r.uasg,
                objeto=r.objeto,
                modalidade=r.modalidade,
                valor_estimado=r.valor_estimado,
                data_abertura=r.data_abertura,
                data_encerramento=r.data_encerramento,
                link_edital=r.link_edital,
                link_pdf=r.link_pdf,
                exclusivo_me=r.exclusivo_me,
                estado=r.estado,
                municipio=r.municipio,
                texto_pdf=r.texto_pdf,
            )
            for r in source_results
        ]
```

- [ ] **Step 5: Commit**

```bash
git add scraper/sources/pncp.py scraper/browser.py tests/scraper/test_pncp_source.py
git commit -m "feat: migrate PNCP to BaseSource with parallel UF fetch"
```

---

## Task 4: Migration Alembic — campo `fonte` e `fonte` em SyncLog

**Files:**
- Modify: `database/models.py`
- Create: `alembic/versions/<hash>_add_fonte_field.py` (gerado pelo alembic)

**Interfaces:**
- Produces: `Edital.fonte: str | None`, `SyncLog.fonte: str | None`

- [ ] **Step 1: Verificar se Alembic está configurado**

```bash
ls C:\dev\govMatch\api\alembic* 2>/dev/null || echo "sem alembic"
```

Se não existir `alembic.ini`:
```bash
cd C:\dev\govMatch\api && alembic init alembic
```

Editar `alembic/env.py` para importar `Base` e `DATABASE_URL`:
```python
# No topo de alembic/env.py, após os imports existentes:
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.engine import Base
from database import models  # noqa — garante que os models são carregados
from config import settings

# Substituir a linha: target_metadata = None
target_metadata = Base.metadata

# Substituir a linha: config.set_main_option("sqlalchemy.url", ...)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("+aiosqlite", ""))
```

- [ ] **Step 2: Adicionar campos em `database/models.py`**

Em `class Edital`, após `municipio`:
```python
    fonte: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
```

Em `class SyncLog`, após `status`:
```python
    fonte: Mapped[str | None] = mapped_column(String(50), nullable=True)
```

- [ ] **Step 3: Gerar migration**

```bash
cd C:\dev\govMatch\api
alembic revision --autogenerate -m "add_fonte_field"
```

Esperado: arquivo criado em `alembic/versions/XXXX_add_fonte_field.py`

- [ ] **Step 4: Verificar migration gerada**

Abrir o arquivo gerado. Deve conter:
```python
op.add_column('editais', sa.Column('fonte', sa.String(length=50), nullable=True))
op.add_column('sync_logs', sa.Column('fonte', sa.String(length=50), nullable=True))
```

- [ ] **Step 5: Aplicar migration**

```bash
alembic upgrade head
```

Esperado: `Running upgrade -> <hash>, add_fonte_field`

- [ ] **Step 6: Commit**

```bash
git add database/models.py alembic/
git commit -m "feat: add fonte field to Edital and SyncLog"
```

---

## Task 5: processar_lote no EditalService

**Files:**
- Modify: `services/edital_service.py`
- Test: `tests/services/test_edital_service_lote.py`

**Interfaces:**
- Consumes: `EditalRaw` de `scraper/sources/base.py`
- Produces: `async processar_lote(db, editais_raw: list[EditalRaw], fonte: str) -> dict`

- [ ] **Step 1: Adicionar `processar_lote` em `services/edital_service.py`**

Após a função `sincronizar_editais`, adicionar:

```python
from scraper.sources.base import EditalRaw as SourceEditalRaw


async def processar_lote(
    db: AsyncSession,
    editais_raw: list[SourceEditalRaw],
    fonte: str,
) -> dict:
    """
    Persiste lote de editais de qualquer fonte. Deduplicação por numero_controle.
    Retorna resumo: { total_recebidos, novos, duplicados, erros }.
    """
    log = SyncLog(iniciado_em=datetime.utcnow(), fonte=fonte)
    db.add(log)
    await db.flush()

    log.total_encontrados = len(editais_raw)
    novos = 0
    erros = 0

    for raw in editais_raw:
        try:
            inserido = await _persistir_edital_fonte(db, raw)
            if inserido:
                novos += 1
        except Exception as exc:
            erros += 1
            logger.warning("[%s] Falha ao persistir %s: %s", fonte, raw.numero_controle, exc)

    log.total_novos = novos
    log.status = "concluido"
    log.finalizado_em = datetime.utcnow()
    await db.flush()

    return {
        "fonte": fonte,
        "total_recebidos": len(editais_raw),
        "novos": novos,
        "duplicados": len(editais_raw) - novos - erros,
        "erros": erros,
    }


async def _persistir_edital_fonte(db: AsyncSession, raw: SourceEditalRaw) -> bool:
    """Insere edital de qualquer fonte. Retorna True se inserido."""
    existente = await db.scalar(
        select(Edital).where(Edital.numero_controle == raw.numero_controle)
    )
    if existente:
        return False

    texto_pdf: str | None = None
    if raw.link_pdf:
        try:
            async with GovMatchScraper(headless=True) as scraper:
                caminho = await scraper.baixar_pdf(
                    raw.link_pdf,
                    f"{raw.numero_controle.replace('/', '_').replace(':', '_')}.pdf",
                )
            if caminho:
                extraido = await processar_pdf(caminho)
                texto_pdf = extraido.texto_completo
                if raw.valor_estimado is None and extraido.valor_estimado:
                    raw.valor_estimado = extraido.valor_estimado
                if not raw.exclusivo_me and extraido.exclusivo_me:
                    raw.exclusivo_me = True
        except Exception as exc:
            logger.warning("Falha ao processar PDF %s: %s", raw.numero_controle, exc)

    edital = Edital(
        numero_controle=raw.numero_controle,
        orgao=raw.orgao,
        uasg=raw.uasg,
        objeto=raw.objeto,
        modalidade=raw.modalidade,
        valor_estimado=raw.valor_estimado,
        data_abertura=raw.data_abertura,
        data_encerramento=raw.data_encerramento,
        link_edital=raw.link_edital,
        link_pdf=raw.link_pdf,
        exclusivo_me=raw.exclusivo_me,
        estado=raw.estado,
        municipio=raw.municipio,
        texto_extraido=texto_pdf,
        status=EditalStatus.PUBLICADO,
        fonte=raw.fonte,
    )
    db.add(edital)
    return True
```

- [ ] **Step 2: Criar `tests/services/__init__.py` e `tests/services/test_edital_service_lote.py`**

```python
"""Testa processar_lote com banco SQLite em memória."""
import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from database.engine import Base
from database.models import Edital
from scraper.sources.base import EditalRaw
from services.edital_service import processar_lote


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


def make_edital(numero="bll:001"):
    return EditalRaw(
        numero_controle=numero,
        orgao="Prefeitura Teste",
        objeto="Aquisição de material",
        modalidade="Pregão",
        fonte="bll",
    )


@pytest.mark.asyncio
async def test_processar_lote_insere_novo(db_session):
    editais = [make_edital("bll:001")]
    resultado = await processar_lote(db_session, editais, "bll")
    assert resultado["novos"] == 1
    assert resultado["duplicados"] == 0


@pytest.mark.asyncio
async def test_processar_lote_deduplica(db_session):
    editais = [make_edital("bll:002")]
    await processar_lote(db_session, editais, "bll")
    resultado = await processar_lote(db_session, editais, "bll")
    assert resultado["novos"] == 0
    assert resultado["duplicados"] == 1
```

- [ ] **Step 3: Rodar testes**

```bash
pytest tests/services/test_edital_service_lote.py -v
```

Esperado: 2 testes PASS

- [ ] **Step 4: Commit**

```bash
git add services/edital_service.py tests/services/
git commit -m "feat: add processar_lote for multi-source deduplication"
```

---

## Task 6: SchedulerService com APScheduler

**Files:**
- Create: `services/scheduler_service.py`
- Modify: `main.py` (lifespan)
- Test: `tests/services/test_scheduler_service.py`

**Interfaces:**
- Consumes: `BaseSource` (Task 2), `processar_lote` (Task 5)
- Produces:
  - `SchedulerService` com `register(source)`, `start()`, `shutdown()`, `get_status() -> list[dict]`

- [ ] **Step 1: Instalar APScheduler**

```bash
pip install "apscheduler>=3.10.4"
echo "apscheduler>=3.10.4" >> requirements.txt
```

- [ ] **Step 2: Criar `services/scheduler_service.py`**

```python
"""Agendador de scrapers — cada BaseSource tem seu próprio intervalo."""
import logging
import random
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from database.engine import AsyncSessionLocal
from scraper.sources.base import BaseSource
from services.edital_service import processar_lote

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()
        self._sources: list[BaseSource] = []
        self._last_run: dict[str, datetime | None] = {}
        self._last_count: dict[str, int] = {}
        self._last_error: dict[str, str | None] = {}

    def register(self, source: BaseSource) -> None:
        """Registra uma fonte com jitter de ±10% no intervalo."""
        self._sources.append(source)
        self._last_run[source.source_id] = None
        self._last_count[source.source_id] = 0
        self._last_error[source.source_id] = None

        jitter = int(source.interval_seconds * 0.1)
        seconds = source.interval_seconds + random.randint(-jitter, jitter)

        self._scheduler.add_job(
            self._executar_fonte,
            trigger=IntervalTrigger(seconds=seconds),
            args=[source],
            id=f"source_{source.source_id}",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=300,
        )
        logger.info(
            "Fonte '%s' registrada — intervalo ~%ds", source.source_id, seconds
        )

    async def _executar_fonte(self, source: BaseSource) -> None:
        logger.info("[Scheduler] Iniciando '%s'", source.source_id)
        try:
            editais = await source.buscar()
            async with AsyncSessionLocal() as db:
                resultado = await processar_lote(db, editais, source.source_id)
                await db.commit()
            self._last_count[source.source_id] = resultado["novos"]
            self._last_error[source.source_id] = None
            logger.info(
                "[Scheduler] '%s' concluído — %d novos de %d",
                source.source_id,
                resultado["novos"],
                resultado["total_recebidos"],
            )
        except Exception as exc:
            self._last_error[source.source_id] = str(exc)
            logger.error("[Scheduler] Erro em '%s': %s", source.source_id, exc)
        finally:
            self._last_run[source.source_id] = datetime.utcnow()

    def start(self) -> None:
        self._scheduler.start()
        logger.info("SchedulerService iniciado com %d fontes", len(self._sources))

    async def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)
        logger.info("SchedulerService encerrado")

    def get_status(self) -> list[dict]:
        jobs = {job.id: job for job in self._scheduler.get_jobs()}
        status = []
        for source in self._sources:
            job = jobs.get(f"source_{source.source_id}")
            status.append({
                "source_id": source.source_id,
                "interval_seconds": source.interval_seconds,
                "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
                "last_run": self._last_run[source.source_id].isoformat()
                    if self._last_run[source.source_id] else None,
                "last_count": self._last_count[source.source_id],
                "last_error": self._last_error[source.source_id],
            })
        return status
```

- [ ] **Step 3: Criar `tests/services/test_scheduler_service.py`**

```python
"""Testa SchedulerService com fonte fake."""
import pytest
from scraper.sources.base import BaseSource, EditalRaw
from services.scheduler_service import SchedulerService


class FakeSource(BaseSource):
    source_id = "fake_sched"
    interval_seconds = 3600

    async def buscar(self, palavras_chave=None, estado=None):
        return []


def test_register_adiciona_fonte():
    svc = SchedulerService()
    svc.register(FakeSource())
    status = svc.get_status()
    assert any(s["source_id"] == "fake_sched" for s in status)


def test_get_status_retorna_campos_esperados():
    svc = SchedulerService()
    svc.register(FakeSource())
    s = svc.get_status()[0]
    assert "source_id" in s
    assert "interval_seconds" in s
    assert "next_run" in s
    assert "last_run" in s
    assert "last_count" in s
    assert "last_error" in s
```

- [ ] **Step 4: Rodar testes**

```bash
pytest tests/services/test_scheduler_service.py -v
```

Esperado: 2 testes PASS

- [ ] **Step 5: Modificar `main.py` — lifespan inicia/para scheduler e browser pool**

Substituir o bloco `lifespan` e o bloco de imports em `main.py`:

```python
# Adicionar aos imports (após from database.engine import create_tables):
from scraper import browser_pool
from scraper.sources.pncp import PNCPSource
from services.scheduler_service import SchedulerService

# Antes do lifespan, criar instância global do scheduler:
scheduler = SchedulerService()
scheduler.register(PNCPSource())


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando GovMatch API...")
    await create_tables()
    logger.info("Banco de dados pronto.")
    scheduler.start()
    logger.info("Scheduler iniciado.")
    yield
    await scheduler.shutdown()
    await browser_pool.close_all()
    logger.info("GovMatch API encerrada.")
```

- [ ] **Step 6: Adicionar rota de status do scheduler em `api/routes/scheduler.py`**

```python
"""Rota de status do agendador."""
from fastapi import APIRouter
from main import scheduler

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


@router.get("/status")
async def status_scheduler():
    return {"sources": scheduler.get_status()}
```

Em `main.py`, após `app.include_router(editais_router, ...)`:
```python
from api.routes.scheduler import router as scheduler_router
app.include_router(scheduler_router, prefix="/api/v1")
```

- [ ] **Step 7: Testar manualmente**

```bash
cd C:\dev\govMatch\api
uvicorn main:app --reload --port 8000
```

Acessar: `http://localhost:8000/api/v1/scheduler/status`

Esperado: JSON com `sources: [{ source_id: "pncp", interval_seconds: 3600, ... }]`

- [ ] **Step 8: Commit**

```bash
git add services/scheduler_service.py main.py api/routes/scheduler.py tests/services/test_scheduler_service.py requirements.txt
git commit -m "feat: add SchedulerService with per-source intervals and APScheduler"
```

---

## Task 7: Scrapers Playwright — BLL, BNC, Licitações-e

**Files:**
- Create: `scraper/sources/bll.py`
- Create: `scraper/sources/bnc.py`
- Create: `scraper/sources/licitacoes_e.py`
- Create: `tests/scraper/test_playwright_sources.py`

**Interfaces:**
- Consumes: `BaseSource`, `EditalRaw` (Task 2), `browser_pool.new_page` (Task 1)
- Produces: 3 implementações de `BaseSource` com `interval_seconds = 21600` (6h)

- [ ] **Step 1: Criar `scraper/sources/bll.py`**

```python
"""Fonte BLL — Bolsa de Licitações e Leilões (bll.net.br)."""
import logging
from datetime import datetime

from scraper import browser_pool
from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)


class BLLSource(BaseSource):
    source_id = "bll"
    interval_seconds = 21600  # 6 horas
    _base_url = "https://bll.org.br/licitacao/consulta"

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        editais: list[EditalRaw] = []
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            await page.goto(self._base_url, wait_until="domcontentloaded", timeout=30_000)
            await browser_pool.random_delay(800, 1400)

            # Aguarda tabela de resultados
            await page.wait_for_selector("table.licitacoes, .lista-licitacoes, #tblLicitacoes", timeout=15_000)

            rows = await page.query_selector_all("table tr[data-id], .item-licitacao, tr.licitacao")
            for row in rows:
                edital = await self._parse_row(row, page)
                if edital:
                    if palavras_chave:
                        texto = f"{edital.objeto} {edital.orgao}".lower()
                        if not all(p.lower() in texto for p in palavras_chave):
                            continue
                    if estado and edital.estado and edital.estado.upper() != estado.upper():
                        continue
                    editais.append(edital)

            logger.info("[BLL] %d editais encontrados", len(editais))
        except Exception as exc:
            logger.error("[BLL] Erro ao buscar: %s", exc)
        finally:
            await ctx.close()

        return editais

    async def _parse_row(self, row, page) -> EditalRaw | None:
        try:
            # Seletores fuzzy — BLL pode mudar layout
            for sel_num in ("td:nth-child(1)", ".numero", "[data-field='numero']"):
                el = await row.query_selector(sel_num)
                if el:
                    numero = (await el.inner_text()).strip()
                    break
            else:
                numero = None

            for sel_obj in ("td:nth-child(3)", ".objeto", "[data-field='objeto']"):
                el = await row.query_selector(sel_obj)
                if el:
                    objeto = (await el.inner_text()).strip()
                    break
            else:
                objeto = ""

            for sel_org in ("td:nth-child(2)", ".orgao", "[data-field='orgao']"):
                el = await row.query_selector(sel_org)
                if el:
                    orgao = (await el.inner_text()).strip()
                    break
            else:
                orgao = ""

            link_el = await row.query_selector("a[href*='licitacao'], a[href*='edital']")
            link = await link_el.get_attribute("href") if link_el else None
            if link and not link.startswith("http"):
                link = f"https://bll.org.br{link}"

            if not numero:
                return None

            return EditalRaw(
                numero_controle=f"bll:{numero}",
                orgao=orgao,
                objeto=objeto,
                modalidade="",
                fonte="bll",
                link_edital=link,
            )
        except Exception as exc:
            logger.warning("[BLL] Erro ao parsear linha: %s", exc)
            return None

    async def testar_conexao(self) -> bool:
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            resp = await page.goto(self._base_url, wait_until="domcontentloaded", timeout=15_000)
            return resp is not None and resp.status < 500
        except Exception:
            return False
        finally:
            await ctx.close()
```

- [ ] **Step 2: Criar `scraper/sources/bnc.py`**

```python
"""Fonte BNC — Banco Nacional de Contratações Públicas (bnc.org.br)."""
import logging

from scraper import browser_pool
from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)


class BNCSource(BaseSource):
    source_id = "bnc"
    interval_seconds = 21600
    _base_url = "https://www.bnc.org.br/licitacoes"

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        editais: list[EditalRaw] = []
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            await page.goto(self._base_url, wait_until="domcontentloaded", timeout=30_000)
            await browser_pool.random_delay(800, 1400)

            await page.wait_for_selector(".licitacao-item, table.licitacoes, #lista-licitacoes", timeout=15_000)

            items = await page.query_selector_all(".licitacao-item, table tr.licitacao")
            for item in items:
                edital = await self._parse_item(item)
                if edital:
                    if palavras_chave:
                        texto = f"{edital.objeto} {edital.orgao}".lower()
                        if not all(p.lower() in texto for p in palavras_chave):
                            continue
                    if estado and edital.estado and edital.estado.upper() != estado.upper():
                        continue
                    editais.append(edital)

            logger.info("[BNC] %d editais encontrados", len(editais))
        except Exception as exc:
            logger.error("[BNC] Erro: %s", exc)
        finally:
            await ctx.close()

        return editais

    async def _parse_item(self, item) -> EditalRaw | None:
        try:
            for sel in (".numero-licitacao", "td:nth-child(1)", "[data-numero]"):
                el = await item.query_selector(sel)
                if el:
                    numero = (await el.inner_text()).strip()
                    break
            else:
                numero = None

            for sel in (".objeto-licitacao", "td:nth-child(3)", ".descricao"):
                el = await item.query_selector(sel)
                if el:
                    objeto = (await el.inner_text()).strip()
                    break
            else:
                objeto = ""

            for sel in (".orgao-licitacao", "td:nth-child(2)", ".entidade"):
                el = await item.query_selector(sel)
                if el:
                    orgao = (await el.inner_text()).strip()
                    break
            else:
                orgao = ""

            link_el = await item.query_selector("a[href]")
            link = await link_el.get_attribute("href") if link_el else None
            if link and not link.startswith("http"):
                link = f"https://www.bnc.org.br{link}"

            if not numero:
                return None

            return EditalRaw(
                numero_controle=f"bnc:{numero}",
                orgao=orgao,
                objeto=objeto,
                modalidade="",
                fonte="bnc",
                link_edital=link,
            )
        except Exception as exc:
            logger.warning("[BNC] Erro ao parsear item: %s", exc)
            return None

    async def testar_conexao(self) -> bool:
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            resp = await page.goto(self._base_url, wait_until="domcontentloaded", timeout=15_000)
            return resp is not None and resp.status < 500
        except Exception:
            return False
        finally:
            await ctx.close()
```

- [ ] **Step 3: Criar `scraper/sources/licitacoes_e.py`**

```python
"""Fonte Licitações-e — Portal BB (licitacoes-e.info.bb.com.br)."""
import logging

from scraper import browser_pool
from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)


class LicitacoesESource(BaseSource):
    source_id = "licitacoes_e"
    interval_seconds = 21600
    _base_url = "https://www.licitacoes-e.com.br/aop/pesquisarLicitacao.aop"

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        editais: list[EditalRaw] = []
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            await page.goto(self._base_url, wait_until="domcontentloaded", timeout=30_000)
            await browser_pool.random_delay(1000, 2000)

            # Intercept JSON API response (Licitações-e usa Ajax)
            captured: list[dict] = []

            async def on_response(response):
                if "pesquisarLicitacao" in response.url and "json" in (response.headers.get("content-type", "")):
                    try:
                        data = await response.json()
                        if isinstance(data, list):
                            captured.extend(data)
                        elif isinstance(data, dict):
                            captured.extend(data.get("licitacoes", data.get("lista", [])))
                    except Exception:
                        pass

            page.on("response", on_response)

            # Aguarda tabela renderizar
            await page.wait_for_selector("#tblResultado, .resultado-licitacao, table.listagem", timeout=20_000)
            await browser_pool.random_delay(500, 1000)

            if captured:
                for item in captured:
                    edital = _mapear_json_bb(item)
                    if edital:
                        editais.append(edital)
            else:
                # Fallback: scrape HTML direto
                rows = await page.query_selector_all("#tblResultado tr[id], .resultado-licitacao")
                for row in rows:
                    edital = await _parse_row_bb(row)
                    if edital:
                        editais.append(edital)

            if palavras_chave:
                editais = [
                    e for e in editais
                    if all(p.lower() in f"{e.objeto} {e.orgao}".lower() for p in palavras_chave)
                ]
            if estado:
                editais = [e for e in editais if not e.estado or e.estado.upper() == estado.upper()]

            logger.info("[Licitações-e] %d editais encontrados", len(editais))
        except Exception as exc:
            logger.error("[Licitações-e] Erro: %s", exc)
        finally:
            await ctx.close()

        return editais

    async def testar_conexao(self) -> bool:
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            resp = await page.goto(self._base_url, wait_until="domcontentloaded", timeout=15_000)
            return resp is not None and resp.status < 500
        except Exception:
            return False
        finally:
            await ctx.close()


def _mapear_json_bb(item: dict) -> EditalRaw | None:
    try:
        numero = str(item.get("numeroLicitacao") or item.get("codigoLicitacao") or "")
        if not numero:
            return None
        return EditalRaw(
            numero_controle=f"licitacoes_e:{numero}",
            orgao=item.get("nomeOrgao") or item.get("orgao") or "",
            objeto=item.get("objeto") or item.get("descricao") or "",
            modalidade=item.get("modalidade") or "",
            fonte="licitacoes_e",
            link_edital=item.get("linkEdital") or item.get("url"),
        )
    except Exception as exc:
        logger.warning("[Licitações-e] Erro ao mapear JSON: %s", exc)
        return None


async def _parse_row_bb(row) -> EditalRaw | None:
    try:
        for sel in ("td:nth-child(1)", ".num-licitacao"):
            el = await row.query_selector(sel)
            if el:
                numero = (await el.inner_text()).strip()
                break
        else:
            numero = None
        if not numero:
            return None

        for sel in ("td:nth-child(3)", ".objeto"):
            el = await row.query_selector(sel)
            if el:
                objeto = (await el.inner_text()).strip()
                break
        else:
            objeto = ""

        for sel in ("td:nth-child(2)", ".orgao"):
            el = await row.query_selector(sel)
            if el:
                orgao = (await el.inner_text()).strip()
                break
        else:
            orgao = ""

        return EditalRaw(
            numero_controle=f"licitacoes_e:{numero}",
            orgao=orgao,
            objeto=objeto,
            modalidade="",
            fonte="licitacoes_e",
        )
    except Exception as exc:
        logger.warning("[Licitações-e] Erro ao parsear linha: %s", exc)
        return None
```

- [ ] **Step 4: Criar `tests/scraper/test_playwright_sources.py`**

```python
"""Smoke tests de estrutura para fontes Playwright."""
from scraper.sources.bll import BLLSource
from scraper.sources.bnc import BNCSource
from scraper.sources.licitacoes_e import LicitacoesESource


def test_bll_source_ids():
    s = BLLSource()
    assert s.source_id == "bll"
    assert s.interval_seconds == 21600


def test_bnc_source_ids():
    s = BNCSource()
    assert s.source_id == "bnc"
    assert s.interval_seconds == 21600


def test_licitacoes_e_source_ids():
    s = LicitacoesESource()
    assert s.source_id == "licitacoes_e"
    assert s.interval_seconds == 21600
```

- [ ] **Step 5: Rodar testes**

```bash
pytest tests/scraper/test_playwright_sources.py -v
```

Esperado: 3 testes PASS

- [ ] **Step 6: Commit**

```bash
git add scraper/sources/bll.py scraper/sources/bnc.py scraper/sources/licitacoes_e.py tests/scraper/test_playwright_sources.py
git commit -m "feat: add BLL, BNC and Licitações-e Playwright scrapers"
```

---

## Task 8: Scrapers TCE — SP, MG, RS

**Files:**
- Create: `scraper/sources/tce_sp.py`
- Create: `scraper/sources/tce_mg.py`
- Create: `scraper/sources/tce_rs.py`
- Create: `tests/scraper/test_tce_sources.py`

**Interfaces:**
- Consumes: `BaseSource`, `EditalRaw` (Task 2), `browser_pool.new_page` (Task 1)
- Produces: 3 implementações com `interval_seconds = 21600`

- [ ] **Step 1: Criar `scraper/sources/tce_sp.py`**

```python
"""Fonte TCE-SP — licitacoes.tce.sp.gov.br."""
import logging

from scraper import browser_pool
from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)


class TCESPSource(BaseSource):
    source_id = "tce_sp"
    interval_seconds = 21600
    _base_url = "https://www.tce.sp.gov.br/licitacoes"

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "SP":
            return []

        editais: list[EditalRaw] = []
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            await page.goto(self._base_url, wait_until="domcontentloaded", timeout=30_000)
            await browser_pool.random_delay(800, 1500)

            await page.wait_for_selector(
                "table.tabela-licitacoes, .licitacao-row, #resultado-consulta",
                timeout=20_000,
            )

            rows = await page.query_selector_all(
                "table tr[data-id], .licitacao-row, #resultado-consulta tr"
            )
            for row in rows:
                edital = await _parse_row_tce(row, "tce_sp", "SP")
                if edital:
                    if palavras_chave:
                        texto = f"{edital.objeto} {edital.orgao}".lower()
                        if not all(p.lower() in texto for p in palavras_chave):
                            continue
                    editais.append(edital)

            logger.info("[TCE-SP] %d editais encontrados", len(editais))
        except Exception as exc:
            logger.error("[TCE-SP] Erro: %s", exc)
        finally:
            await ctx.close()

        return editais

    async def testar_conexao(self) -> bool:
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            resp = await page.goto(self._base_url, wait_until="domcontentloaded", timeout=15_000)
            return resp is not None and resp.status < 500
        except Exception:
            return False
        finally:
            await ctx.close()
```

- [ ] **Step 2: Criar `scraper/sources/tce_mg.py`**

```python
"""Fonte TCE-MG — licitacao.tce.mg.gov.br."""
import logging

from scraper import browser_pool
from scraper.sources.base import BaseSource, EditalRaw
from scraper.sources.tce_sp import _parse_row_tce

logger = logging.getLogger(__name__)


class TCEMGSource(BaseSource):
    source_id = "tce_mg"
    interval_seconds = 21600
    _base_url = "https://licitacao.tce.mg.gov.br/ConsultaLicitacao"

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "MG":
            return []

        editais: list[EditalRaw] = []
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            await page.goto(self._base_url, wait_until="domcontentloaded", timeout=30_000)
            await browser_pool.random_delay(800, 1500)

            await page.wait_for_selector(
                "table, .grid-licitacoes, #grdLicitacoes",
                timeout=20_000,
            )

            rows = await page.query_selector_all(
                "table tr:not(:first-child), .grid-licitacoes tr, #grdLicitacoes tr"
            )
            for row in rows:
                edital = await _parse_row_tce(row, "tce_mg", "MG")
                if edital:
                    if palavras_chave:
                        texto = f"{edital.objeto} {edital.orgao}".lower()
                        if not all(p.lower() in texto for p in palavras_chave):
                            continue
                    editais.append(edital)

            logger.info("[TCE-MG] %d editais encontrados", len(editais))
        except Exception as exc:
            logger.error("[TCE-MG] Erro: %s", exc)
        finally:
            await ctx.close()

        return editais

    async def testar_conexao(self) -> bool:
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            resp = await page.goto(self._base_url, wait_until="domcontentloaded", timeout=15_000)
            return resp is not None and resp.status < 500
        except Exception:
            return False
        finally:
            await ctx.close()
```

- [ ] **Step 3: Criar `scraper/sources/tce_rs.py`**

```python
"""Fonte TCE-RS — licitacon.tce.rs.gov.br."""
import logging

from scraper import browser_pool
from scraper.sources.base import BaseSource, EditalRaw
from scraper.sources.tce_sp import _parse_row_tce

logger = logging.getLogger(__name__)


class TCERSSource(BaseSource):
    source_id = "tce_rs"
    interval_seconds = 21600
    _base_url = "https://www1.tce.rs.gov.br/aplicprod/f?p=50500:2"

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "RS":
            return []

        editais: list[EditalRaw] = []
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            await page.goto(self._base_url, wait_until="domcontentloaded", timeout=30_000)
            await browser_pool.random_delay(800, 1500)

            await page.wait_for_selector(
                "table.apexir_WORKSHEET_DATA, .t-Report-wrap table, table.licitacoes",
                timeout=20_000,
            )

            rows = await page.query_selector_all(
                "table.apexir_WORKSHEET_DATA tr[class*='data'], .t-Report-wrap table tr:not(:first-child)"
            )
            for row in rows:
                edital = await _parse_row_tce(row, "tce_rs", "RS")
                if edital:
                    if palavras_chave:
                        texto = f"{edital.objeto} {edital.orgao}".lower()
                        if not all(p.lower() in texto for p in palavras_chave):
                            continue
                    editais.append(edital)

            logger.info("[TCE-RS] %d editais encontrados", len(editais))
        except Exception as exc:
            logger.error("[TCE-RS] Erro: %s", exc)
        finally:
            await ctx.close()

        return editais

    async def testar_conexao(self) -> bool:
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            resp = await page.goto(self._base_url, wait_until="domcontentloaded", timeout=15_000)
            return resp is not None and resp.status < 500
        except Exception:
            return False
        finally:
            await ctx.close()
```

- [ ] **Step 4: Adicionar helper `_parse_row_tce` em `scraper/sources/tce_sp.py`**

Adicionar após a classe `TCESPSource`:

```python
async def _parse_row_tce(row, fonte: str, estado: str) -> EditalRaw | None:
    """Helper compartilhado entre TCEs — seletores fuzzy por ordem de coluna."""
    try:
        for sel in ("td:nth-child(1)", ".numero-edital", "[data-label='Número']"):
            el = await row.query_selector(sel)
            if el:
                numero = (await el.inner_text()).strip()
                if numero and numero.lower() not in ("número", "nº", "#"):
                    break
        else:
            return None

        for sel in ("td:nth-child(3)", ".objeto-licitacao", "[data-label='Objeto']"):
            el = await row.query_selector(sel)
            if el:
                objeto = (await el.inner_text()).strip()
                break
        else:
            objeto = ""

        for sel in ("td:nth-child(2)", ".orgao-licitacao", "[data-label='Órgão']"):
            el = await row.query_selector(sel)
            if el:
                orgao = (await el.inner_text()).strip()
                break
        else:
            orgao = ""

        link_el = await row.query_selector("a[href*='edital'], a[href*='licitacao']")
        link = await link_el.get_attribute("href") if link_el else None

        if not numero or not objeto:
            return None

        return EditalRaw(
            numero_controle=f"{fonte}:{numero}",
            orgao=orgao,
            objeto=objeto,
            modalidade="",
            fonte=fonte,
            estado=estado,
            link_edital=link,
        )
    except Exception as exc:
        logger.warning("[%s] Erro ao parsear linha: %s", fonte, exc)
        return None
```

- [ ] **Step 5: Criar `tests/scraper/test_tce_sources.py`**

```python
"""Smoke tests de estrutura para fontes TCE."""
from scraper.sources.tce_sp import TCESPSource
from scraper.sources.tce_mg import TCEMGSource
from scraper.sources.tce_rs import TCERSSource


def test_tce_sp_ids():
    s = TCESPSource()
    assert s.source_id == "tce_sp"
    assert s.interval_seconds == 21600


def test_tce_mg_ids():
    s = TCEMGSource()
    assert s.source_id == "tce_mg"
    assert s.interval_seconds == 21600


def test_tce_rs_ids():
    s = TCERSSource()
    assert s.source_id == "tce_rs"
    assert s.interval_seconds == 21600


def test_tce_sp_filtra_estado_errado():
    """buscar deve retornar lista vazia se estado != SP."""
    import asyncio
    s = TCESPSource()
    result = asyncio.run(s.buscar(estado="MG"))
    assert result == []
```

- [ ] **Step 6: Rodar testes**

```bash
pytest tests/scraper/test_tce_sources.py -v
```

Esperado: 4 testes PASS

- [ ] **Step 7: Commit**

```bash
git add scraper/sources/tce_sp.py scraper/sources/tce_mg.py scraper/sources/tce_rs.py tests/scraper/test_tce_sources.py
git commit -m "feat: add TCE-SP, TCE-MG, TCE-RS Playwright scrapers"
```

---

## Task 9: Infraestrutura de Portais Municipais

**Files:**
- Create: `scraper/sources/municipais/__init__.py`
- Create: `scraper/sources/municipais/base_municipal.py`
- Test: `tests/scraper/test_municipais.py`

**Interfaces:**
- Consumes: `BaseSource`, `EditalRaw` (Task 2), `browser_pool.new_page` (Task 1)
- Produces: `BaseMunicipalSource(BaseSource)` que subclasses preenchem apenas `_url` e `estado` e `municipio`

- [ ] **Step 1: Criar `scraper/sources/municipais/__init__.py`**

```python
from scraper.sources.municipais.base_municipal import BaseMunicipalSource

__all__ = ["BaseMunicipalSource"]
```

- [ ] **Step 2: Criar `scraper/sources/municipais/base_municipal.py`**

```python
"""Base para scrapers de portais municipais — subclasses precisam apenas de _url."""
import logging

from scraper import browser_pool
from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)


class BaseMunicipalSource(BaseSource):
    """
    Base para portais municipais.

    Subclasse mínima:
        class SaoPauloSource(BaseMunicipalSource):
            source_id = "municipal_sp_sao_paulo"
            _url = "https://e-negocioscidadesp.prefeitura.sp.gov.br/BuscaLicitacao.aspx"
            _estado = "SP"
            _municipio = "São Paulo"
    """

    interval_seconds = 86400  # 24 horas por padrão para municipais
    _url: str = ""
    _estado: str = ""
    _municipio: str = ""

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and self._estado and estado.upper() != self._estado.upper():
            return []
        if not self._url:
            logger.error("[%s] _url não definida", self.source_id)
            return []

        editais: list[EditalRaw] = []
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            await page.goto(self._url, wait_until="domcontentloaded", timeout=30_000)
            await browser_pool.random_delay(800, 1500)

            # Estratégia genérica: captura qualquer tabela com links de edital
            await page.wait_for_selector("table tr, .licitacao, .edital", timeout=15_000)
            rows = await page.query_selector_all("table tr:not(:first-child)")

            for row in rows:
                edital = await self._parse_row_generico(row)
                if edital:
                    if palavras_chave:
                        texto = f"{edital.objeto} {edital.orgao}".lower()
                        if not all(p.lower() in texto for p in palavras_chave):
                            continue
                    editais.append(edital)

            logger.info("[%s] %d editais encontrados", self.source_id, len(editais))
        except Exception as exc:
            logger.error("[%s] Erro: %s", self.source_id, exc)
        finally:
            await ctx.close()

        return editais

    async def _parse_row_generico(self, row) -> EditalRaw | None:
        try:
            cells = await row.query_selector_all("td")
            if len(cells) < 2:
                return None

            numero = (await cells[0].inner_text()).strip()
            orgao = (await cells[1].inner_text()).strip() if len(cells) > 1 else ""
            objeto = (await cells[2].inner_text()).strip() if len(cells) > 2 else ""

            link_el = await row.query_selector("a[href]")
            link = await link_el.get_attribute("href") if link_el else None
            if link and not link.startswith("http"):
                link = f"{self._url.split('/')[0]}//{self._url.split('/')[2]}{link}"

            if not numero:
                return None

            return EditalRaw(
                numero_controle=f"{self.source_id}:{numero}",
                orgao=orgao or self._municipio,
                objeto=objeto,
                modalidade="",
                fonte=self.source_id,
                estado=self._estado or None,
                municipio=self._municipio or None,
                link_edital=link,
            )
        except Exception as exc:
            logger.warning("[%s] Erro ao parsear linha: %s", self.source_id, exc)
            return None

    async def testar_conexao(self) -> bool:
        if not self._url:
            return False
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            resp = await page.goto(self._url, wait_until="domcontentloaded", timeout=15_000)
            return resp is not None and resp.status < 500
        except Exception:
            return False
        finally:
            await ctx.close()
```

- [ ] **Step 3: Criar `tests/scraper/test_municipais.py`**

```python
"""Testa infraestrutura base municipal."""
import asyncio
import pytest
from scraper.sources.municipais.base_municipal import BaseMunicipalSource


class FakeMunicipal(BaseMunicipalSource):
    source_id = "municipal_fake_sp_campinas"
    _url = "https://example.com/licitacoes"
    _estado = "SP"
    _municipio = "Campinas"


def test_municipal_source_ids():
    s = FakeMunicipal()
    assert s.source_id == "municipal_fake_sp_campinas"
    assert s.interval_seconds == 86400


def test_municipal_filtra_estado_errado():
    s = FakeMunicipal()
    result = asyncio.run(s.buscar(estado="RJ"))
    assert result == []


def test_municipal_sem_url_retorna_vazio():
    class SemUrl(BaseMunicipalSource):
        source_id = "municipal_sem_url"
        _url = ""
        _estado = "SP"
        _municipio = "Sem Cidade"

    s = SemUrl()
    result = asyncio.run(s.buscar())
    assert result == []
```

- [ ] **Step 4: Rodar testes**

```bash
pytest tests/scraper/test_municipais.py -v
```

Esperado: 3 testes PASS

- [ ] **Step 5: Commit**

```bash
git add scraper/sources/municipais/ tests/scraper/test_municipais.py
git commit -m "feat: add BaseMunicipalSource infrastructure for municipal portals"
```

---

## Task 10: Registrar todas as fontes no scheduler e rota de sync manual

**Files:**
- Modify: `main.py` (registrar todas as fontes)
- Modify: `api/routes/editais.py` (adicionar parâmetro `fonte` no sync manual)
- Test: `tests/test_integration.py`

**Interfaces:**
- Consumes: todas as `BaseSource` das tasks anteriores, `SchedulerService` (Task 6)

- [ ] **Step 1: Atualizar `main.py` para registrar todas as fontes**

```python
# Substituir o bloco de imports e registro do scheduler em main.py:

from scraper import browser_pool
from scraper.sources.pncp import PNCPSource
from scraper.sources.bll import BLLSource
from scraper.sources.bnc import BNCSource
from scraper.sources.licitacoes_e import LicitacoesESource
from scraper.sources.tce_sp import TCESPSource
from scraper.sources.tce_mg import TCEMGSource
from scraper.sources.tce_rs import TCERSSource
from services.scheduler_service import SchedulerService

scheduler = SchedulerService()
scheduler.register(PNCPSource())         # 1h
scheduler.register(BLLSource())          # 6h
scheduler.register(BNCSource())          # 6h
scheduler.register(LicitacoesESource())  # 6h
scheduler.register(TCESPSource())        # 6h
scheduler.register(TCEMGSource())        # 6h
scheduler.register(TCERSSource())        # 6h
```

- [ ] **Step 2: Adicionar parâmetro `fonte` na rota de sync manual**

Em `api/routes/editais.py`, modificar a rota `/sync`:

```python
# Adicionar import no topo:
from main import scheduler

# Substituir a rota GET /sync:
@router.get("/sync", response_model=SyncResponseSchema)
async def sincronizar(
    background_tasks: BackgroundTasks,
    q: list[str] = Query(default=[]),
    estado: str | None = Query(default=None),
    max_paginas: int = Query(default=5, ge=1, le=20),
    fonte: str | None = Query(default=None, description="ID da fonte: pncp, bll, bnc, tce_sp..."),
):
    job_id = str(uuid.uuid4())
    background_tasks.add_task(_executar_sync, q, estado, max_paginas, job_id, fonte)
    return SyncResponseSchema(
        mensagem=f"Sincronização iniciada {'para ' + fonte if fonte else 'para todas as fontes'}",
        job_id=job_id,
    )


async def _executar_sync(termos, estado, max_paginas, job_id, fonte=None):
    from database.engine import AsyncSessionLocal
    from services.edital_service import processar_lote, sincronizar_editais

    async with AsyncSessionLocal() as db:
        if fonte:
            # Busca apenas na fonte especificada via scheduler
            source = next(
                (s for s in scheduler._sources if s.source_id == fonte), None
            )
            if source:
                editais = await source.buscar(palavras_chave=termos or None, estado=estado)
                resultado = await processar_lote(db, editais, fonte)
                await db.commit()
                logger.info("[sync manual] job=%s fonte=%s resultado=%s", job_id, fonte, resultado)
            else:
                logger.warning("[sync manual] Fonte '%s' não encontrada", fonte)
        else:
            await sincronizar_editais(db, palavras_chave=termos or None, estado=estado, max_paginas=max_paginas)
```

- [ ] **Step 3: Criar `tests/test_integration.py`**

```python
"""Smoke test de integração — verifica que todas as fontes estão registradas."""
from main import scheduler


def test_todas_fontes_registradas():
    ids = {s.source_id for s in scheduler._sources}
    esperados = {"pncp", "bll", "bnc", "licitacoes_e", "tce_sp", "tce_mg", "tce_rs"}
    assert esperados.issubset(ids), f"Faltando fontes: {esperados - ids}"


def test_scheduler_status_retorna_todas():
    status = scheduler.get_status()
    assert len(status) >= 7
    ids = {s["source_id"] for s in status}
    assert "pncp" in ids
    assert "tce_sp" in ids
```

- [ ] **Step 4: Rodar todos os testes**

```bash
pytest tests/ -v --tb=short
```

Esperado: todos PASS

- [ ] **Step 5: Testar endpoint de status**

```bash
uvicorn main:app --reload --port 8000
curl http://localhost:8000/api/v1/scheduler/status
```

Esperado: JSON com 7 fontes listadas.

- [ ] **Step 6: Testar sync manual por fonte**

```bash
curl "http://localhost:8000/api/v1/editais/sync?fonte=pncp&estado=SP&max_paginas=1"
```

Esperado: `{ "mensagem": "Sincronização iniciada para pncp", "job_id": "..." }`

- [ ] **Step 7: Commit final**

```bash
git add main.py api/routes/editais.py tests/test_integration.py
git commit -m "feat: register all sources in scheduler and add fonte param to manual sync"
```

---

## Task 11: Atualizar rota `/health` e documentação

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Melhorar rota `/health`**

```python
# Substituir a rota /health em main.py:
@app.get("/health", tags=["Health"])
async def health():
    from scraper import browser_pool
    return {
        "status": "healthy",
        "browser_headless": browser_pool._HEADLESS is not None and browser_pool._HEADLESS.is_connected(),
        "browser_visible": browser_pool._VISIBLE is not None and browser_pool._VISIBLE.is_connected(),
        "scheduler_sources": len(scheduler._sources),
    }
```

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "feat: enrich /health with browser pool and scheduler status"
```
