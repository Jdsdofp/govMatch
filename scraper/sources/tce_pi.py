"""Fonte TCE-PI — sistemas.tce.pi.gov.br/muralic (JSF/PrimeFaces portal).

Fluxo:
  1. GET /muralic/ → obtém jsessionid (cookie) e ViewState (hidden input)
  2. POST AJAX com filtro ug_input=Teresina → pesquisa licitações
  3. POST AJAX para exportar → baixa planilha Excel (.xlsx) com todos os registros
  4. Parseia o Excel com openpyxl

Cobertura: municípios de Teresina (PI) — único município disponível via filtro público.
O portal retorna ~10.000 licitações de Teresina por exportação.
"""
import io
import logging
import re
from datetime import datetime

import httpx
import openpyxl

from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)

_BASE = "https://sistemas.tce.pi.gov.br/muralic"
_INDEX = f"{_BASE}/index.xhtml"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
}
_AJAX_HEADERS = {
    **_HEADERS,
    "Accept": "application/xml, text/xml, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Faces-Request": "partial/ajax",
    "X-Requested-With": "XMLHttpRequest",
}


class TCEPISource(BaseSource):
    source_id = "tce_pi"
    interval_seconds = 86400  # 24h — exportação completa, sem filtro de data

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "PI":
            return []

        try:
            async with httpx.AsyncClient(
                headers=_HEADERS,
                timeout=120,
                follow_redirects=True,
                verify=False,
            ) as c:
                # 1. GET para obter session cookie + ViewState
                r = await c.get(_INDEX)
                if r.status_code != 200:
                    logger.warning("[TCE-PI] GET inicial HTTP %d", r.status_code)
                    return []

                view_state = _extrair_viewstate(r.text)
                jsessionid = _extrair_jsessionid(str(r.url))
                if not view_state:
                    logger.error("[TCE-PI] ViewState não encontrado na página inicial")
                    return []

                url_post = f"{_INDEX};jsessionid={jsessionid}" if jsessionid else _INDEX

                # 2. POST AJAX para pesquisar com filtro Teresina
                payload_pesq = _payload_pesquisar(view_state)
                r2 = await c.post(url_post, content=payload_pesq, headers=_AJAX_HEADERS)
                if r2.status_code != 200:
                    logger.warning("[TCE-PI] POST pesquisa HTTP %d", r2.status_code)
                    return []

                # ViewState pode ter sido atualizado na resposta AJAX
                novo_vs = _extrair_viewstate_xml(r2.text)
                if novo_vs:
                    view_state = novo_vs

                # 3. POST AJAX para exportar Excel
                payload_exp = _payload_exportar(view_state)
                r3 = await c.post(url_post, content=payload_exp, headers=_AJAX_HEADERS)

                # A exportação pode retornar o arquivo diretamente ou via redirect
                xlsx_bytes = None
                content_type = r3.headers.get("content-type", "")
                if "spreadsheet" in content_type or "excel" in content_type or "octet" in content_type:
                    xlsx_bytes = r3.content
                elif "xml" in content_type or "html" in content_type:
                    # Resposta AJAX com redirect para o arquivo
                    download_url = _extrair_download_url(r3.text)
                    if download_url:
                        r4 = await c.get(download_url)
                        xlsx_bytes = r4.content

                if not xlsx_bytes:
                    logger.error("[TCE-PI] Não foi possível obter o arquivo Excel")
                    return []

        except Exception as exc:
            logger.error("[TCE-PI] Erro ao buscar: %s", exc)
            return []

        editais = _processar_excel(xlsx_bytes, palavras_chave)
        logger.info("[TCE-PI] %d editais processados", len(editais))
        return editais

    async def testar_conexao(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True, verify=False) as c:
                r = await c.get(_INDEX)
                return r.status_code == 200
        except Exception:
            return False


# ── helpers de extração ───────────────────────────────────────────────────────

