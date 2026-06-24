"""Testa infraestrutura base municipal."""
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


@pytest.mark.asyncio
async def test_municipal_filtra_estado_errado():
    s = FakeMunicipal()
    result = await s.buscar(estado="RJ")
    assert result == []


@pytest.mark.asyncio
async def test_municipal_sem_url_retorna_vazio():
    class SemUrl(BaseMunicipalSource):
        source_id = "municipal_sem_url"
        _url = ""
        _estado = "SP"
        _municipio = "Sem Cidade"

    s = SemUrl()
    result = await s.buscar()
    assert result == []


@pytest.mark.asyncio
async def test_testar_conexao_sem_url_retorna_false():
    class SemUrl(BaseMunicipalSource):
        source_id = "municipal_sem_url_2"
        _url = ""
        _estado = ""
        _municipio = ""

    s = SemUrl()
    assert await s.testar_conexao() is False
