"""Fonte TCE-PI — sistemas.tce.pi.gov.br/muralic (JSF/PrimeFaces portal).

Usa Playwright porque o portal JSF vincula o estado da sessão ao ViewState
do servidor — não é possível reproduzir o fluxo com httpx puro.

Fluxo:
  1. Navegar para /muralic/
  2. Preencher filtro Órgão/UG com "Teresina"
  3. Clicar em Pesquisar e aguardar resultados (~10k licitações)
  4. Interceptar o download ao clicar em "exportar para planilha excel"
  5. Parsear o Excel com openpyxl

Cobertura: municípios de Teresina (PI).
"""
import io
import logging
from datetime import datetime

import openpyxl

from scraper import browser_pool
from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)

_URL = "https://sistemas.tce.pi.gov.br/muralic/"


class TCEPISource(BaseSource):
    source_id = "tce_pi"
    interval_seconds = 86400  # 24h

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "PI":
            return []

        xlsx_bytes = await _baixar_excel_playwright()
        if not xlsx_bytes:
            return []

        editais = _processar_excel(xlsx_bytes, palavras_chave)
        logger.info("[TCE-PI] %d editais processados", len(editais))
        return editais

    async def testar_conexao(self) -> bool:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15, follow_redirects=True, verify=False) as c:
                r = await c.get(_URL)
                return r.status_code == 200
        except Exception:
            return False


async def _baixar_excel_playwright() -> bytes | None:
    context, page = await browser_pool.new_page(headless=True, block_resources=False)
    try:
        # Navegar para o portal
        await page.goto(_URL, wait_until="networkidle", timeout=30000)

        # O portal abre um modal — clicar em "MURAL DE LICITAÇÕES"
        try:
            btn_mural = page.get_by_role("button", name="MURAL DE LICITAÇÕES")
            if await btn_mural.is_visible(timeout=5000):
                await btn_mural.click()
                await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass  # Modal pode não aparecer em todas as sessões

        # Preencher filtro Órgão/UG com "Teresina"
        campo_ug = page.get_by_placeholder("informe parte do nome do órgão ou município, etc")
        await campo_ug.fill("Teresina")

        # Clicar em Pesquisar e aguardar resultados
        await page.get_by_role("button", name="Pesquisar").click()
        await page.wait_for_selector("text=lic.", timeout=30000)

        # Interceptar download ao clicar em exportar
        async with page.expect_download(timeout=60000) as download_info:
            await page.get_by_role("link", name="exportar para planilha excel").click()

        download = await download_info.value
        stream = await download.failure()
        if stream:
            logger.error("[TCE-PI] Falha no download: %s", stream)
            return None

        # Ler bytes do arquivo
        path = await download.path()
        with open(path, "rb") as f:
            return f.read()

    except Exception as exc:
        logger.error("[TCE-PI] Erro no Playwright: %s", exc)
        return None
    finally:
        await context.close()


# ── processamento do Excel ────────────────────────────────────────────────────

def _processar_excel(xlsx_bytes: bytes, palavras_chave: list[str] | None) -> list[EditalRaw]:
    editais: list[EditalRaw] = []
    try:
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            edital = _mapear_linha(row)
            if edital is None:
                continue
            if palavras_chave:
                texto = f"{edital.objeto} {edital.orgao}".lower()
                if not all(p.lower() in texto for p in palavras_chave):
                    continue
            editais.append(edital)
    except Exception as exc:
        logger.error("[TCE-PI] Erro ao processar Excel: %s", exc)
    return editais


def _mapear_linha(row: tuple) -> EditalRaw | None:
    try:
        # Colunas (0-indexed): orgao, esfera, nr_proc_tce, nr_procedimento,
        # regime, modalidade, forma, criterio, tipo_objeto, objeto,
        # dt_abert, valor, status, ..., link (19)
        if not row or len(row) < 13:
            return None
        orgao = str(row[0] or "").strip()
        nr_proc_tce = str(row[2] or "").strip()       # ex: LW-007256/26
        nr_procedimento = str(row[3] or "").strip()   # ex: Pregão nº PE 90058/2026
        modalidade = str(row[5] or "").strip()
        objeto = str(row[9] or "").strip()
        dt_abert = _parse_data(row[10])
        valor = _parse_float(row[11])
        link = str(row[19] or "").strip() if len(row) > 19 else None

        if not nr_proc_tce and not nr_procedimento:
            return None

        numero_controle = f"tce_pi:{nr_proc_tce}" if nr_proc_tce else f"tce_pi:{nr_procedimento}"

        return EditalRaw(
            numero_controle=numero_controle,
            orgao=orgao,
            objeto=objeto,
            modalidade=modalidade,
            valor_estimado=valor,
            data_abertura=dt_abert,
            data_encerramento=None,
            link_edital=link or None,
            exclusivo_me=False,
            estado="PI",
            fonte="tce_pi",
        )
    except Exception as exc:
        logger.debug("[TCE-PI] Erro ao mapear linha: %s", exc)
        return None


def _parse_float(v) -> float | None:
    if v is None:
        return None
    s = str(v).strip().replace("\xa0", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_data(raw) -> datetime | None:
    if not raw:
        return None
    s = str(raw).strip()[:16]
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None
