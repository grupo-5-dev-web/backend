"""Cache Redis utilities para OrganizationSettings e disponibilidade de recursos.

Fornece funções para cachear dados com TTL configurável e invalidação.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
from uuid import UUID

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None


# Prefixos para chaves de cache
SETTINGS_CACHE_PREFIX = "settings:tenant:"
AVAILABILITY_CACHE_PREFIX = "availability:resource:"


def create_redis_cache(redis_url: Optional[str]) -> Optional[redis.Redis]:
    """Cria cliente Redis para cache.
    
    Args:
        redis_url: URL de conexão Redis (ou None se não configurado)
        
    Returns:
        Cliente Redis ou None se não disponível
    """
    if not REDIS_AVAILABLE or not redis_url or not redis_url.strip():
        return None
    
    try:
        return redis.Redis.from_url(redis_url, decode_responses=True)
    except Exception:
        return None


def _get_settings_cache_key(tenant_id: UUID) -> str:
    """Gera chave de cache para OrganizationSettings."""
    return f"{SETTINGS_CACHE_PREFIX}{tenant_id}"


def _get_availability_cache_key(resource_id: UUID, date_str: str) -> str:
    """Gera chave de cache para disponibilidade de recurso."""
    return f"{AVAILABILITY_CACHE_PREFIX}{resource_id}:{date_str}"


def get_cached_settings(
    cache: Optional[redis.Redis],
    tenant_id: UUID,
) -> Optional[Dict[str, Any]]:
    """Recupera OrganizationSettings do cache.
    
    Args:
        cache: Cliente Redis (ou None se não disponível)
        tenant_id: ID do tenant
        
    Returns:
        Dicionário com settings ou None se não encontrado
    """
    if cache is None:
        return None
    
    try:
        key = _get_settings_cache_key(tenant_id)
        cached_data = cache.get(key)
        
        if cached_data is None:
            return None
        
        return json.loads(cached_data)
    except Exception:
        return None


def set_cached_settings(
    cache: Optional[redis.Redis],
    tenant_id: UUID,
    settings: Dict[str, Any],
    ttl: int = 300,
) -> bool:
    """Armazena OrganizationSettings no cache.
    
    Args:
        cache: Cliente Redis (ou None se não disponível)
        tenant_id: ID do tenant
        settings: Dicionário com settings
        ttl: Time to live em segundos (padrão: 300 = 5 minutos)
        
    Returns:
        True se armazenado com sucesso, False caso contrário
    """
    if cache is None:
        return False
    
    try:
        key = _get_settings_cache_key(tenant_id)
        data = json.dumps(settings)
        cache.set(key, data, ex=ttl)
        return True
    except Exception:
        return False


def invalidate_settings_cache(
    cache: Optional[redis.Redis],
    tenant_id: UUID,
) -> bool:
    """Invalida cache de OrganizationSettings para um tenant.
    
    Args:
        cache: Cliente Redis (ou None se não disponível)
        tenant_id: ID do tenant
        
    Returns:
        True se invalidado com sucesso, False caso contrário
    """
    if cache is None:
        return False
    
    try:
        key = _get_settings_cache_key(tenant_id)
        cache.delete(key)
        return True
    except Exception:
        return False


def get_cached_availability(
    cache: Optional[redis.Redis],
    resource_id: UUID,
    date_str: str,
) -> Optional[Dict[str, Any]]:
    """Recupera disponibilidade de recurso do cache.
    
    Args:
        cache: Cliente Redis (ou None se não disponível)
        resource_id: ID do recurso
        date_str: Data no formato YYYY-MM-DD
        
    Returns:
        Dicionário com disponibilidade ou None se não encontrado
    """
    if cache is None:
        return None
    
    try:
        key = _get_availability_cache_key(resource_id, date_str)
        cached_data = cache.get(key)
        
        if cached_data is None:
            return None
        
        return json.loads(cached_data)
    except Exception:
        return None


def set_cached_availability(
    cache: Optional[redis.Redis],
    resource_id: UUID,
    date_str: str,
    availability: Dict[str, Any],
    ttl: int = 300,
) -> bool:
    """Armazena disponibilidade de recurso no cache.
    
    Args:
        cache: Cliente Redis (ou None se não disponível)
        resource_id: ID do recurso
        date_str: Data no formato YYYY-MM-DD
        availability: Dicionário com dados de disponibilidade
        ttl: Time to live em segundos (padrão: 300 = 5 minutos)
        
    Returns:
        True se armazenado com sucesso, False caso contrário
    """
    if cache is None:
        return False
    
    try:
        key = _get_availability_cache_key(resource_id, date_str)
        data = json.dumps(availability)
        cache.set(key, data, ex=ttl)
        return True
    except Exception:
        return False


def invalidate_availability_cache(
    cache: Optional[redis.Redis],
    resource_id: UUID,
    date_str: Optional[str] = None,
) -> bool:
    """Invalida cache de disponibilidade de recurso.
    
    Args:
        cache: Cliente Redis (ou None se não disponível)
        resource_id: ID do recurso
        date_str: Data específica (YYYY-MM-DD) ou None para invalidar todas
        
    Returns:
        True se invalidado com sucesso, False caso contrário
    """
    if cache is None:
        return False
    
    try:
        if date_str:
            # Invalidar data específica
            key = _get_availability_cache_key(resource_id, date_str)
            cache.delete(key)
        else:
            # Invalidar todas as datas do recurso
            pattern = f"{AVAILABILITY_CACHE_PREFIX}{resource_id}:*"
            keys = cache.keys(pattern)
            if keys:
                cache.delete(*keys)
        return True
    except Exception:
        return False


def get_cache_ttl(ttl_type: str, default: int = 300) -> int:
    """Obtém TTL de cache de variável de ambiente.
    
    Args:
        ttl_type: Tipo de TTL ('settings' ou 'availability')
        default: Valor padrão em segundos
        
    Returns:
        TTL em segundos
    """
    env_var = f"CACHE_TTL_{ttl_type.upper()}"
    ttl_str = os.getenv(env_var)
    
    if ttl_str:
        try:
            return int(ttl_str)
        except ValueError:
            pass
    
    return default

