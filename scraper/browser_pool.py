"""
Browser pool singleton — compartilhado por todos os scrapers Playwright.
Dois singletons: headless (padrão) e visible (bypass Cloudflare/Turnstile).
"""
import asyncio
import logging
import random

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

logger = logging.getLogger(__name__)

import os

_LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--lang=pt-BR",
]

# Em produção usa o Chromium do sistema; em dev usa o Playwright padrão
_CHROMIUM_EXECUTABLE = os.environ.get("CHROMIUM_EXECUTABLE_PATH") or None

_HEADLESS: Browser | None = None
_VISIBLE: Browser | None = None
_PW: Playwright | None = None  # instância global do playwright
_LOCK = asyncio.Lock()


async def _ensure_pw() -> Playwright:
    """Inicia playwright se necessário. NÃO adquire o lock — deve ser chamado dentro de _LOCK."""
    global _PW
    if _PW is None:
        _PW = await async_playwright().start()
    return _PW


async def _get_pw() -> Playwright:
    """Retorna instância global do playwright, criando se necessário."""
    async with _LOCK:
        return await _ensure_pw()


async def get_browser(headless: bool = True) -> Browser:
    """Retorna singleton de browser. Cria se não existir ou se crashou."""
    global _HEADLESS, _VISIBLE
    async with _LOCK:
        if headless:
            if _HEADLESS is None or not _HEADLESS.is_connected():
                pw = await _ensure_pw()
                _HEADLESS = await pw.chromium.launch(
                    headless=True,
                    args=_LAUNCH_ARGS,
                    executable_path=_CHROMIUM_EXECUTABLE,
                )
                logger.info("Browser headless iniciado")
            return _HEADLESS
        else:
            if _VISIBLE is None or not _VISIBLE.is_connected():
                pw = await _ensure_pw()
                _VISIBLE = await pw.chromium.launch(
                    headless=False,
                    args=_LAUNCH_ARGS,
                    executable_path=_CHROMIUM_EXECUTABLE,
                )
                logger.info("Browser visible iniciado")
            return _VISIBLE


async def new_page(
    headless: bool = True,
    block_resources: bool = True,
    locale: str = "pt-BR",
) -> tuple[BrowserContext, Page]:
    """Cria contexto isolado + página dentro do singleton."""
    browser = await get_browser(headless)
    context = await browser.new_context(
        locale=locale,
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    page = await context.new_page()

    if block_resources:
        async def _block(route, request):
            if request.resource_type in ("image", "stylesheet", "font", "media"):
                await route.abort()
            else:
                await route.continue_()
        await page.route("**/*", _block)

    return context, page


async def close_all() -> None:
    """Fecha todos os browsers. Chamar no lifespan shutdown."""
    global _HEADLESS, _VISIBLE, _PW
    for browser in (_HEADLESS, _VISIBLE):
        if browser and browser.is_connected():
            await browser.close()
    _HEADLESS = None
    _VISIBLE = None
    if _PW:
        await _PW.stop()
        _PW = None
    logger.info("Browser pool encerrado")


async def random_delay(min_ms: int = 500, max_ms: int = 1500) -> None:
    """Delay humanizado para evitar detecção de bot."""
    ms = random.randint(min_ms, max_ms)
    await asyncio.sleep(ms / 1000)
