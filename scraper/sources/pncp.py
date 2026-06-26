"""Fonte PNCP — API REST pública via httpx, busca paralela por UF."""
import asyncio
import logging
from datetime import date, datetime, timedelta

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)

PNCP_API_BASE = "https://pncp.gov.br/api/consulta/v1"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# Modalidades válidas na nova API (2 = Diálogo Competitivo retorna 204)
MODALIDADES = [1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]


class PNCPSource(BaseSource):
    source_id = "pncp"
    interval_seconds = 3600  # 1 hora

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
        max_paginas: int = 5,
    ) -> list[EditalRaw]:
        # Processa modalidades sequencialmente para não estourar o rate limit da PNCP
        editais: list[EditalRaw] = []
        for i, mod in enumerate(MODALIDADES):
            try:
                res = await self._buscar_modalidade(mod, palavras_chave, estado, max_paginas)
                editais.extend(res)
            except Exception as exc:
                logger.error("[PNCP] Erro modalidade=%d: %s", mod, exc)
            if i < len(MODALIDADES) - 1:
                await asyncio.sleep(1.5)

        logger.info("[PNCP] Total: %d editais", len(editais))
        return editais

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
    async def _buscar_modalidade(
        self,
        modalidade: int,
        palavras_chave: list[str] | None,
        estado: str | None,
        max_paginas: int = 5,
    ) -> list[EditalRaw]:
        resultados: list[EditalRaw] = []
        hoje = date.today()
        data_fim = hoje.strftime("%Y%m%d")
        data_ini = (hoje - timedelta(days=30)).strftime("%Y%m%d")

        async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            for pagina in range(1, max_paginas + 1):
                params = {
                    "codigoModalidadeContratacao": modalidade,
                    "dataInicial": data_ini,
                    "dataFinal": data_fim,
                    "pagina": pagina,
                    "tamanhoPagina": 20,
                }
                try:
                    resp = await client.get(
                        f"{PNCP_API_BASE}/contratacoes/publicacao", params=params
                    )
                except Exception as exc:
                    logger.error("[PNCP/mod=%d] Erro de rede pág %d: %s", modalidade, pagina, exc)
                    break

                if resp.status_code in (204, 404):
                    break
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", "10"))
                    logger.warning("[PNCP/mod=%d] 429 pág %d — aguardando %ds", modalidade, pagina, retry_after)
                    await asyncio.sleep(retry_after)
                    continue
                if resp.status_code != 200:
                    logger.warning("[PNCP/mod=%d] Status %d pág %d", modalidade, resp.status_code, pagina)
                    break

                try:
                    dados = resp.json()
                except Exception:
                    break

                itens = dados.get("data", [])
                if not itens:
                    break

                for item in itens:
                    # Filtra por UF no response (nova API não tem parâmetro uf)
                    if estado:
                        uf_item = item.get("unidadeOrgao", {}).get("ufSigla", "")
                        if uf_item.upper() != estado.upper():
                            continue

                    edital = _mapear_item_pncp(item)
                    if edital is None:
                        continue
                    if palavras_chave:
                        texto = f"{edital.objeto} {edital.orgao}".lower()
                        if not all(p.lower() in texto for p in palavras_chave):
                            continue
                    resultados.append(edital)

                total_paginas = dados.get("totalPaginas", pagina)
                if pagina >= total_paginas:
                    break

                await asyncio.sleep(0.3)

        return resultados

    async def testar_conexao(self) -> bool:
        try:
            hoje = date.today()
            async with httpx.AsyncClient(headers=HEADERS, timeout=10) as client:
                r = await client.get(
                    f"{PNCP_API_BASE}/contratacoes/publicacao",
                    params={
                        "codigoModalidadeContratacao": 8,
                        "dataInicial": (hoje - timedelta(days=1)).strftime("%Y%m%d"),
                        "dataFinal": hoje.strftime("%Y%m%d"),
                        "pagina": 1,
                        "tamanhoPagina": 10,
                    },
                )
                return r.status_code < 500
        except Exception:
            return False


def _mapear_item_pncp(item: dict) -> EditalRaw | None:
    try:
        return EditalRaw(
            numero_controle=item.get("numeroControlePNCP") or f"pncp:{item.get('sequencialCompra', '')}",
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
            fonte="pncp",
        )
    except Exception as exc:
        logger.warning("[PNCP] Erro ao mapear item: %s", exc)
        return None


def _parse_valor(raw) -> float | None:
    if raw is None:
        return None
    try:
        # Se já é numérico (int/float), retorna diretamente
        if isinstance(raw, (int, float)):
            return float(raw)
        # String no formato brasileiro: "1.234,56" → 1234.56
        s = str(raw)
        if "," in s:
            return float(s.replace(".", "").replace(",", "."))
        return float(s)
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
