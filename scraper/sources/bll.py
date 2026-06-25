"""Fonte BLL — BLL Compras (bllcompras.com) — busca pública sem login."""
import logging

from scraper import browser_pool
from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)

_BASE = "https://bllcompras.com"


class BLLSource(BaseSource):
    source_id = "bll"
    interval_seconds = 21600  # 6 horas
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

            # Tabela de resultados carregada via AJAX
            await page.wait_for_selector("#tableProcessData tbody tr", timeout=20_000)

            links = await page.query_selector_all("a[href*='ProcessView']")
            for link_el in links:
                edital = await self._parse_link_row(link_el, estado)
                if edital:
                    if palavras_chave:
                        texto = f"{edital.objeto} {edital.orgao}".lower()
                        if not all(p.lower() in texto for p in palavras_chave):
                            continue
                    editais.append(edital)

            logger.info("[BLL] %d editais encontrados", len(editais))
        except Exception as exc:
            logger.error("[BLL] Erro ao buscar: %s", exc)
        finally:
            await ctx.close()

        return editais

    async def _parse_link_row(self, link_el, estado: str | None) -> EditalRaw | None:
        """Parseia linha da tabela #tableProcessData a partir do link ProcessView."""
        try:
            link = await link_el.get_attribute("href") or ""
            row = await link_el.evaluate_handle("el => el.closest('tr')")
            if not row:
                return None

            cells = await row.query_selector_all("td")
            if len(cells) < 5:
                return None

            orgao     = (await cells[1].inner_text()).strip()
            numero    = (await cells[2].inner_text()).strip()
            modalidade = (await cells[3].inner_text()).strip()
            cidade    = (await cells[4].inner_text()).strip()  # "NOME-UF"

            # Extrai UF do campo cidade (ex: "CURITIBA-PR" → "PR")
            uf = cidade.rsplit("-", 1)[-1].strip().upper() if "-" in cidade else ""
            municipio = cidade.rsplit("-", 1)[0].strip().title() if "-" in cidade else cidade

            if estado and uf and uf != estado.upper():
                return None
            if not numero:
                return None

            return EditalRaw(
                numero_controle=f"bll:{numero}",
                orgao=orgao,
                objeto=f"{modalidade} - {orgao}",
                modalidade=modalidade,
                fonte="bll",
                estado=uf or None,
                municipio=municipio or None,
                link_edital=link,
            )
        except Exception as exc:
            logger.warning("[BLL] Erro ao parsear linha: %s", exc)
            return None

    async def testar_conexao(self) -> bool:
        ctx, page = await browser_pool.new_page(headless=True, block_resources=False)
        try:
            resp = await page.goto(self._base_url, wait_until="domcontentloaded", timeout=15_000)
            return resp is not None and resp.status < 500
        except Exception:
            return False
        finally:
            await ctx.close()
