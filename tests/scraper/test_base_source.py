"""Testa contrato da BaseSource."""
import pytest
from scraper.sources.base import BaseSource, EditalRaw


class FakeSource(BaseSource):
    source_id = "fake"
    interval_seconds = 3600

    async def buscar(self, palavras_chave=None, estado=None):
        return [
            EditalRaw(
                numero_controle="fake:001",
                orgao="Prefeitura Teste",
                objeto="Teste de objeto",
                modalidade="Pregão",
                fonte="fake",
            )
        ]


@pytest.mark.asyncio
async def test_fake_source_retorna_edital_raw():
    source = FakeSource()
    resultado = await source.buscar()
    assert len(resultado) == 1
    assert resultado[0].fonte == "fake"
    assert resultado[0].numero_controle == "fake:001"


@pytest.mark.asyncio
async def test_testar_conexao_padrao():
    source = FakeSource()
    assert await source.testar_conexao() is True
