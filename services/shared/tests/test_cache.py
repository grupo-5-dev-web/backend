"""Testes para cache Redis."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, time
from uuid import uuid4
import json

from shared.cache import (
    get_cached_settings,
    set_cached_settings,
    get_cached_availability,
    set_cached_availability,
    invalidate_settings_cache,
    invalidate_availability_cache,
    create_redis_cache,
)


class TestRedisCache:
    """Testes para criação e configuração de cache Redis."""

    def test_create_redis_cache_with_url(self):
        """Testa criação de cache com URL Redis."""
        cache = create_redis_cache("redis://localhost:6379")
        assert cache is not None

    def test_create_redis_cache_without_redis(self):
        """Testa que retorna None se Redis não está disponível."""
        cache = create_redis_cache(None)
        assert cache is None

    def test_create_redis_cache_with_empty_url(self):
        """Testa que retorna None se URL está vazia."""
        cache = create_redis_cache("")
        assert cache is None


class TestSettingsCache:
    """Testes para cache de OrganizationSettings."""

    def test_set_and_get_cached_settings(self):
        """Testa armazenar e recuperar settings do cache."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True
        
        tenant_id = uuid4()
        settings = {
            "timezone": "America/Sao_Paulo",
            "working_hours_start": "08:00:00",
            "working_hours_end": "18:00:00",
            "booking_interval": 30,
            "advance_booking_days": 30,
            "cancellation_hours": 24,
        }
        
        # Simular cache miss e set
        cached = get_cached_settings(mock_redis, tenant_id)
        assert cached is None
        
        set_cached_settings(mock_redis, tenant_id, settings, ttl=300)
        mock_redis.set.assert_called_once()
        
        # Simular cache hit
        mock_redis.get.return_value = json.dumps(settings)
        cached = get_cached_settings(mock_redis, tenant_id)
        assert cached is not None
        assert cached["timezone"] == settings["timezone"]

    def test_get_cached_settings_cache_miss(self):
        """Testa que retorna None quando não há cache."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        
        tenant_id = uuid4()
        cached = get_cached_settings(mock_redis, tenant_id)
        
        assert cached is None
        mock_redis.get.assert_called_once()

    def test_get_cached_settings_invalid_json(self):
        """Testa que retorna None quando JSON é inválido."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = "invalid json"
        
        tenant_id = uuid4()
        cached = get_cached_settings(mock_redis, tenant_id)
        
        assert cached is None

    def test_invalidate_settings_cache(self):
        """Testa invalidação de cache de settings."""
        mock_redis = MagicMock()
        mock_redis.delete.return_value = 1
        
        tenant_id = uuid4()
        invalidate_settings_cache(mock_redis, tenant_id)
        
        mock_redis.delete.assert_called_once()

    def test_set_cached_settings_with_ttl(self):
        """Testa que TTL é aplicado corretamente."""
        mock_redis = MagicMock()
        mock_redis.set.return_value = True
        
        tenant_id = uuid4()
        settings = {"timezone": "UTC"}
        
        set_cached_settings(mock_redis, tenant_id, settings, ttl=600)
        
        # Verificar que set foi chamado com ex (expiration)
        call_args = mock_redis.set.call_args
        assert "ex" in call_args.kwargs
        assert call_args.kwargs.get("ex") == 600


class TestAvailabilityCache:
    """Testes para cache de disponibilidade de recursos."""

    def test_set_and_get_cached_availability(self):
        """Testa armazenar e recuperar disponibilidade do cache."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True
        
        resource_id = uuid4()
        date_str = "2025-12-15"
        availability = {
            "resource_id": str(resource_id),
            "date": date_str,
            "slots": [
                {"start_time": "2025-12-15T08:00:00Z", "end_time": "2025-12-15T08:30:00Z"},
                {"start_time": "2025-12-15T08:30:00Z", "end_time": "2025-12-15T09:00:00Z"},
            ],
        }
        
        # Simular cache miss e set
        cached = get_cached_availability(mock_redis, resource_id, date_str)
        assert cached is None
        
        set_cached_availability(mock_redis, resource_id, date_str, availability, ttl=300)
        mock_redis.set.assert_called_once()
        
        # Simular cache hit
        mock_redis.get.return_value = json.dumps(availability)
        cached = get_cached_availability(mock_redis, resource_id, date_str)
        assert cached is not None
        assert len(cached["slots"]) == 2

    def test_get_cached_availability_cache_miss(self):
        """Testa que retorna None quando não há cache."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        
        resource_id = uuid4()
        cached = get_cached_availability(mock_redis, resource_id, "2025-12-15")
        
        assert cached is None

    def test_invalidate_availability_cache(self):
        """Testa invalidação de cache de disponibilidade."""
        mock_redis = MagicMock()
        mock_redis.delete.return_value = 1
        
        resource_id = uuid4()
        invalidate_availability_cache(mock_redis, resource_id, "2025-12-15")
        
        mock_redis.delete.assert_called_once()

    def test_invalidate_all_availability_for_resource(self):
        """Testa invalidação de todo cache de disponibilidade de um recurso."""
        mock_redis = MagicMock()
        mock_redis.keys.return_value = ["availability:resource:123:2025-12-15", "availability:resource:123:2025-12-16"]
        mock_redis.delete.return_value = 2
        
        resource_id = uuid4()
        invalidate_availability_cache(mock_redis, resource_id, date_str=None)
        
        mock_redis.keys.assert_called_once()
        mock_redis.delete.assert_called_once()


class TestCacheIntegration:
    """Testes de integração do cache."""

    def test_cache_without_redis_gracefully_degrades(self):
        """Testa que sistema funciona sem Redis (graceful degradation)."""
        tenant_id = uuid4()
        settings = {"timezone": "UTC"}
        
        # Sem Redis, deve retornar None sem erro
        cached = get_cached_settings(None, tenant_id)
        assert cached is None
        
        # Set também não deve falhar
        set_cached_settings(None, tenant_id, settings, ttl=300)
        # Não deve levantar exceção

    def test_cache_key_format(self):
        """Testa formato das chaves de cache."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True
        
        tenant_id = uuid4()
        resource_id = uuid4()
        
        # Verificar formato das chaves
        get_cached_settings(mock_redis, tenant_id)
        settings_key = mock_redis.get.call_args[0][0]
        assert settings_key.startswith("settings:")
        assert str(tenant_id) in settings_key
        
        get_cached_availability(mock_redis, resource_id, "2025-12-15")
        availability_key = mock_redis.get.call_args[0][0]
        assert availability_key.startswith("availability:")
        assert str(resource_id) in availability_key
        assert "2025-12-15" in availability_key

