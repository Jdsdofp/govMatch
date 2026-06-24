"""Fonte BNC — Banco Nacional de Contratações Públicas (bnc.org.br)."""
import logging

from scraper import browser_pool
from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)


class BNCSource(BaseSource):
    source_id = "bnc"
    interval_seconds = 21600
    _base_url = "https://www.bnc.org.br/licitacoes"

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

            await page.wait_for_selector(".licitacao-item, table.licitacoes, #lista-licitacoes", timeout=15_000)

            items = await page.query_selector_all(".licitacao-item, table tr.licitacao")
            for item in items:
                edital = await self._parse_item(item)
                if edital:
                    if palavras_chave:
                        texto = f"{edital.objeto} {edital.orgao}".lower()
                        if not all(p.lower() in texto for p in palavras_chave):
                            continue
                    if estado and edital.estado and edital.estado.upper() != estado.upper():
                        continue
                    editais.append(edital)

            logger.info("[BNC] %d editais encontrados", len(editais))
        except Exception as exc:
            logger.error("[BNC] Erro: %s", exc)
        finally:
            await ctx.close()

        return editais

    async def _parse_item(self, item) -> EditalRaw | None:
        try:
            numero = None
            for sel in (".numero-licitacao", "td:nth-child(1)", "[data-numero]"):
                el = await item.query_selector(sel)
                if el:
                    numero = (await el.inner_text()).strip()
                    break

            objeto = ""
            for sel in (".objeto-licitacao", "td:nth-child(3)", ".descricao"):
                el = await item.query_selector(sel)
                if el:
                    objeto = (await el.inner_text()).strip()
                    break

            orgao = ""
            for sel in (".orgao-licitacao", "td:nth-child(2)", ".entidade"):
                el = await item.query_selector(sel)
                if el:
                    orgao = (await el.inner_text()).strip()
                    break

            link_el = await item.query_selector("a[href]")
            link = await link_el.get_attribute("href") if link_el else None
            if link and not link.startswith("http"):
                link = f"https://www.bnc.org.br{link}"

            if not numero:
                return None

            return EditalRaw(
                numero_controle=f"bnc:{numero}",
                orgao=orgao,
                objeto=objeto,
                modalidade="",
                fonte="bnc",
                link_edital=link,
            )
        except Exception as exc:
            logger.warning("[BNC] Erro ao parsear item: %s", exc)
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
