"""Testa processar_lote com banco SQLite em memória."""
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from database.engine import Base
from scraper.sources.base import EditalRaw
from services.edital_service import processar_lote


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


def make_edital(numero="bll:001"):
    return EditalRaw(
        numero_controle=numero,
        orgao="Prefeitura Teste",
        objeto="Aquisição de material",
        modalidade="Pregão",
        fonte="bll",
    )


@pytest.mark.asyncio
async def test_processar_lote_insere_novo(db_session):
    editais = [make_edital("bll:001")]
    resultado = await processar_lote(db_session, editais, "bll")
    assert resultado["novos"] == 1
    assert resultado["duplicados"] == 0
    assert resultado["erros"] == 0


@pytest.mark.asyncio
async def test_processar_lote_deduplica(db_session):
    editais = [make_edital("bll:002")]
    await processar_lote(db_session, editais, "bll")
    resultado = await processar_lote(db_session, editais, "bll")
    assert resultado["novos"] == 0
    assert resultado["duplicados"] == 1
    assert resultado["erros"] == 0


@pytest.mark.asyncio
async def test_processar_lote_retorna_fonte(db_session):
    editais = [make_edital("bll:003")]
    resultado = await processar_lote(db_session, editais, "bll")
    assert resultado["fonte"] == "bll"
