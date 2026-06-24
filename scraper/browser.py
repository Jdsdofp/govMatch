"""
Download de PDFs via Playwright (proteção por sessão).
Busca de editais delegada para PNCPSource via GovMatchScraper.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import httpx

from config import settings
from scraper.sources.pncp import PNCPSource as _PNCPSource

logger = logging.getLogger(__name__)


@dataclass
class EditalRaw:
    numero_controle: str
    orgao: str
    uasg: str | None
    objeto: str
    modalidade: str
    valor_estimado: float | None
    data_abertura: datetime | None
    data_encerramento: datetime | None
    link_edital: str | None
    link_pdf: str | None
    exclusivo_me: bool
    estado: str | None
    municipio: str | None
    texto_pdf: str | None = field(default=None)


# ── download de PDF (sync_playwright em thread) ───────────────────────────────

def _baixar_pdf_sync(url_pdf: str, nome_arquivo: str, headless: bool = True) -> Path | None:
    """Baixa PDF via Playwright síncrono. Chamado via asyncio.to_thread()."""
    from playwright.sync_api import sync_playwright

    destino = settings.PDF_DOWNLOAD_DIR / nome_arquivo
    if destino.exists():
        return destino

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, args=["--no-sandbox"])
        context = browser.new_context()
        page = context.new_page()
        try:
            with page.expect_download(timeout=60_000) as dl_info:
                page.goto(url_pdf, wait_until="commit", timeout=30_000)
            dl = dl_info.value
            dl.save_as(destino)
            logger.info("PDF salvo em %s", destino)
            return destino
        except Exception as exc:
            logger.error("Playwright falhou para %s: %s — tentando httpx", url_pdf, exc)
            return _baixar_pdf_httpx_sync(url_pdf, destino)
        finally:
            page.close()
            context.close()
            browser.close()


def _baixar_pdf_httpx_sync(url: str, destino: Path) -> Path | None:
    try:
        with httpx.Client(follow_redirects=True, timeout=60) as client:
            r = client.get(url)
            r.raise_for_status()
            destino.write_bytes(r.content)
            return destino
    except Exception as exc:
        logger.error("Fallback httpx falhou para %s: %s", url, exc)
        return None


# ── interface pública (mantém compatibilidade com edital_service.py) ──────────

class GovMatchScraper:
    def __init__(self, headless: bool = True) -> None:
        self._headless = headless

    async def __aenter__(self) -> "GovMatchScraper":
        return self

    async def __aexit__(self, *_) -> None:
        pass

    async def buscar_editais(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
        max_paginas: int = 5,
    ) -> list[EditalRaw]:
        """Delega para PNCPSource para manter compatibilidade com edital_service."""
        source = _PNCPSource()
        if estado:
            source_results = await source._buscar_uf(estado.upper(), palavras_chave, max_paginas)
        else:
            source_results = await source.buscar(palavras_chave, None)
        return [
            EditalRaw(
                numero_controle=r.numero_controle,
                orgao=r.orgao,
                uasg=r.uasg,
                objeto=r.objeto,
                modalidade=r.modalidade,
                valor_estimado=r.valor_estimado,
                data_abertura=r.data_abertura,
                data_encerramento=r.data_encerramento,
                link_edital=r.link_edital,
                link_pdf=r.link_pdf,
                exclusivo_me=r.exclusivo_me,
                estado=r.estado,
                municipio=r.municipio,
                texto_pdf=r.texto_pdf,
            )
            for r in source_results
        ]

    async def baixar_pdf(self, url_pdf: str, nome_arquivo: str) -> Path | None:
        return await asyncio.to_thread(_baixar_pdf_sync, url_pdf, nome_arquivo, self._headless)
