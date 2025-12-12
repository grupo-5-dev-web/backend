from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.booking import BookingStatus


class RecurringPattern(BaseModel):
    """Padrão de recorrência para reservas repetitivas."""
    frequency: str = Field(pattern="^(daily|weekly|monthly)$", description="Frequência da recorrência: daily, weekly ou monthly", examples=["weekly"])
    interval: int = Field(ge=1, le=52, default=1, description="Intervalo entre ocorrências (ex: a cada 2 semanas)", examples=[1])
    end_date: Optional[datetime] = Field(default=None, description="Data final da recorrência", examples=["2025-12-31T23:59:59Z"])
    days_of_week: Optional[list[int]] = Field(default=None, description="Dias da semana para recorrência semanal (0=Segunda, 6=Domingo)", examples=[[0, 2, 4]])

    @field_validator("days_of_week")
    @classmethod
    def validar_dias_semana(cls, value, info):
        if value is None:
            return value
        if not all(0 <= day <= 6 for day in value):
            raise ValueError("days_of_week deve conter valores de 0 a 6")
        return value


class BookingBase(BaseModel):
    """Schema base para reservas."""
    tenant_id: UUID = Field(description="ID do tenant (organização)", examples=["550e8400-e29b-41d4-a716-446655440000"])
    resource_id: UUID = Field(description="ID do recurso a ser reservado", examples=["660e8400-e29b-41d4-a716-446655440001"])
    user_id: UUID = Field(description="ID do usuário responsável pela reserva", examples=["770e8400-e29b-41d4-a716-446655440002"])
    client_id: Optional[UUID] = Field(default=None, description="ID do cliente/beneficiário da reserva (pode ser diferente do user_id)", examples=["880e8400-e29b-41d4-a716-446655440003"])
    start_time: datetime = Field(description="Data/hora de início da reserva no formato ISO 8601 com timezone (ex: 2025-12-05T14:00:00-03:00 ou 2025-12-05T17:00:00Z). IMPORTANTE: se enviar sem timezone, será interpretado como UTC.", examples=["2025-12-15T14:00:00-03:00"])
    end_time: datetime = Field(description="Data/hora de término da reserva no formato ISO 8601 com timezone (ex: 2025-12-05T15:00:00-03:00 ou 2025-12-05T18:00:00Z). IMPORTANTE: se enviar sem timezone, será interpretado como UTC.", examples=["2025-12-15T15:00:00-03:00"])
    notes: Optional[str] = Field(default=None, description="Observações sobre a reserva", examples=["Reunião de planejamento trimestral"])
    recurring_enabled: bool = Field(default=False, description="Se true, cria reservas recorrentes", examples=[False])
    recurring_pattern: Optional[RecurringPattern] = Field(default=None, description="Padrão de recorrência (obrigatório se recurring_enabled=true)")
    
    @field_validator("recurring_pattern")
    @classmethod
    def validate_recurring_pattern(cls, value, info):
        """Valida que recurring_pattern está presente se recurring_enabled é True."""
        recurring_enabled = info.data.get("recurring_enabled", False)
        if recurring_enabled and value is None:
            raise ValueError("recurring_pattern é obrigatório quando recurring_enabled é True")
        return value

    @field_validator("start_time", "end_time")
    @classmethod
    def ensure_timezone_aware(cls, value: datetime) -> datetime:
        """Garante que datetime sempre tem timezone. Se não tiver, assume UTC."""
        if value.tzinfo is None:
            from datetime import timezone
            value = value.replace(tzinfo=timezone.utc)
        return value

    @field_validator("end_time")
    @classmethod
    def validar_intervalo(cls, end_time, info):
        start_time = info.data.get("start_time")
        if start_time and end_time <= start_time:
            raise ValueError("end_time deve ser maior que start_time")
        return end_time


