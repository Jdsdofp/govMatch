"""Smoke tests de estrutura para fontes TCE."""
import asyncio
import pytest
from scraper.sources.tce_sp import TCESPSource
from scraper.sources.tce_mg import TCEMGSource
from scraper.sources.tce_rs import TCERSSource
from scraper.sources.tce_ro import TCEROSource
from scraper.sources.tce_rn import TCERNSource
from scraper.sources.tce_ma import TCEMASource
from scraper.sources.tce_pe import TCEPESource


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
    assert s.interval_seconds == 86400


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


def test_tce_ro_ids():
    s = TCEROSource()
    assert s.source_id == "tce_ro"
    assert s.interval_seconds == 21600


def test_tce_rn_ids():
    s = TCERNSource()
    assert s.source_id == "tce_rn"
    assert s.interval_seconds == 21600


@pytest.mark.asyncio
async def test_tce_ro_filtra_estado_errado():
    s = TCEROSource()
    result = await s.buscar(estado="SP")
    assert result == []


@pytest.mark.asyncio
async def test_tce_rn_filtra_estado_errado():
    s = TCERNSource()
    result = await s.buscar(estado="SP")
    assert result == []


def test_tce_ma_ids():
    s = TCEMASource()
    assert s.source_id == "tce_ma"
    assert s.interval_seconds == 21600


@pytest.mark.asyncio
async def test_tce_ma_filtra_estado_errado():
    s = TCEMASource()
    result = await s.buscar(estado="SP")
    assert result == []


def test_tce_pe_ids():
    s = TCEPESource()
    assert s.source_id == "tce_pe"
    assert s.interval_seconds == 86400


@pytest.mark.asyncio
async def test_tce_pe_filtra_estado_errado():
    s = TCEPESource()
    result = await s.buscar(estado="SP")
    assert result == []

