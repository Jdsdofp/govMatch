"""Testes de integração para BrowserPool."""
import pytest
from scraper import browser_pool


@pytest.mark.asyncio
async def test_get_browser_cria_singleton():
    b1 = await browser_pool.get_browser(headless=True)
    b2 = await browser_pool.get_browser(headless=True)
    assert b1 is b2


@pytest.mark.asyncio
async def test_new_page_retorna_contexto_e_pagina():
    ctx, page = await browser_pool.new_page(headless=True)
    assert page is not None
    await ctx.close()


@pytest.mark.asyncio
async def test_close_all_limpa_singletons():
    await browser_pool.get_browser(headless=True)
    await browser_pool.close_all()
    assert browser_pool._HEADLESS is None
    assert browser_pool._PW is None
