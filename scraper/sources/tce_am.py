"""Fonte TCE-AM — econtasapi.tce.am.gov.br (OpenAPI 3.0, dados abertos).

Estratégia:
  1. Busca 466 unidades gestoras via /transparencia/dados-abertos/unidades
  2. Para cada unidade, busca licitações do ano atual e anterior
  3. Semáforo de 10 workers concorrentes
  Sem autenticação para endpoints /transparencia/dados-abertos/*.
"""
import asyncio
import logging
from datetime import datetime

import httpx

from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)

_BASE = "https://econtasapi.tce.am.gov.br/transparencia/dados-abertos"
_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}
_MAX_WORKERS = 10


class TCEAMSource(BaseSource):
    source_id = "tce_am"
    interval_seconds = 86400  # 24h — 466 unidades × 2 anos

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "AM":
            return []

        unidades = await self._buscar_unidades()
        if not unidades:
            logger.warning("[TCE-AM] Nenhuma unidade encontrada")
            return []

        ano_atual = datetime.now().year
        anos = [ano_atual, ano_atual - 1]
        semaphore = asyncio.Semaphore(_MAX_WORKERS)
        editais: list[EditalRaw] = []

        async def buscar_unidade_ano(uid: int, nome: str, ano: int) -> list[EditalRaw]:
            async with semaphore:
                try:
                    async with httpx.AsyncClient(headers=_HEADERS, timeout=20, follow_redirects=True) as c:
                        r = await c.get(f"{_BASE}/licitacoes/{uid}/{ano}")
                        if r.status_code != 200:
                            return []
                        itens = r.json()
                        resultado = []
                        for item in (itens if isinstance(itens, list) else []):
                            edital = _mapear(item, nome)
                            if edital is None:
                                continue
                            if palavras_chave:
                                texto = f"{edital.objeto} {edital.orgao}".lower()
                                if not all(p.lower() in texto for p in palavras_chave):
                                    continue
                            resultado.append(edital)
                        return resultado
                except Exception as exc:
                    logger.debug("[TCE-AM] Erro uid=%d ano=%d: %s", uid, ano, exc)
                    return []

        tarefas = [
            buscar_unidade_ano(u["id_unidade_gestora"], u.get("nome", ""), ano)
            for u in unidades
            for ano in anos
        ]
        resultados = await asyncio.gather(*tarefas, return_exceptions=True)
        for res in resultados:
            if isinstance(res, list):
                editais.extend(res)

        logger.info("[TCE-AM] %d editais de %d unidades", len(editais), len(unidades))
        return editais

    async def _buscar_unidades(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=20, follow_redirects=True) as c:
                r = await c.get(f"{_BASE}/unidades")
                if r.status_code == 200:
                    return r.json() or []
        except Exception as exc:
            logger.error("[TCE-AM] Erro ao buscar unidades: %s", exc)
        return []

    async def testar_conexao(self) -> bool:
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=10) as c:
                r = await c.get(f"{_BASE}/unidades")
                return r.status_code == 200
        except Exception:
            return False


def _mapear(item: dict, orgao_fallback: str) -> EditalRaw | None:
    try:
        id_lic = str(item.get("idLicitacao") or "").strip()
        if not id_lic:
            return None
        uid = str(item.get("idUnidadeGestora") or "").strip()
        numero_controle = f"tce_am:{uid}:{id_lic}"
        orgao = (item.get("nomeUnidadeGestora") or orgao_fallback or "").strip()
        objeto = (item.get("descricaoObjeto") or "").strip()
        modalidade = (item.get("desTipoLicitacao") or item.get("descricao") or "").strip()
        valor = _parse_float(item.get("valorTotal"))
        data_abertura = _parse_data(item.get("dtPublicacaoEdital"))
        return EditalRaw(
            numero_controle=numero_controle,
            orgao=orgao,
            objeto=objeto,
            modalidade=modalidade,
            valor_estimado=valor,
            data_abertura=data_abertura,
            data_encerramento=None,
            link_edital=None,
            exclusivo_me=False,
            estado="AM",
            fonte="tce_am",
        )
    except Exception as exc:
        logger.debug("[TCE-AM] Erro ao mapear: %s", exc)
        return None


def _parse_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "."))
    except (ValueError, TypeError):
        return None


def _parse_data(raw) -> datetime | None:
    if not raw:
        return None
    raw = str(raw).strip()[:19]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None
