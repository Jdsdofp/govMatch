"""Fonte TCE-RS — tce.rs.gov.br."""
import logging

from scraper import browser_pool
from scraper.sources.base import BaseSource, EditalRaw
from scraper.sources.tce_sp import _parse_row_tce

logger = logging.getLogger(__name__)


class TCERSSource(BaseSource):
    source_id = "tce_rs"
    interval_seconds = 21600
    _base_url = "https://www1.tce.rs.gov.br/aplicprod/f?p=50500:2"

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "RS":
            return []

        editais: list[EditalRaw] = []
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            await page.goto(self._base_url, wait_until="domcontentloaded", timeout=30_000)
            await browser_pool.random_delay(800, 1500)

            await page.wait_for_selector(
                "table.apexir_WORKSHEET_DATA, .t-Report-wrap table, table.licitacoes",
                timeout=20_000,
            )

            rows = await page.query_selector_all(
                "table.apexir_WORKSHEET_DATA tr[class*='data'], .t-Report-wrap table tr:not(:first-child)"
            )
            for row in rows:
                edital = await _parse_row_tce(row, "tce_rs", "RS")
                if edital:
                    if palavras_chave:
                        texto = f"{edital.objeto} {edital.orgao}".lower()
                        if not all(p.lower() in texto for p in palavras_chave):
                            continue
                    editais.append(edital)

            logger.info("[TCE-RS] %d editais encontrados", len(editais))
        except Exception as exc:
            logger.error("[TCE-RS] Erro: %s", exc)
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
