from datetime import datetime
from uuid import UUID

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import LIMITE_MENSAGEM_SOS
from app.db.base import Base

UUID_GERADO = text("gen_random_uuid()")


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        Index("uq_usuarios_email_minusculo", func.lower(text("email")), unique=True),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=UUID_GERADO)
    nome_completo: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(150))
    senha_hash: Mapped[str] = mapped_column(String(255))
    telefone_pessoal: Mapped[str] = mapped_column(String(20))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ContatoEmergencia(Base):
    __tablename__ = "contatos_emergencia"
    __table_args__ = (
        CheckConstraint(
            r"telefone_whatsapp ~ '^\+[1-9][0-9]{7,14}$'", name="ck_contatos_telefone_e164"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=UUID_GERADO)
    usuario_id: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    nome: Mapped[str] = mapped_column(String(100))
    telefone_whatsapp: Mapped[str] = mapped_column(String(20))
    ativo: Mapped[bool] = mapped_column(server_default=true())
    consentido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AlertaSos(Base):
    __tablename__ = "alertas_sos"
    __table_args__ = (
        CheckConstraint(
            "status_envio IN ('PENDENTE', 'ENVIADO', 'ERRO')", name="ck_alertas_status_envio"
        ),
        CheckConstraint("tentativas >= 0", name="ck_alertas_tentativas_nao_negativas"),
        Index("ix_alertas_sos_localizacao", "localizacao", postgresql_using="gist"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=UUID_GERADO)
    usuario_id: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    localizacao: Mapped[WKBElement] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False)
    )
    mensagem: Mapped[str | None] = mapped_column(String(LIMITE_MENSAGEM_SOS))
    status_envio: Mapped[str] = mapped_column(String(20), server_default="PENDENTE")
    tentativas: Mapped[int] = mapped_column(server_default="0")
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TentativaEnvioSos(Base):
    __tablename__ = "tentativas_envio_sos"
    __table_args__ = (
        CheckConstraint(
            "numero_tentativa BETWEEN 1 AND 5", name="ck_tentativas_numero_de_1_a_5"
        ),
        CheckConstraint("status IN ('SUCESSO', 'FALHOU')", name="ck_tentativas_status"),
        UniqueConstraint(
            "alerta_id", "contato_id", "numero_tentativa", name="uq_tentativas_alerta_contato_numero"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=UUID_GERADO)
    alerta_id: Mapped[UUID] = mapped_column(
        ForeignKey("alertas_sos.id", ondelete="CASCADE"), index=True
    )
    contato_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("contatos_emergencia.id", ondelete="SET NULL")
    )
    numero_tentativa: Mapped[int]
    status: Mapped[str] = mapped_column(String(10))
    erro_codigo: Mapped[str | None] = mapped_column(String(50))
    executado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
