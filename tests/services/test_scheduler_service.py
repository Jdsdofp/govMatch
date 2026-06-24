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
