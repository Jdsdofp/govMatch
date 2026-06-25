"""Fonte TCE-RS — tcers.tc.br / LicitaCon.

NOTA: O domínio www1.tce.rs.gov.br não resolve mais. O TCE-RS migrou para
tcers.tc.br. O sistema LicitaCon não tem busca pública sem login — retornamos
lista vazia até identificar API alternativa.
"""
import logging
import httpx

from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)

_HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}


class TCERSSource(BaseSource):
    source_id = "tce_rs"
    interval_seconds = 21600
    _base_url = "https://tcers.tc.br/"

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "RS":
            return []
        logger.warning("[TCE-RS] LicitaCon não tem busca pública sem login — fonte indisponível")
        return []

    async def testar_conexao(self) -> bool:
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=10, follow_redirects=True) as c:
                r = await c.get(self._base_url)
                return r.status_code < 500
        except Exception:
            return False