class BookingCreate(BookingBase):
    """Schema para criação de nova reserva. Valida regras de antecedência, horário comercial e conflitos."""
    status: Optional[str] = Field(default=BookingStatus.CONFIRMED, description="Status inicial da reserva (pendente, confirmado, cancelado)")

    @field_validator("status")
    @classmethod
    def validar_status(cls, value):
        if value not in BookingStatus.ALL:
            raise ValueError("Status inválido")
        return value


class BookingUpdate(BaseModel):
    """Schema para atualização parcial de reserva existente."""
    resource_id: Optional[UUID] = Field(default=None, description="Novo recurso (validará conflitos)")
    client_id: Optional[UUID] = Field(default=None, description="Atualizar cliente/beneficiário")
    start_time: Optional[datetime] = Field(default=None, description="Nova data/hora de início")
    end_time: Optional[datetime] = Field(default=None, description="Nova data/hora de término")
    notes: Optional[str] = Field(default=None, description="Atualizar observações")
    status: Optional[str] = Field(default=None, description="Atualizar status da reserva")
    recurring_enabled: Optional[bool] = Field(default=None, description="Habilitar/desabilitar recorrência")
    recurring_pattern: Optional[RecurringPattern] = Field(default=None, description="Atualizar padrão de recorrência")

    @field_validator("status")
    @classmethod
    def validar_status(cls, value):
        if value and value not in BookingStatus.ALL:
            raise ValueError("Status inválido")
        return value

    @field_validator("end_time")
    @classmethod
    def validar_intervalo(cls, end_time, info):
        start_time = info.data.get("start_time")
        if start_time and end_time and end_time <= start_time:
            raise ValueError("end_time deve ser maior que start_time")
        return end_time


class BookingOut(BaseModel):
    """Representação completa de uma reserva com todos os campos."""
    id: UUID = Field(description="ID único da reserva")
    tenant_id: UUID = Field(description="ID do tenant")
    resource_id: UUID = Field(description="ID do recurso reservado")
    user_id: UUID = Field(description="ID do usuário que criou a reserva")
    client_id: Optional[UUID] = Field(description="ID do cliente/beneficiário")
    start_time: datetime = Field(description="Data/hora de início")
    end_time: datetime = Field(description="Data/hora de término")
    status: str = Field(description="Status atual: pendente, confirmado, cancelado, concluido")
    notes: Optional[str] = Field(description="Observações da reserva")
    confirmation_code: Optional[str] = Field(description="Código de confirmação único")
    recurring_enabled: bool = Field(description="Se é uma reserva recorrente")
    recurring_pattern: Optional[Dict[str, Any]] = Field(description="Padrão de recorrência aplicado")
    cancellation_reason: Optional[str] = Field(description="Motivo do cancelamento")
    cancelled_at: Optional[datetime] = Field(description="Data/hora do cancelamento")
    cancelled_by: Optional[UUID] = Field(description="ID do usuário que cancelou")
    created_at: datetime = Field(description="Data/hora de criação do registro")
    updated_at: datetime = Field(description="Data/hora da última atualização")

    model_config = ConfigDict(from_attributes=True)


class BookingCancelRequest(BaseModel):
    """Requisição de cancelamento de reserva."""
    reason: Optional[str] = Field(default=None, max_length=500, description="Motivo do cancelamento (opcional)")


class BookingConflict(BaseModel):
    """Representa uma reserva conflitante."""
    booking_id: UUID = Field(description="ID da reserva conflitante")
    start_time: datetime = Field(description="Início da reserva conflitante")
    end_time: datetime = Field(description="Término da reserva conflitante")


class BookingConflictResponse(BaseModel):
    """Resposta de erro quando há conflito de horário (HTTP 409)."""
    success: bool = Field(description="Sempre false para conflitos")
    error: str = Field(description="Tipo do erro: 'conflict'")
    message: str = Field(description="Mensagem descritiva do conflito")
    conflicts: list[BookingConflict] = Field(description="Lista de reservas conflitantes")


class BookingWithPolicy(BookingOut):
    """BookingOut estendido com informações de política de cancelamento."""
    can_cancel: bool = Field(description="Se a reserva pode ser cancelada baseado na janela de cancelamento do tenant")