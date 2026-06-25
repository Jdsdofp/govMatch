"""Fonte BNC — BNC Compras (bnccompras.com) — mesma estrutura que BLL."""
import logging

from scraper import browser_pool
from scraper.sources.base import BaseSource, EditalRaw
from scraper.sources.bll import BLLSource

logger = logging.getLogger(__name__)

_BASE = "https://bnccompras.com"


class BNCSource(BaseSource):
    source_id = "bnc"
    interval_seconds = 21600
    _base_url = f"{_BASE}/Process/ProcessSearchPublic?param1=0"

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        editais: list[EditalRaw] = []
        ctx, page = await browser_pool.new_page(headless=True, block_resources=False)
        try:
            await page.goto(self._base_url, wait_until="networkidle", timeout=40_000)
            await browser_pool.random_delay(800, 1400)

            await page.wait_for_selector("#tableProcessData tbody tr", timeout=20_000)

            # Reutiliza parser do BLL — mesma estrutura de tabela
            _bll = BLLSource()
            links = await page.query_selector_all("a[href*='ProcessView']")
            for link_el in links:
                edital = await _bll._parse_link_row(link_el, estado)
                if edital:
                    edital = EditalRaw(
                        **{**edital.__dict__, "fonte": "bnc",
                           "numero_controle": edital.numero_controle.replace("bll:", "bnc:", 1)}
                    )
                    if palavras_chave:
                        texto = f"{edital.objeto} {edital.orgao}".lower()
                        if not all(p.lower() in texto for p in palavras_chave):
                            continue
                    editais.append(edital)

            logger.info("[BNC] %d editais encontrados", len(editais))
        except Exception as exc:
            logger.error("[BNC] Erro: %s", exc)
        finally:
            await ctx.close()

        return editais

    async def testar_conexao(self) -> bool:
        ctx, page = await browser_pool.new_page(headless=True, block_resources=False)
        try:
            resp = await page.goto(self._base_url, wait_until="domcontentloaded", timeout=15_000)
            return resp is not None and resp.status < 500
        except Exception:
            return False
        finally:
            await ctx.close()