def _extrair_viewstate(html: str) -> str | None:
    m = re.search(r'id="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html)
    return m.group(1) if m else None


def _extrair_viewstate_xml(xml: str) -> str | None:
    m = re.search(r'<update id="javax\.faces\.ViewState[^"]*"><!\[CDATA\[([^\]]+)\]\]>', xml)
    return m.group(1) if m else None


def _extrair_jsessionid(url: str) -> str | None:
    m = re.search(r"jsessionid=([A-Za-z0-9._-]+)", url)
    return m.group(1) if m else None


def _extrair_download_url(xml: str) -> str | None:
    m = re.search(r'window\.location\s*=\s*[\'"]([^\'"]+)[\'"]', xml)
    return m.group(1) if m else None


def _payload_pesquisar(view_state: str) -> bytes:
    from urllib.parse import urlencode
    data = {
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": "btnPesquisar",
        "javax.faces.partial.execute": "j_idt20",
        "javax.faces.partial.render": "growl j_idt20 formListaLic:listaLic",
        "btnPesquisar": "btnPesquisar",
        "j_idt20": "j_idt20",
        "tvPrincipal:j_idt25_focus": "",
        "tvPrincipal:j_idt25_input": "POR_PROCESSO_LICITATORIO",
        "tvPrincipal:j_idt30": "",
        "tvPrincipal:j_idt34_input": "",
        "tvPrincipal:j_idt34_hinput": "",
        "tvPrincipal:status_focus": "",
        "tvPrincipal:status_input": "0",
        "tvPrincipal:ug_input": "Teresina",
        "tvPrincipal:mod_focus": "",
        "tvPrincipal:mod_input": "",
        "tvPrincipal:j_idt52": "",
        "tvPrincipal:dataAberturaInicial_input": "",
        "tvPrincipal:dataAberturaFinal_input": "",
        "tvPrincipal:tvMaisFiltros:j_idt62_focus": "",
        "tvPrincipal:tvMaisFiltros:j_idt62_input": "POR_PROCESSO_LICITATORIO",
        "tvPrincipal:tvMaisFiltros:j_idt67": "",
        "tvPrincipal:tvMaisFiltros:j_idt69_input": "",
        "tvPrincipal:tvMaisFiltros:j_idt69_hinput": "",
        "tvPrincipal:tvMaisFiltros:status2_focus": "",
        "tvPrincipal:tvMaisFiltros:status2_input": "0",
        "tvPrincipal:tvMaisFiltros:regimeJuridico_focus": "",
        "tvPrincipal:tvMaisFiltros:regimeJuridico_input": "",
        "tvPrincipal:tvMaisFiltros:mod_focus": "",
        "tvPrincipal:tvMaisFiltros:mod_input": "",
        "tvPrincipal:tvMaisFiltros:procedContratacao_focus": "",
        "tvPrincipal:tvMaisFiltros:procedContratacao_input": "",
        "tvPrincipal:tvMaisFiltros:meEpp_focus": "",
        "tvPrincipal:tvMaisFiltros:meEpp_input": "",
        "tvPrincipal:tvMaisFiltros:tipoLic_focus": "",
        "tvPrincipal:tvMaisFiltros:tipoLic_input": "",
        "tvPrincipal:tvMaisFiltros:fr_focus": "",
        "tvPrincipal:tvMaisFiltros:fr_input": "",
        "tvPrincipal:tvMaisFiltros:srp_focus": "",
        "tvPrincipal:tvMaisFiltros:srp_input": "",
        "tvPrincipal:tvMaisFiltros_activeIndex": "0",
        "tvPrincipal_activeIndex": "0",
        "javax.faces.ViewState": view_state,
    }
    return urlencode(data).encode("utf-8")


def _payload_exportar(view_state: str) -> bytes:
    from urllib.parse import urlencode
    data = {
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": "formListaLic:listaLic:j_idt290",
        "javax.faces.partial.execute": "@all",
        "formListaLic:listaLic:j_idt290": "formListaLic:listaLic:j_idt290",
        "formListaLic": "formListaLic",
        "formListaLic:listaLic_reflowDD": "0_0",
        "formListaLic:listaLic_rppDD": "8",
        "javax.faces.ViewState": view_state,
    }
    return urlencode(data).encode("utf-8")


# ── processamento do Excel ────────────────────────────────────────────────────

def _processar_excel(xlsx_bytes: bytes, palavras_chave: list[str] | None) -> list[EditalRaw]:
    editais: list[EditalRaw] = []
    try:
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb.active
        # Linha 1 = cabeçalho, dados a partir da linha 2
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
        # dt_abert, valor, status, dt_ult_public, dt_adjud, dt_homolog,
        # dt_final, dt_cadastro, dt_ult_atual, link
        if not row or len(row) < 13:
            return None
        orgao = str(row[0] or "").strip()
        nr_proc_tce = str(row[2] or "").strip()   # ex: LW-007256/26
        nr_procedimento = str(row[3] or "").strip()  # ex: Pregão nº PE 90058/2026
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
