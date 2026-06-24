"""Fonte BLL — Bolsa de Licitações e Leilões (bll.org.br)."""
import logging

from scraper import browser_pool
from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)


class BLLSource(BaseSource):
    source_id = "bll"
    interval_seconds = 21600  # 6 horas
    _base_url = "https://bll.org.br/licitacao/consulta"

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        editais: list[EditalRaw] = []
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            await page.goto(self._base_url, wait_until="domcontentloaded", timeout=30_000)
            await browser_pool.random_delay(800, 1400)

            await page.wait_for_selector("table.licitacoes, .lista-licitacoes, #tblLicitacoes", timeout=15_000)

            rows = await page.query_selector_all("table tr[data-id], .item-licitacao, tr.licitacao")
            for row in rows:
                edital = await self._parse_row(row, page)
                if edital:
                    if palavras_chave:
                        texto = f"{edital.objeto} {edital.orgao}".lower()
                        if not all(p.lower() in texto for p in palavras_chave):
                            continue
                    if estado and edital.estado and edital.estado.upper() != estado.upper():
                        continue
                    editais.append(edital)

            logger.info("[BLL] %d editais encontrados", len(editais))
        except Exception as exc:
            logger.error("[BLL] Erro ao buscar: %s", exc)
        finally:
            await ctx.close()

        return editais

    async def _parse_row(self, row, page) -> EditalRaw | None:
        try:
            numero = None
            for sel_num in ("td:nth-child(1)", ".numero", "[data-field='numero']"):
                el = await row.query_selector(sel_num)
                if el:
                    numero = (await el.inner_text()).strip()
                    break

            objeto = ""
            for sel_obj in ("td:nth-child(3)", ".objeto", "[data-field='objeto']"):
                el = await row.query_selector(sel_obj)
                if el:
                    objeto = (await el.inner_text()).strip()
                    break

            orgao = ""
            for sel_org in ("td:nth-child(2)", ".orgao", "[data-field='orgao']"):
                el = await row.query_selector(sel_org)
                if el:
                    orgao = (await el.inner_text()).strip()
                    break

            link_el = await row.query_selector("a[href*='licitacao'], a[href*='edital']")
            link = await link_el.get_attribute("href") if link_el else None
            if link and not link.startswith("http"):
                link = f"https://bll.org.br{link}"

            if not numero:
                return None

            return EditalRaw(
                numero_controle=f"bll:{numero}",
                orgao=orgao,
                objeto=objeto,
                modalidade="",
                fonte="bll",
                link_edital=link,
            )
        except Exception as exc:
            logger.warning("[BLL] Erro ao parsear linha: %s", exc)
            return None

    async def testar_conexao(self) -> bool:
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            resp = await page.goto(self._base_url, wait_until="domcontentloaded", timeout=15_000)
            return resp is not None and resp.status < 500
        except Exception:
            return False
        finally:
            await ctx.close()
