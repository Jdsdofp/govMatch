"""Agendador de scrapers — cada BaseSource tem seu próprio intervalo."""
import logging
import random
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

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
                "next_run": getattr(job, "next_run_time", None).isoformat()
                    if job and getattr(job, "next_run_time", None) else None,
                "last_run": self._last_run[source.source_id].isoformat()
                    if self._last_run[source.source_id] else None,
                "last_count": self._last_count[source.source_id],
                "last_error": self._last_error[source.source_id],
            })
        return status
