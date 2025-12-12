"""Testes para lógica de recorrência de bookings."""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from shared.recurring import (
    calculate_recurring_occurrences,
    get_next_occurrence,
    validate_recurring_pattern,
)


class TestCalculateRecurringOccurrences:
    """Testes para cálculo de ocorrências recorrentes."""

    def test_daily_recurrence_basic(self):
        """Testa recorrência diária básica."""
        start_time = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2025, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        pattern = {
            "frequency": "daily",
            "interval": 1,
            "end_date": datetime(2025, 1, 20, 23, 59, 59, tzinfo=timezone.utc),
        }
        
        occurrences = calculate_recurring_occurrences(start_time, end_time, pattern)
        
        # Deve criar 6 ocorrências (15, 16, 17, 18, 19, 20)
        assert len(occurrences) == 6
        assert occurrences[0]["start_time"] == start_time
        assert occurrences[1]["start_time"] == start_time + timedelta(days=1)
        assert occurrences[-1]["start_time"] == start_time + timedelta(days=5)

    def test_daily_recurrence_with_interval(self):
        """Testa recorrência diária com intervalo."""
        start_time = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2025, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        pattern = {
            "frequency": "daily",
            "interval": 2,  # A cada 2 dias
            "end_date": datetime(2025, 1, 25, 23, 59, 59, tzinfo=timezone.utc),
        }
        
        occurrences = calculate_recurring_occurrences(start_time, end_time, pattern)
        
        # Deve criar 6 ocorrências (15, 17, 19, 21, 23, 25)
        assert len(occurrences) == 6
        assert occurrences[0]["start_time"] == start_time
        assert occurrences[1]["start_time"] == start_time + timedelta(days=2)
        assert occurrences[-1]["start_time"] == start_time + timedelta(days=10)

    def test_weekly_recurrence_basic(self):
        """Testa recorrência semanal básica."""
        start_time = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)  # Quarta-feira
        end_time = datetime(2025, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        pattern = {
            "frequency": "weekly",
            "interval": 1,
            "end_date": datetime(2025, 2, 15, 23, 59, 59, tzinfo=timezone.utc),
        }
        
        occurrences = calculate_recurring_occurrences(start_time, end_time, pattern)
        
        # Deve criar ~5 ocorrências (15, 22, 29, 5, 12)
        assert len(occurrences) >= 4
        assert occurrences[0]["start_time"] == start_time
        assert occurrences[1]["start_time"] == start_time + timedelta(weeks=1)

    def test_weekly_recurrence_with_days_of_week(self):
        """Testa recorrência semanal com dias específicos."""
        start_time = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)  # Quarta-feira (2)
        end_time = datetime(2025, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        pattern = {
            "frequency": "weekly",
            "interval": 1,
            "days_of_week": [0, 2, 4],  # Segunda, Quarta, Sexta
            "end_date": datetime(2025, 1, 31, 23, 59, 59, tzinfo=timezone.utc),
        }
        
        occurrences = calculate_recurring_occurrences(start_time, end_time, pattern)
        
        # Deve criar múltiplas ocorrências nos dias especificados
        assert len(occurrences) >= 3
        # Verificar que todas são nos dias corretos (0, 2, 4)
        for occ in occurrences:
            weekday = occ["start_time"].weekday()
            assert weekday in [0, 2, 4]

    def test_monthly_recurrence_basic(self):
        """Testa recorrência mensal básica."""
        start_time = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2025, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        pattern = {
            "frequency": "monthly",
            "interval": 1,
            "end_date": datetime(2025, 4, 15, 23, 59, 59, tzinfo=timezone.utc),
        }
        
        occurrences = calculate_recurring_occurrences(start_time, end_time, pattern)
        
        # Deve criar 4 ocorrências (Jan, Fev, Mar, Abr)
        assert len(occurrences) == 4
        assert occurrences[0]["start_time"] == start_time
        assert occurrences[1]["start_time"].month == 2
        assert occurrences[-1]["start_time"].month == 4

    def test_recurrence_respects_end_date(self):
        """Testa que recorrência respeita end_date."""
        start_time = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2025, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        pattern = {
            "frequency": "daily",
            "interval": 1,
            "end_date": datetime(2025, 1, 17, 12, 0, 0, tzinfo=timezone.utc),  # Meio do dia 17
        }
        
        occurrences = calculate_recurring_occurrences(start_time, end_time, pattern)
        
        # Deve criar apenas 3 ocorrências (15, 16, 17) - não inclui 18 porque end_date é meio do dia 17
        assert len(occurrences) == 3
        assert all(occ["start_time"] <= pattern["end_date"] for occ in occurrences)

    def test_recurrence_without_end_date_creates_max_occurrences(self):
        """Testa que sem end_date cria número máximo de ocorrências."""
        start_time = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2025, 1, 15, 15, 0, 0, tzinfo=timezone.utc)
        pattern = {
            "frequency": "daily",
            "interval": 1,
            "end_date": None,
        }
        
        occurrences = calculate_recurring_occurrences(start_time, end_time, pattern)
        
        # Deve criar número máximo padrão (ex: 365 dias)
        assert len(occurrences) > 0
        assert len(occurrences) <= 365  # Limite razoável


class TestGetNextOccurrence:
    """Testes para cálculo da próxima ocorrência."""

    def test_daily_next_occurrence(self):
        """Testa próxima ocorrência diária."""
        current = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        pattern = {"frequency": "daily", "interval": 1}
        
        next_occ = get_next_occurrence(current, pattern)
        
        assert next_occ == current + timedelta(days=1)

    def test_weekly_next_occurrence(self):
        """Testa próxima ocorrência semanal."""
        current = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        pattern = {"frequency": "weekly", "interval": 1}
        
        next_occ = get_next_occurrence(current, pattern)
        
        assert next_occ == current + timedelta(weeks=1)

    def test_monthly_next_occurrence(self):
        """Testa próxima ocorrência mensal."""
        current = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        pattern = {"frequency": "monthly", "interval": 1}
        
        next_occ = get_next_occurrence(current, pattern)
        
        # Deve ser aproximadamente 1 mês depois
        assert next_occ.month == 2
        assert next_occ.day == 15


class TestValidateRecurringPattern:
    """Testes para validação de padrão de recorrência."""

    def test_validate_daily_pattern(self):
        """Testa validação de padrão diário."""
        pattern = {"frequency": "daily", "interval": 1}
        assert validate_recurring_pattern(pattern) is True

    def test_validate_weekly_pattern(self):
        """Testa validação de padrão semanal."""
        pattern = {"frequency": "weekly", "interval": 1, "days_of_week": [0, 2, 4]}
        assert validate_recurring_pattern(pattern) is True

    def test_validate_monthly_pattern(self):
        """Testa validação de padrão mensal."""
        pattern = {"frequency": "monthly", "interval": 1}
        assert validate_recurring_pattern(pattern) is True

    def test_validate_invalid_frequency(self):
        """Testa que frequência inválida falha."""
        pattern = {"frequency": "invalid", "interval": 1}
        with pytest.raises(ValueError, match="Invalid frequency"):
            validate_recurring_pattern(pattern)

    def test_validate_invalid_interval(self):
        """Testa que intervalo inválido falha."""
        pattern = {"frequency": "daily", "interval": 0}
        with pytest.raises(ValueError, match="Interval must be"):
            validate_recurring_pattern(pattern)

    def test_validate_weekly_requires_days_of_week(self):
        """Testa que semanal pode ter days_of_week opcional."""
        pattern = {"frequency": "weekly", "interval": 1}
        # days_of_week é opcional, então deve passar
        assert validate_recurring_pattern(pattern) is True

