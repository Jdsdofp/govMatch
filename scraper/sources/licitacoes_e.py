"""Fonte Licitações-e — Portal BB (licitacoes-e.com.br).

NOTA: O portal usa CAPTCHA ("Digite os caracteres abaixo para continuar") no
formulário de pesquisa e Cloudflare WAF que bloqueia httpx mesmo com cookies de
sessão válidos. O scraping automatizado é inviável. Esta fonte retorna lista
vazia até que uma API alternativa sem CAPTCHA seja identificada.
"""
import logging

from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)


class LicitacoesESource(BaseSource):
    source_id = "licitacoes_e"
    interval_seconds = 21600
    _base_url = "https://www.licitacoes-e.com.br/aop/pesquisar-licitacao.aop?opcao=preencherPesquisar"

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        logger.warning("[Licitações-e] Portal requer CAPTCHA e Cloudflare WAF — scraping indisponível")
        return []

    async def testar_conexao(self) -> bool:
        return False
