"""Fonte Licitações-e — Portal BB (licitacoes-e.com.br)."""
import logging

from scraper import browser_pool
from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)


class LicitacoesESource(BaseSource):
    source_id = "licitacoes_e"
    interval_seconds = 21600
    _base_url = "https://www.licitacoes-e.com.br/aop/pesquisarLicitacao.aop"

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        editais: list[EditalRaw] = []
        ctx, page = await browser_pool.new_page(headless=True)
        try:
            await page.goto(self._base_url, wait_until="domcontentloaded", timeout=30_000)
            await browser_pool.random_delay(1000, 2000)

            captured: list[dict] = []

            async def on_response(response):
                if "pesquisarLicitacao" in response.url and "json" in (response.headers.get("content-type", "")):
                    try:
                        data = await response.json()
                        if isinstance(data, list):
                            captured.extend(data)
                        elif isinstance(data, dict):
                            captured.extend(data.get("licitacoes", data.get("lista", [])))
                    except Exception:
                        pass

            page.on("response", on_response)

            await page.wait_for_selector("#tblResultado, .resultado-licitacao, table.listagem", timeout=20_000)
            await browser_pool.random_delay(500, 1000)

            if captured:
                for item in captured:
                    edital = _mapear_json_bb(item)
                    if edital:
                        editais.append(edital)
            else:
                rows = await page.query_selector_all("#tblResultado tr[id], .resultado-licitacao")
                for row in rows:
                    edital = await _parse_row_bb(row)
                    if edital:
                        editais.append(edital)

            if palavras_chave:
                editais = [
                    e for e in editais
                    if all(p.lower() in f"{e.objeto} {e.orgao}".lower() for p in palavras_chave)
                ]
            if estado:
                editais = [e for e in editais if not e.estado or e.estado.upper() == estado.upper()]

            logger.info("[Licitações-e] %d editais encontrados", len(editais))
        except Exception as exc:
            logger.error("[Licitações-e] Erro: %s", exc)
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


def _mapear_json_bb(item: dict) -> EditalRaw | None:
    try:
        numero = str(item.get("numeroLicitacao") or item.get("codigoLicitacao") or "")
        if not numero:
            return None
        return EditalRaw(
            numero_controle=f"licitacoes_e:{numero}",
            orgao=item.get("nomeOrgao") or item.get("orgao") or "",
            objeto=item.get("objeto") or item.get("descricao") or "",
            modalidade=item.get("modalidade") or "",
            fonte="licitacoes_e",
            link_edital=item.get("linkEdital") or item.get("url"),
        )
    except Exception as exc:
        logger.warning("[Licitações-e] Erro ao mapear JSON: %s", exc)
        return None


async def _parse_row_bb(row) -> EditalRaw | None:
    try:
        numero = None
        for sel in ("td:nth-child(1)", ".num-licitacao"):
            el = await row.query_selector(sel)
            if el:
                numero = (await el.inner_text()).strip()
                break
        if not numero:
            return None

        objeto = ""
        for sel in ("td:nth-child(3)", ".objeto"):
            el = await row.query_selector(sel)
            if el:
                objeto = (await el.inner_text()).strip()
                break

        orgao = ""
        for sel in ("td:nth-child(2)", ".orgao"):
            el = await row.query_selector(sel)
            if el:
                orgao = (await el.inner_text()).strip()
                break

        return EditalRaw(
            numero_controle=f"licitacoes_e:{numero}",
            orgao=orgao,
            objeto=objeto,
            modalidade="",
            fonte="licitacoes_e",
        )
    except Exception as exc:
        logger.warning("[Licitações-e] Erro ao parsear linha: %s", exc)
        return None
