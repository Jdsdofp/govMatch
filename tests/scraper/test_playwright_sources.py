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
