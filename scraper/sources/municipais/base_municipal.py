"""Base para scrapers de portais municipais — subclasses precisam apenas de _url."""
import logging

from scraper import browser_pool
from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)


class BaseMunicipalSource(BaseSource):
    """
    Base para portais municipais.

    Subclasse mínima:
        class SaoPauloSource(BaseMunicipalSource):
            source_id = "municipal_sp_sao_paulo"
            _url = "https://e-negocioscidadesp.prefeitura.sp.gov.br/BuscaLicitacao.aspx"
            _estado = "SP"
            _municipio = "São Paulo"
    """

    interval_seconds = 86400  # 24 horas por padrão para municipais
    _url: str = ""
    _estado: str = ""
    _municipio: str = ""

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and self._estado and estado.upper() != self._estado.upper():
            return []
        if not self._url:
            logger.error("[%s] _url não definida", self.source_id)
            return []

        editais: list[EditalRaw] = []
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            await page.goto(self._url, wait_until="domcontentloaded", timeout=30_000)
            await browser_pool.random_delay(800, 1500)

            await page.wait_for_selector("table tr, .licitacao, .edital", timeout=15_000)
            rows = await page.query_selector_all("table tr:not(:first-child)")

            for row in rows:
                edital = await self._parse_row_generico(row)
                if edital:
                    if palavras_chave:
                        texto = f"{edital.objeto} {edital.orgao}".lower()
                        if not all(p.lower() in texto for p in palavras_chave):
                            continue
                    editais.append(edital)

            logger.info("[%s] %d editais encontrados", self.source_id, len(editais))
        except Exception as exc:
            logger.error("[%s] Erro: %s", self.source_id, exc)
        finally:
            await ctx.close()

        return editais

    async def _parse_row_generico(self, row) -> EditalRaw | None:
        try:
            cells = await row.query_selector_all("td")
            if len(cells) < 2:
                return None

            numero = (await cells[0].inner_text()).strip()
            orgao = (await cells[1].inner_text()).strip() if len(cells) > 1 else ""
            objeto = (await cells[2].inner_text()).strip() if len(cells) > 2 else ""

            link_el = await row.query_selector("a[href]")
            link = await link_el.get_attribute("href") if link_el else None
            if link and not link.startswith("http"):
                base = f"{self._url.split('/')[0]}//{self._url.split('/')[2]}"
                link = f"{base}{link}"

            if not numero:
                return None

            return EditalRaw(
                numero_controle=f"{self.source_id}:{numero}",
                orgao=orgao or self._municipio,
                objeto=objeto,
                modalidade="",
                fonte=self.source_id,
                estado=self._estado or None,
                municipio=self._municipio or None,
                link_edital=link,
            )
        except Exception as exc:
            logger.warning("[%s] Erro ao parsear linha: %s", self.source_id, exc)
            return None

    async def testar_conexao(self) -> bool:
        if not self._url:
            return False
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            resp = await page.goto(self._url, wait_until="domcontentloaded", timeout=15_000)
            return resp is not None and resp.status < 500
        except Exception:
            return False
        finally:
            await ctx.close()
