"""Lógica de recorrência para bookings.

Fornece funções para calcular ocorrências recorrentes baseadas em padrões
(diário, semanal, mensal).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from dateutil.relativedelta import relativedelta


# Limite máximo de ocorrências quando end_date não está definido
MAX_RECURRING_OCCURRENCES = 365


def validate_recurring_pattern(pattern: Dict[str, Any]) -> bool:
    """Valida um padrão de recorrência.
    
    Args:
        pattern: Dicionário com frequency, interval, end_date, days_of_week
        
    Returns:
        True se válido
        
    Raises:
        ValueError: Se padrão for inválido
    """
    frequency = pattern.get("frequency")
    if frequency not in ["daily", "weekly", "monthly"]:
        raise ValueError(f"Invalid frequency: {frequency}. Must be 'daily', 'weekly', or 'monthly'")
    
    interval = pattern.get("interval", 1)
    if interval < 1 or interval > 52:
        raise ValueError(f"Interval must be between 1 and 52, got {interval}")
    
    # days_of_week é opcional, mas se presente deve ser lista de 0-6
    days_of_week = pattern.get("days_of_week")
    if days_of_week is not None:
        if not isinstance(days_of_week, list):
            raise ValueError("days_of_week must be a list")
        if not all(0 <= day <= 6 for day in days_of_week):
            raise ValueError("days_of_week must contain values between 0 (Monday) and 6 (Sunday)")
    
    return True


def get_next_occurrence(
    current: datetime,
    pattern: Dict[str, Any],
) -> datetime:
    """Calcula a próxima ocorrência baseada no padrão.
    
    Args:
        current: Data/hora atual
        pattern: Padrão de recorrência
        
    Returns:
        Próxima ocorrência
    """
    frequency = pattern["frequency"]
    interval = pattern.get("interval", 1)
    
    if frequency == "daily":
        return current + timedelta(days=interval)
    elif frequency == "weekly":
        return current + timedelta(weeks=interval)
    elif frequency == "monthly":
        return current + relativedelta(months=interval)
    else:
        raise ValueError(f"Unsupported frequency: {frequency}")


def calculate_recurring_occurrences(
    start_time: datetime,
    end_time: datetime,
    pattern: Dict[str, Any],
) -> List[Dict[str, datetime]]:
    """Calcula todas as ocorrências recorrentes baseadas no padrão.
    
    Args:
        start_time: Data/hora de início da primeira ocorrência
        end_time: Data/hora de término da primeira ocorrência
        pattern: Padrão de recorrência com frequency, interval, end_date, days_of_week
        
    Returns:
        Lista de dicionários com start_time e end_time para cada ocorrência
    """
    validate_recurring_pattern(pattern)
    
    frequency = pattern["frequency"]
    interval = pattern.get("interval", 1)
    end_date = pattern.get("end_date")
    days_of_week = pattern.get("days_of_week")
    
    occurrences = []
    duration = end_time - start_time
    
    # Primeira ocorrência sempre incluída
    current_start = start_time
    current_end = end_time
    
    # Limite de iterações para evitar loops infinitos
    max_iterations = MAX_RECURRING_OCCURRENCES if end_date is None else 1000
    iteration = 0
    
    while iteration < max_iterations:
        # Verificar se passou do end_date
        if end_date and current_start > end_date:
            break
        
        # Para weekly com days_of_week, verificar se o dia atual está na lista
        if frequency == "weekly" and days_of_week is not None:
            weekday = current_start.weekday()
            if weekday in days_of_week:
                occurrences.append({
                    "start_time": current_start,
                    "end_time": current_end,
                })
        else:
            # Para daily, monthly ou weekly sem days_of_week específicos
            occurrences.append({
                "start_time": current_start,
                "end_time": current_end,
            })
        
        # Calcular próxima ocorrência
        if frequency == "daily":
            current_start = current_start + timedelta(days=interval)
        elif frequency == "weekly":
            if days_of_week is not None:
                # Para weekly com days_of_week, avançar para o próximo dia da semana válido
                current_start = _get_next_weekday_occurrence(current_start, days_of_week, interval)
            else:
                current_start = current_start + timedelta(weeks=interval)
        elif frequency == "monthly":
            current_start = current_start + relativedelta(months=interval)
        
        current_end = current_start + duration
        
        iteration += 1
    
    return occurrences


def _get_next_weekday_occurrence(
    current: datetime,
    days_of_week: List[int],
    interval: int,
) -> datetime:
    """Calcula próxima ocorrência para weekly com days_of_week específicos.
    
    Args:
        current: Data/hora atual
        days_of_week: Lista de dias da semana (0=Segunda, 6=Domingo)
        interval: Intervalo em semanas
        
    Returns:
        Próxima ocorrência válida
    """
    current_weekday = current.weekday()
    days_of_week_sorted = sorted(days_of_week)
    
    # Procurar próximo dia válido na mesma semana
    for day in days_of_week_sorted:
        if day > current_weekday:
            days_ahead = day - current_weekday
            return current + timedelta(days=days_ahead)
    
    # Se não encontrou na mesma semana, pegar primeiro dia da próxima semana
    days_until_next_week = 7 - current_weekday + days_of_week_sorted[0]
    weeks_to_add = interval - 1 if interval > 1 else 0
    return current + timedelta(days=days_until_next_week + (weeks_to_add * 7))

