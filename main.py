"""
GovMatch API — ponto de entrada principal.

Execução local:
    uvicorn main:app --reload --port 8000

Produção:
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

# Playwright exige ProactorEventLoop no Windows para criar subprocessos.
# O uvicorn usa SelectorEventLoop por padrão, o que causa NotImplementedError.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes.editais import router as editais_router
from api.routes.scheduler import router as scheduler_router
from config import settings
from database.engine import create_tables
from scraper import browser_pool
from scraper.sources.pncp import PNCPSource
from scraper.sources.bll import BLLSource
from scraper.sources.bnc import BNCSource
from scraper.sources.licitacoes_e import LicitacoesESource
from scraper.sources.tce_sp import TCESPSource
from scraper.sources.tce_mg import TCEMGSource
from scraper.sources.tce_rs import TCERSSource
from services.scheduler_service import SchedulerService

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── instância global do scheduler ────────────────────────────────────────────

scheduler = SchedulerService()
scheduler.register(PNCPSource())          # 1h
scheduler.register(BLLSource())           # 6h
scheduler.register(BNCSource())           # 6h
scheduler.register(LicitacoesESource())   # 6h
scheduler.register(TCESPSource())         # 6h
scheduler.register(TCEMGSource())         # 6h
scheduler.register(TCERSSource())         # 6h


# ── lifecycle ────────────────────────────────────────────────────────────────

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


# ── app ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="GovMatch API",
    description=(
        "API RESTful para busca, raspagem e processamento de editais de "
        "licitação pública brasileira. Consome o PNCP e portais estaduais."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção: lista de domínios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── tratamento global de exceções ────────────────────────────────────────────

@app.exception_handler(Exception)
async def handler_generico(request: Request, exc: Exception):
    logger.error("Erro não tratado em %s: %s", request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detalhe": "Erro interno do servidor.", "codigo": type(exc).__name__},
    )


# ── rotas ────────────────────────────────────────────────────────────────────

app.include_router(editais_router, prefix="/api/v1")
app.include_router(scheduler_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "servico": "GovMatch API", "versao": "1.0.0"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}
