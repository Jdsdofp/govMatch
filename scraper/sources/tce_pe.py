"""Fonte TCE-PE — sistemas.tcepe.tc.br/DadosAbertos (Struts2 JSON API).

Endpoint: GET /DadosAbertos/LicitacoesDetalhes!json
Retorna até 100.000 licitações em uma única chamada, encoding ISO-8859-1.
Sem autenticação, sem paginação (resposta completa de uma vez).
"""
import json
import logging
from datetime import datetime

import httpx

from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)

_URL = "https://sistemas.tcepe.tc.br/DadosAbertos/LicitacoesDetalhes!json"
_HEADERS = {
    "Accept": "*/*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


class TCEPESource(BaseSource):
    source_id = "tce_pe"
    interval_seconds = 86400  # 24h — payload grande (~100k registros), sem filtro de data

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "PE":
            return []

        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=120, follow_redirects=True, verify=False) as c:
                r = await c.get(_URL)
                if r.status_code != 200:
                    logger.warning("[TCE-PE] HTTP %d", r.status_code)
                    return []
                # A API retorna ISO-8859-1 mas informa charset errado — decode manual
                text = r.content.decode("iso-8859-1")
                d = json.loads(text)
        except Exception as exc:
            logger.error("[TCE-PE] Erro ao buscar: %s", exc)
            return []

        itens = d.get("resposta", {}).get("conteudo", [])
        editais: list[EditalRaw] = []
        for item in itens:
            edital = _mapear(item)
            if edital is None:
                continue
            if palavras_chave:
                texto = f"{edital.objeto} {edital.orgao}".lower()
                if not all(p.lower() in texto for p in palavras_chave):
                    continue
            editais.append(edital)

        logger.info("[TCE-PE] %d editais encontrados", len(editais))
        return editais

    async def testar_conexao(self) -> bool:
        try:
            # stream para não baixar os 100k registros só para checar conexão
            async with httpx.AsyncClient(headers=_HEADERS, timeout=15, verify=False) as c:
                async with c.stream("GET", _URL) as r:
                    return r.status_code == 200
        except Exception:
            return False


def _mapear(item: dict) -> EditalRaw | None:
    try:
        cod_ug = str(item.get("CODIGOUG") or "").strip()
        modalidade = str(item.get("CODIGOMODALIDADE") or "").strip()
        numero = str(item.get("NUMEROMODALIDADE") or "").strip()
        ano = str(item.get("ANOMODALIDADE") or "").strip()
        if not cod_ug or not numero:
            return None
        numero_controle = f"tce_pe:{cod_ug}:{modalidade}:{ano}:{numero}"
        orgao = (item.get("UG") or "").strip()
        objeto = (
            item.get("OBJETOCONFORMEEDITAL")
            or item.get("ESPECIFICACAOOBJETO")
            or item.get("DESCRICAOOBJETO")
            or ""
        ).strip()
        nome_modalidade = (item.get("NOMEMODALIDADE") or "").strip()
        valor = _parse_float(item.get("VALORORCAMENTOESTIMATIVO") or item.get("TOTALADJUDICADOLICITACAO"))
        data_abertura = _parse_data(item.get("DATAEMISSAOEDITAL"))
        data_enc = _parse_data(item.get("DATAPUBLICACAOHOMOLOGACAO"))
        link = item.get("LinkArquivo") or None
        return EditalRaw(
            numero_controle=numero_controle,
            orgao=orgao,
            objeto=objeto,
            modalidade=nome_modalidade,
            valor_estimado=valor,
            data_abertura=data_abertura,
            data_encerramento=data_enc,
            link_edital=link,
            exclusivo_me=False,
            estado="PE",
            fonte="tce_pe",
        )
    except Exception as exc:
        logger.debug("[TCE-PE] Erro ao mapear: %s", exc)
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
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None
