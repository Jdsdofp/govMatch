# Design: Scraper Multi-Portal com Agendamento

**Data:** 2026-06-24  
**Status:** Aprovado

## Objetivo

Refatorar o scraper do govMatch para suportar múltiplos portais de licitação (PNCP, BLL, BNC, Licitações-e, TCE-SP, TCE-MG, TCE-RS, municipais) com agendamento independente por fonte, browser pool singleton e execução paralela — replicando a sistemática robusta do projeto_leitor (Node.js) em Python/FastAPI.

---

## Arquitetura

### Estrutura de arquivos

```
scraper/
  browser_pool.py          # Singleton Playwright (headless + visible)
  sources/
    base.py                # BaseSource ABC + EditalRaw dataclass
    pncp.py                # Refatorado — httpx paralelo por UF
    bll.py                 # BLL (Bolsa de Licitações e Leilões) — Playwright
    bnc.py                 # BNC (Banco Nacional de Contratações) — Playwright
    licitacoes_e.py        # Licitações-e Banco do Brasil — Playwright
    tce_sp.py              # TCE-SP — Playwright
    tce_mg.py              # TCE-MG — Playwright
    tce_rs.py              # TCE-RS — Playwright
    municipais/
      base_municipal.py    # Base comum para portais municipais
services/
  scheduler_service.py     # APScheduler async com intervalos por fonte
api/routes/
  scheduler.py             # GET /api/v1/scheduler/status
```

---

## Componentes

### 1. BrowserPool (`scraper/browser_pool.py`)

- Singletons: `_headless_browser` e `_visible_browser`
- `get_browser(headless=True)` → inicia se não existir, retorna existente
- `new_page(headless=True)` → cria contexto isolado + página dentro do singleton
- `close_all()` → graceful shutdown (chamado no lifespan)
- Launch args idênticos ao projeto_leitor: `--no-sandbox`, `--disable-blink-features=AutomationControlled`
- Delays humanizados: `random_delay(min_ms, max_ms)` helper
- Interceptação de recursos: bloqueia image/stylesheet/font por padrão (configurável)

### 2. BaseSource (`scraper/sources/base.py`)

```python
@dataclass
class EditalRaw:
    numero_controle: str
    orgao: str
    objeto: str
    modalidade: str | None
    valor_estimado: float | None
    data_abertura: datetime | None
    data_encerramento: datetime | None
    link_edital: str | None
    link_pdf: str | None
    exclusivo_me: bool
    estado: str | None
    municipio: str | None
    fonte: str              # identificador do portal

class BaseSource(ABC):
    source_id: str          # ex: "pncp", "bll", "tce_sp"
    interval_seconds: int   # intervalo de agendamento
    
    @abstractmethod
    async def buscar(self, palavras_chave: list[str], estado: str | None) -> list[EditalRaw]: ...
    
    async def testar_conexao(self) -> bool: ...  # health check
```

### 3. Fontes de Dados

| Fonte | Método | Intervalo | Observação |
|-------|--------|-----------|------------|
| PNCP | httpx (API REST) | 1h | Paralelo por UF via asyncio.gather |
| BLL | Playwright headless | 6h | Site com autenticação parcial |
| BNC | Playwright headless | 6h | Portal federal |
| Licitações-e | Playwright headless | 6h | Banco do Brasil |
| TCE-SP | Playwright headless | 6h | Portal estadual SP |
| TCE-MG | Playwright headless | 6h | Portal estadual MG |
| TCE-RS | Playwright headless | 6h | Portal estadual RS |
| Municipais | Playwright headless | 24h | Base comum reutilizável |

Cada fonte implementa `BaseSource`. Falha de uma não afeta as demais.

### 4. SchedulerService (`services/scheduler_service.py`)

- APScheduler `AsyncIOScheduler`
- `register(source: BaseSource)` → adiciona job com `IntervalTrigger(seconds=source.interval_seconds)`
- `start()` / `shutdown()` — chamados no lifespan FastAPI
- Cada job chama `source.buscar()` → passa resultado para `EditalService.processar_lote()`
- `get_status()` → dict com próxima execução e última execução de cada fonte
- Jitter de ±10% no intervalo para evitar thundering herd

### 5. Rota de Status (`api/routes/scheduler.py`)

```
GET /api/v1/scheduler/status
```

Retorna estado de cada fonte: `{ source_id, interval_s, next_run, last_run, last_count, last_error }`.

---

## Fluxo de Dados

```
FastAPI lifespan
  └─ SchedulerService.start()
       └─ registra todas as BaseSource com seus intervalos

No tick de cada fonte:
  source.buscar(palavras_chave, estado)
    └─ [PNCP] httpx paralelo por UF
    └─ [outros] BrowserPool.new_page() → scrape → close page
       └─ asyncio.gather(return_exceptions=True) por página
  EditalService.processar_lote(editais_raw)
    └─ deduplicação por numero_controle (upsert)
    └─ download PDF + OCR (existente, sem mudança)
    └─ atualiza SyncLog
```

---

## Tratamento de Erros

- `asyncio.gather(return_exceptions=True)` — falha de uma página não cancela o resto
- Retry com `tenacity`: 3 tentativas, backoff exponencial (2s → 4s → 8s)
- Se portal retornar 0 resultados por 3 runs consecutivos → loga warning (possível mudança de layout)
- `SyncLog` registra erros por fonte separadamente
- Browser crashado → pool recria automaticamente na próxima chamada

---

## Mudanças no Código Existente

- `main.py` — lifespan inicia/para `SchedulerService` e `BrowserPool`
- `scraper/browser.py` — refatorado para usar `BrowserPool` em vez de criar browser próprio
- `services/edital_service.py` — adiciona `processar_lote()` (extrai lógica do `sincronizar_editais` existente)
- `api/routes/editais.py` — rota `/sync` dispara run manual de uma fonte específica
- `database/models.py` — adiciona campo `fonte` em `Edital` e em `SyncLog`

---

## Dependências Novas

```
apscheduler>=3.10.4
```

Playwright já está no `requirements.txt`.

---

## Fora do Escopo

- Autenticação nos portais (login/senha)
- Notificações push em tempo real por nova licitação
- Dashboard web de monitoramento
- Portais municipais de cidades específicas (infraestrutura criada, preenchimento posterior)
