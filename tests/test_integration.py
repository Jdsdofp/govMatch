"""Smoke test de integração — verifica que todas as fontes estão registradas."""
import pytest
from main import scheduler


def test_todas_fontes_registradas():
    ids = {s.source_id for s in scheduler._sources}
    esperados = {"pncp", "bll", "bnc", "licitacoes_e", "tce_sp", "tce_mg", "tce_rs"}
    assert esperados.issubset(ids), f"Faltando fontes: {esperados - ids}"


def test_scheduler_tem_7_ou_mais_fontes():
    assert len(scheduler._sources) >= 7


def test_scheduler_status_tem_todos_ids():
    status = scheduler.get_status()
    ids = {s["source_id"] for s in status}
    for esperado in ["pncp", "bll", "bnc", "licitacoes_e", "tce_sp", "tce_mg", "tce_rs"]:
        assert esperado in ids, f"Faltando no status: {esperado}"
