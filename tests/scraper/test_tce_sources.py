"""Smoke tests de estrutura para fontes TCE."""
import asyncio
import pytest
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


@pytest.mark.asyncio
async def test_tce_sp_filtra_estado_errado():
    """buscar deve retornar lista vazia se estado != SP."""
    s = TCESPSource()
    result = await s.buscar(estado="MG")
    assert result == []


@pytest.mark.asyncio
async def test_tce_mg_filtra_estado_errado():
    s = TCEMGSource()
    result = await s.buscar(estado="SP")
    assert result == []


@pytest.mark.asyncio
async def test_tce_rs_filtra_estado_errado():
    s = TCERSSource()
    result = await s.buscar(estado="SP")
    assert result == []
