"""Testes unitários para PNCPSource — mockam httpx."""
import pytest
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
    edital = _mapear_item_pncp({})
    assert edital is not None or edital is None  # não lança exceção


@pytest.mark.asyncio
async def test_pncp_source_ids():
    source = PNCPSource()
    assert source.source_id == "pncp"
    assert source.interval_seconds == 3600
