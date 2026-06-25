"""Fonte TCE-RN — apidadosabertos.tce.rn.gov.br (API REST com Swagger).

Estratégia:
  1. Busca todas as 915 unidades jurisdicionadas via /JurisdicionadosTCE/json
  2. Para cada unidade, busca licitações dos últimos 30 dias via /LicitacaoPublica/json
  3. Filtra e mapeia para EditalRaw

Sem autenticação, sem CAPTCHA. Documentação: apidadosabertos.tce.rn.gov.br/swagger/ui/index
"""
import asyncio
import logging
from datetime import datetime, timedelta

import httpx

from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)

_BASE = "https://apidadosabertos.tce.rn.gov.br/api"
_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}
_DIAS_RETROATIVOS = 30
_MAX_UNIDADES = 50  # cobre os maiores municípios sem timeout no scheduler


class TCERNSource(BaseSource):
    source_id = "tce_rn"
    interval_seconds = 21600  # 6 horas

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "RN":
            return []

        unidades = await self._buscar_unidades()
        if not unidades:
            logger.warning("[TCE-RN] Nenhuma unidade encontrada")
            return []

        hoje = datetime.now()
        data_fim = hoje.strftime("%Y-%m-%d")
        data_ini = (hoje - timedelta(days=_DIAS_RETROATIVOS)).strftime("%Y-%m-%d")

        editais: list[EditalRaw] = []
        semaphore = asyncio.Semaphore(5)

        async def buscar_unidade(unidade: dict) -> list[EditalRaw]:
            uid = unidade["identificadorUnidade"]
            nome = unidade["nomeOrgao"]
            async with semaphore:
                try:
                    async with httpx.AsyncClient(headers=_HEADERS, timeout=20, follow_redirects=True) as c:
                        url = f"{_BASE}/ProcedimentosLicitatoriosApi/LicitacaoPublica/json/{uid}/{data_ini}/{data_fim}"
                        r = await c.get(url)
                        if r.status_code != 200 or not r.text.strip():
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
                    logger.debug("[TCE-RN] Erro unidade %d: %s", uid, exc)
                    return []

        tarefas = [buscar_unidade(u) for u in unidades[:_MAX_UNIDADES]]
        resultados = await asyncio.gather(*tarefas, return_exceptions=True)
        for res in resultados:
            if isinstance(res, list):
                editais.extend(res)

        logger.info("[TCE-RN] %d editais de %d unidades", len(editais), min(len(unidades), _MAX_UNIDADES))
        return editais

    async def _buscar_unidades(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=20, follow_redirects=True) as c:
                r = await c.get(f"{_BASE}/InformacoesBasicasApi/JurisdicionadosTCE/json")
                if r.status_code == 200:
                    return r.json() or []
        except Exception as exc:
            logger.error("[TCE-RN] Erro ao buscar unidades: %s", exc)
        return []

    async def testar_conexao(self) -> bool:
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=10) as c:
                r = await c.get(f"{_BASE}/InformacoesBasicasApi/JurisdicionadosTCE/json")
                return r.status_code == 200
        except Exception:
            return False


def _mapear(item: dict, orgao_fallback: str) -> EditalRaw | None:
    try:
        nr = str(item.get("numeroLicitacao") or "").strip()
        ano = str(item.get("anoLicitacao") or "").strip()
        cod = str(item.get("codigoJurisdicionado") or "").strip()
        if not nr:
            return None
        numero_controle = f"tce_rn:{cod}:{ano}:{nr}"
        orgao = (item.get("nomeJurisdicionado") or orgao_fallback or "").strip()
        objeto = (item.get("descricaoObjeto") or item.get("descricaoLote") or "").strip()
        modalidade = (item.get("modalidade") or item.get("tipoObjeto") or "").strip()
        valor = _parse_float(item.get("valorTotalOrcado") or item.get("valorReferencia"))
        data_abertura = _parse_data(item.get("dataAberturaRecebimento") or item.get("dataDisponibilizacaoInicial"))
        data_enc = _parse_data(item.get("dataRecebimentoFinal") or item.get("dataDisponibilizacaoFinal"))
        return EditalRaw(
            numero_controle=numero_controle,
            orgao=orgao,
            objeto=objeto,
            modalidade=modalidade,
            valor_estimado=valor,
            data_abertura=data_abertura,
            data_encerramento=data_enc,
            link_edital=item.get("linkEdital") or None,
            exclusivo_me=False,
            estado="RN",
            fonte="tce_rn",
        )
    except Exception as exc:
        logger.debug("[TCE-RN] Erro ao mapear: %s", exc)
        return None


def _parse_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).replace(".", "").replace(",", "."))
    except (ValueError, TypeError):
        return None


def _parse_data(raw: str | None) -> datetime | None:
    if not raw:
        return None
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip()[:19], fmt)
        except ValueError:
            continue
    return None
