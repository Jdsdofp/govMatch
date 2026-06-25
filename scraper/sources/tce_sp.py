"""Fonte TCE-SP — tce.sp.gov.br.

NOTA: O portal de licitações do TCE-SP migrou para Power BI embed em 2025,
não sendo diretamente scrapável via Playwright. Esta fonte retorna lista vazia
até que uma API alternativa seja identificada.
"""
import logging

from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)


class TCESPSource(BaseSource):
    source_id = "tce_sp"
    interval_seconds = 21600
    _base_url = "https://www.tce.sp.gov.br/painel-contratacao-tcesp"

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "SP":
            return []
        logger.warning("[TCE-SP] Portal migrou para Power BI — scraping indisponível")
        return []

    async def testar_conexao(self) -> bool:
        return False


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
