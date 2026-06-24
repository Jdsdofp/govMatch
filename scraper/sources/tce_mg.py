"""Fonte TCE-MG — licitacao.tce.mg.gov.br."""
import logging

from scraper import browser_pool
from scraper.sources.base import BaseSource, EditalRaw
from scraper.sources.tce_sp import _parse_row_tce

logger = logging.getLogger(__name__)


class TCEMGSource(BaseSource):
    source_id = "tce_mg"
    interval_seconds = 21600
    _base_url = "https://licitacao.tce.mg.gov.br/ConsultaLicitacao"

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "MG":
            return []

        editais: list[EditalRaw] = []
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            await page.goto(self._base_url, wait_until="domcontentloaded", timeout=30_000)
            await browser_pool.random_delay(800, 1500)

            await page.wait_for_selector(
                "table, .grid-licitacoes, #grdLicitacoes",
                timeout=20_000,
            )

            rows = await page.query_selector_all(
                "table tr:not(:first-child), .grid-licitacoes tr, #grdLicitacoes tr"
            )
            for row in rows:
                edital = await _parse_row_tce(row, "tce_mg", "MG")
                if edital:
                    if palavras_chave:
                        texto = f"{edital.objeto} {edital.orgao}".lower()
                        if not all(p.lower() in texto for p in palavras_chave):
                            continue
                    editais.append(edital)

            logger.info("[TCE-MG] %d editais encontrados", len(editais))
        except Exception as exc:
            logger.error("[TCE-MG] Erro: %s", exc)
        finally:
            await ctx.close()

        return editais

    async def testar_conexao(self) -> bool:
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            resp = await page.goto(self._base_url, wait_until="domcontentloaded", timeout=15_000)
            return resp is not None and resp.status < 500
        except Exception:
            return False
        finally:
            await ctx.close()
