"""
Extrator de texto de PDFs de editais.

Pipeline:
  1. Tenta extração nativa de texto com pdfplumber (PDFs digitais).
  2. Se a página não contiver texto suficiente (PDF escaneado/imagem),
     converte para imagem e aplica OCR via pytesseract (primário) ou
     easyocr (fallback).
  3. Aplica Regex para extrair campos estruturados do texto bruto.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Limiar mínimo de caracteres por página para considerar PDF digital
MIN_CHARS_POR_PAGINA = 100


@dataclass
class EditalExtraido:
    texto_completo: str
    valor_estimado: float | None
    exclusivo_me: bool
    data_sessao: datetime | None
    modalidade_detectada: str | None


# ── extração de texto ────────────────────────────────────────────────────────

async def processar_pdf(caminho: Path) -> EditalExtraido:
    """
    Ponto de entrada assíncrono. Delega para thread pool para não bloquear
    o event loop durante I/O pesado de PDF/OCR.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _processar_pdf_sync, caminho)


def _processar_pdf_sync(caminho: Path) -> EditalExtraido:
    if not caminho.exists():
        raise FileNotFoundError(f"PDF não encontrado: {caminho}")

    texto = _extrair_texto_pdfplumber(caminho)

    if not texto or len(texto.strip()) < MIN_CHARS_POR_PAGINA * 2:
        logger.info("PDF parece escaneado, aplicando OCR: %s", caminho.name)
        texto = _extrair_texto_ocr(caminho)

    return EditalExtraido(
        texto_completo=texto,
        valor_estimado=_extrair_valor(texto),
        exclusivo_me=_detectar_exclusivo_me(texto),
        data_sessao=_extrair_data_sessao(texto),
        modalidade_detectada=_detectar_modalidade(texto),
    )


def _extrair_texto_pdfplumber(caminho: Path) -> str:
    try:
        import pdfplumber

        partes: list[str] = []
        with pdfplumber.open(caminho) as pdf:
            for numero, pagina in enumerate(pdf.pages, start=1):
                texto_pagina = pagina.extract_text() or ""
                partes.append(texto_pagina)
                logger.debug("Página %d: %d chars extraídos", numero, len(texto_pagina))

        return "\n".join(partes)
    except Exception as exc:
        logger.warning("pdfplumber falhou (%s), tentando OCR", exc)
        return ""


def _extrair_texto_ocr(caminho: Path) -> str:
    texto = _ocr_pytesseract(caminho)
    if not texto or len(texto.strip()) < 50:
        texto = _ocr_easyocr(caminho)
    return texto


def _ocr_pytesseract(caminho: Path) -> str:
    try:
        import pytesseract
        from pdf2image import convert_from_path
        from PIL import Image

        from config import settings

        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

        imagens: list[Image.Image] = convert_from_path(
            caminho, dpi=300, fmt="png", thread_count=2
        )

        partes: list[str] = []
        for i, img in enumerate(imagens, start=1):
            texto = pytesseract.image_to_string(img, lang="por", config="--psm 6")
            partes.append(texto)
            logger.debug("OCR pytesseract — página %d: %d chars", i, len(texto))

        return "\n".join(partes)

    except ImportError:
        logger.warning("pytesseract ou pdf2image não instalados")
        return ""
    except Exception as exc:
        logger.warning("pytesseract falhou: %s", exc)
        return ""


def _ocr_easyocr(caminho: Path) -> str:
    try:
        import easyocr
        from pdf2image import convert_from_path

        imagens = convert_from_path(caminho, dpi=200, fmt="png")
        reader = easyocr.Reader(["pt"], gpu=False, verbose=False)

        partes: list[str] = []
        for i, img in enumerate(imagens, start=1):
            import numpy as np

            resultado = reader.readtext(np.array(img), detail=0, paragraph=True)
            texto = " ".join(resultado)
            partes.append(texto)
            logger.debug("OCR easyocr — página %d: %d chars", i, len(texto))

        return "\n".join(partes)

    except ImportError:
        logger.warning("easyocr não instalado")
        return ""
    except Exception as exc:
        logger.warning("easyocr falhou: %s", exc)
        return ""


# ── extração por Regex ────────────────────────────────────────────────────────

# Padrões para valor estimado — cobre formatos comuns em editais brasileiros:
#   R$ 1.234.567,89 | R$1234567.89 | valor estimado: 450.000,00
_RE_VALOR = re.compile(
    r"(?:valor\s+(?:total\s+)?(?:estimado|m[áa]ximo|global)[:\s]*)"
    r"R?\$?\s*([\d]{1,3}(?:[.,][\d]{3})*(?:[.,]\d{2})?)",
    re.IGNORECASE | re.MULTILINE,
)

_RE_ME_EPP = re.compile(
    r"(cota\s+reservada|exclusiv[ao]\s+(?:para\s+)?ME|"
    r"microempresa|empresa\s+de\s+pequeno\s+porte|ME/EPP)",
    re.IGNORECASE,
)

# Data no formato "dd/mm/aaaa às HH:MM" ou "dd de mês de aaaa"
_RE_DATA_SESSAO = re.compile(
    r"(?:data\s+da\s+sess[aã]o|abertura\s+das\s+propostas?|"
    r"data\s+(?:e\s+hor[aá]rio\s+)?da\s+licitaç[aã]o)[:\s]*"
    r"(\d{2}[/.-]\d{2}[/.-]\d{4})"
    r"(?:\s*[àas]+\s*(\d{2}[h:]\d{2}))?",
    re.IGNORECASE | re.MULTILINE,
)

_RE_MODALIDADE = re.compile(
    r"(preg[aã]o\s+eletr[oô]nico|preg[aã]o\s+presencial|"
    r"concorr[eê]ncia(?:\s+eletr[oô]nica)?|"
    r"dispensa\s+de\s+licitaç[aã]o|"
    r"chamamento\s+p[uú]blico|"
    r"credenciamento)",
    re.IGNORECASE,
)

_MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}


def _extrair_valor(texto: str) -> float | None:
    match = _RE_VALOR.search(texto)
    if not match:
        return None
    raw = match.group(1).strip()
    # Normaliza separadores: "1.234.567,89" → 1234567.89
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _detectar_exclusivo_me(texto: str) -> bool:
    return bool(_RE_ME_EPP.search(texto))


def _extrair_data_sessao(texto: str) -> datetime | None:
    match = _RE_DATA_SESSAO.search(texto)
    if not match:
        return None

    data_str = match.group(1)
    hora_str = match.group(2) if match.lastindex and match.lastindex >= 2 else None

    for sep in ["/", ".", "-"]:
        partes = data_str.split(sep)
        if len(partes) == 3:
            try:
                dia, mes, ano = int(partes[0]), int(partes[1]), int(partes[2])
                if hora_str:
                    hora_str = hora_str.replace("h", ":").replace("H", ":")
                    h, m = hora_str.split(":")
                    return datetime(ano, mes, dia, int(h), int(m))
                return datetime(ano, mes, dia)
            except (ValueError, IndexError):
                continue
    return None


def _detectar_modalidade(texto: str) -> str | None:
    match = _RE_MODALIDADE.search(texto)
    if match:
        return " ".join(match.group(0).split()).title()
    return None
