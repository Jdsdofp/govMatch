from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EditalSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    numero_controle: str
    orgao: str
    uasg: str | None
    objeto: str
    modalidade: str
    valor_estimado: float | None
    data_abertura: datetime | None
    data_encerramento: datetime | None
    link_edital: str | None
    exclusivo_me: bool
    estado: str | None
    municipio: str | None
    status: str
    criado_em: datetime


class EditalListaSchema(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    dados: list[EditalSchema]


class SyncResponseSchema(BaseModel):
    mensagem: str
    job_id: str | None = None


class SyncResultadoSchema(BaseModel):
    total_encontrados: int
    total_novos: int
    status: str
    erro: str | None = None


class AlertaRequestSchema(BaseModel):
    dispositivo_token: str | None = Field(
        default=None,
        description="Token FCM/APNs para envio de push notification",
    )


class AlertaResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    edital_id: int
    ativo: bool
    criado_em: datetime


class ErroSchema(BaseModel):
    detalhe: str
    codigo: str | None = None
