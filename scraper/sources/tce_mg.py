"""Fonte TCE-MG — transparencia.tce.mg.gov.br.

NOTA: O portal usa Angular SPA com Google reCAPTCHA antes de carregar os dados
de licitações. O scraping automatizado é bloqueado pelo CAPTCHA. Esta fonte
retorna lista vazia até que uma API alternativa sem CAPTCHA seja identificada.
"""
import logging

from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)


class TCEMGSource(BaseSource):
    source_id = "tce_mg"
    interval_seconds = 21600
    _base_url = "https://transparencia.tce.mg.gov.br/#/licitacao"

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "MG":
            return []
        logger.warning("[TCE-MG] Portal requer reCAPTCHA — scraping indisponível")
        return []

    async def testar_conexao(self) -> bool:
        return False
