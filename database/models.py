import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database.engine import Base


class EditalStatus(str, enum.Enum):
    PUBLICADO = "publicado"
    ABERTO = "aberto"
    EM_ANDAMENTO = "em_andamento"
    DISPUTA_ABERTA = "disputa_aberta"
    HOMOLOGADO = "homologado"
    CANCELADO = "cancelado"
    ENCERRADO = "encerrado"


class Edital(Base):
    __tablename__ = "editais"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    numero_controle: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    orgao: Mapped[str] = mapped_column(String(300))
    uasg: Mapped[str | None] = mapped_column(String(20), nullable=True)
    objeto: Mapped[str] = mapped_column(Text)
    modalidade: Mapped[str] = mapped_column(String(80))
    valor_estimado: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_abertura: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_encerramento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    link_edital: Mapped[str | None] = mapped_column(Text, nullable=True)
    link_pdf: Mapped[str | None] = mapped_column(Text, nullable=True)
    exclusivo_me: Mapped[bool] = mapped_column(Boolean, default=False)
    estado: Mapped[str | None] = mapped_column(String(2), nullable=True)
    municipio: Mapped[str | None] = mapped_column(String(150), nullable=True)
    status: Mapped[EditalStatus] = mapped_column(
        Enum(EditalStatus), default=EditalStatus.PUBLICADO, index=True
    )
    texto_extraido: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AlertaMonitoramento(Base):
    __tablename__ = "alertas_monitoramento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    edital_id: Mapped[int] = mapped_column(Integer, index=True)
    dispositivo_token: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    iniciado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finalizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_encontrados: Mapped[int] = mapped_column(Integer, default=0)
    total_novos: Mapped[int] = mapped_column(Integer, default=0)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="em_andamento")
