"""Fonte TCE-SP — tce.sp.gov.br."""
import logging

from scraper import browser_pool
from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)


class TCESPSource(BaseSource):
    source_id = "tce_sp"
    interval_seconds = 21600
    _base_url = "https://www.tce.sp.gov.br/licitacoes"

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "SP":
            return []

        editais: list[EditalRaw] = []
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            await page.goto(self._base_url, wait_until="domcontentloaded", timeout=30_000)
            await browser_pool.random_delay(800, 1500)

            await page.wait_for_selector(
                "table.tabela-licitacoes, .licitacao-row, #resultado-consulta",
                timeout=20_000,
            )

            rows = await page.query_selector_all(
                "table tr[data-id], .licitacao-row, #resultado-consulta tr"
            )
            for row in rows:
                edital = await _parse_row_tce(row, "tce_sp", "SP")
                if edital:
                    if palavras_chave:
                        texto = f"{edital.objeto} {edital.orgao}".lower()
                        if not all(p.lower() in texto for p in palavras_chave):
                            continue
                    editais.append(edital)

            logger.info("[TCE-SP] %d editais encontrados", len(editais))
        except Exception as exc:
            logger.error("[TCE-SP] Erro: %s", exc)
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


async def _parse_row_tce(row, fonte: str, estado: str) -> EditalRaw | None:
    """Helper compartilhado entre TCEs — seletores fuzzy por ordem de coluna."""
    try:
        numero = None
        for sel in ("td:nth-child(1)", ".numero-edital", "[data-label='Número']"):
            el = await row.query_selector(sel)
            if el:
                texto = (await el.inner_text()).strip()
                if texto and texto.lower() not in ("número", "nº", "#"):
                    numero = texto
                    break

        if not numero:
            return None

        objeto = ""
        for sel in ("td:nth-child(3)", ".objeto-licitacao", "[data-label='Objeto']"):
            el = await row.query_selector(sel)
            if el:
                objeto = (await el.inner_text()).strip()
                break

        orgao = ""
        for sel in ("td:nth-child(2)", ".orgao-licitacao", "[data-label='Órgão']"):
            el = await row.query_selector(sel)
            if el:
                orgao = (await el.inner_text()).strip()
                break

        link_el = await row.query_selector("a[href*='edital'], a[href*='licitacao']")
        link = await link_el.get_attribute("href") if link_el else None

        if not objeto:
            return None

        return EditalRaw(
            numero_controle=f"{fonte}:{numero}",
            orgao=orgao,
            objeto=objeto,
            modalidade="",
            fonte=fonte,
            estado=estado,
            link_edital=link,
        )
    except Exception as exc:
        logger.warning("[%s] Erro ao parsear linha: %s", fonte, exc)
        return None
