"""
Scraper do PNCP usando httpx (API REST JSON pura — Playwright não é necessário aqui).
Playwright é mantido apenas para download de PDFs protegidos por sessão.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

logger = logging.getLogger(__name__)

# PNCP API pública — documentação: https://pncp.gov.br/api/pncp/swagger-ui/index.html
PNCP_API_BASE = "https://pncp.gov.br/api/pncp/v1"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


@dataclass
class EditalRaw:
    numero_controle: str
    orgao: str
    uasg: str | None
    objeto: str
    modalidade: str
    valor_estimado: float | None
    data_abertura: datetime | None
    data_encerramento: datetime | None
    link_edital: str | None
    link_pdf: str | None
    exclusivo_me: bool
    estado: str | None
    municipio: str | None
    texto_pdf: str | None = field(default=None)


# ── busca via httpx (assíncrona) ──────────────────────────────────────────────

async def _buscar_editais_httpx(
    palavras_chave: list[str] | None,
    estado: str | None,
    max_paginas: int,
) -> list[EditalRaw]:
    """Busca editais na API REST do PNCP via httpx."""
    resultados: list[EditalRaw] = []
    hoje = date.today()
    data_fim = hoje.strftime("%Y%m%d")
    data_ini = (hoje - timedelta(days=30)).strftime("%Y%m%d")

    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        for pagina in range(1, max_paginas + 1):
            params: dict = {
                "dataInicial": data_ini,
                "dataFinal": data_fim,
                "pagina": pagina,
                "tamanhoPagina": 20,
            }
            if estado:
                params["uf"] = estado.upper()

            url = f"{PNCP_API_BASE}/contratacoes/publicadas"
            logger.info("Buscando página %d — %s?%s", pagina, url,
                        "&".join(f"{k}={v}" for k, v in params.items()))

            try:
                resp = await client.get(url, params=params)
            except Exception as exc:
                logger.error("Erro de rede na página %d: %s", pagina, exc)
                break

            if resp.status_code == 404:
                logger.warning("404 na página %d — provavelmente sem resultados nesse período", pagina)
                break
            if resp.status_code != 200:
                logger.warning("Status %d na página %d", resp.status_code, pagina)
                break

            try:
                dados = resp.json()
            except Exception as exc:
                logger.error("Resposta não é JSON na página %d: %s", pagina, exc)
                break

            # A API do PNCP retorna lista direta ou dict com campo "data"
            itens = dados if isinstance(dados, list) else dados.get("data", [])
            if not itens:
                logger.info("Sem itens na página %d — encerrando", pagina)
                break

            for item in itens:
                edital = _mapear_item_pncp(item)
                if edital is None:
                    continue
                # Filtra palavras-chave no lado da aplicação
                if palavras_chave:
                    texto = f"{edital.objeto} {edital.orgao}".lower()
                    if not all(p.lower() in texto for p in palavras_chave):
                        continue
                resultados.append(edital)

            total_paginas = dados.get("totalPaginas", pagina) if isinstance(dados, dict) else pagina
            if pagina >= total_paginas:
                break

            await asyncio.sleep(0.5)  # cortesia ao servidor

    logger.info("Total encontrado: %d editais", len(resultados))
    return resultados


# ── download de PDF (sync_playwright em thread) ───────────────────────────────

def _baixar_pdf_sync(url_pdf: str, nome_arquivo: str, headless: bool = True) -> Path | None:
    """Baixa PDF via Playwright síncrono. Chamado via asyncio.to_thread()."""
    from playwright.sync_api import sync_playwright

    destino = settings.PDF_DOWNLOAD_DIR / nome_arquivo
    if destino.exists():
        return destino

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, args=["--no-sandbox"])
        context = browser.new_context()
        page = context.new_page()
        try:
            with page.expect_download(timeout=60_000) as dl_info:
                page.goto(url_pdf, wait_until="commit", timeout=30_000)
            dl = dl_info.value
            dl.save_as(destino)
            logger.info("PDF salvo em %s", destino)
            return destino
        except Exception as exc:
            logger.error("Playwright falhou para %s: %s — tentando httpx", url_pdf, exc)
            return _baixar_pdf_httpx_sync(url_pdf, destino)
        finally:
            page.close()
            context.close()
            browser.close()


def _baixar_pdf_httpx_sync(url: str, destino: Path) -> Path | None:
    try:
        with httpx.Client(follow_redirects=True, timeout=60) as client:
            r = client.get(url)
            r.raise_for_status()
            destino.write_bytes(r.content)
            return destino
    except Exception as exc:
        logger.error("Fallback httpx falhou para %s: %s", url, exc)
        return None


# ── interface pública (mantém compatibilidade com edital_service.py) ──────────

class GovMatchScraper:
    def __init__(self, headless: bool = True) -> None:
        self._headless = headless

    async def __aenter__(self) -> "GovMatchScraper":
        return self

    async def __aexit__(self, *_) -> None:
        pass

    async def buscar_editais(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
        max_paginas: int = 5,
    ) -> list[EditalRaw]:
        return await _buscar_editais_httpx(palavras_chave, estado, max_paginas)

    async def baixar_pdf(self, url_pdf: str, nome_arquivo: str) -> Path | None:
        return await asyncio.to_thread(_baixar_pdf_sync, url_pdf, nome_arquivo, self._headless)


# ── helpers ───────────────────────────────────────────────────────────────────

def _mapear_item_pncp(item: dict) -> EditalRaw | None:
    try:
        return EditalRaw(
            numero_controle=item.get("numeroControlePNCP") or str(item.get("sequencialCompra", "")),
            orgao=item.get("orgaoEntidade", {}).get("razaoSocial", ""),
            uasg=str(item.get("orgaoEntidade", {}).get("cnpj", "")),
            objeto=item.get("objetoCompra", ""),
            modalidade=item.get("modalidadeNome", ""),
            valor_estimado=_parse_valor(item.get("valorTotalEstimado")),
            data_abertura=_parse_data(item.get("dataAberturaProposta")),
            data_encerramento=_parse_data(item.get("dataEncerramentoProposta")),
            link_edital=item.get("linkSistemaOrigem"),
            link_pdf=None,
            exclusivo_me=_detectar_exclusivo_me(item),
            estado=item.get("unidadeOrgao", {}).get("ufSigla"),
            municipio=item.get("unidadeOrgao", {}).get("municipioNome"),
        )
    except Exception as exc:
        logger.warning("Erro ao mapear item PNCP: %s", exc)
        return None


def _parse_valor(raw) -> float | None:
    if raw is None:
        return None
    try:
        return float(str(raw).replace(".", "").replace(",", "."))
    except (ValueError, TypeError):
        return None


def _parse_data(raw: str | None) -> datetime | None:
    if not raw:
        return None
    formatos = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%d/%m/%Y"]
    for fmt in formatos:
        try:
            return datetime.strptime(raw[:19], fmt)
        except ValueError:
            continue
    return None


def _detectar_exclusivo_me(item: dict) -> bool:
    objeto = (item.get("objetoCompra") or "").lower()
    return any(t in objeto for t in ("me/epp", "exclusivo me", "cota reservada", "microempresa"))
