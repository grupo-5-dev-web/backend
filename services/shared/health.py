"""Health check utilities for FastAPI services.

Provides endpoints /health and /ready for Docker/Kubernetes monitoring.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional, Union

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.engine import Engine

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

try:
    import redis.asyncio as aioredis
    AIOREDIS_AVAILABLE = True
except ImportError:
    AIOREDIS_AVAILABLE = False
    aioredis = None


def check_database_health(engine: Engine, timeout: float = 2.0) -> bool:
    """Verifica se o banco de dados está disponível.
    
    Args:
        engine: SQLAlchemy engine para conexão com banco
        timeout: Timeout em segundos para a verificação
        
    Returns:
        True se banco está disponível, False caso contrário
    """
    if engine is None:
        return False
    
    try:
        with engine.connect() as conn:
            # Executa uma query simples para verificar conexão
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        return True
    except Exception:
        return False


async def check_redis_health(
    redis_client: Optional[Union[redis.Redis, aioredis.Redis, str]] = None
) -> Optional[bool]:
    """Verifica se o Redis está disponível.
    
    Args:
        redis_client: Cliente Redis (síncrono, assíncrono, ou URL string) ou None
        
    Returns:
        True se Redis está disponível,
        False se Redis está configurado mas indisponível,
        None se Redis não está configurado
    """
    if redis_client is None:
        return None
    
    try:
        # Se for string (URL), criar cliente temporário
        if isinstance(redis_client, str):
            if AIOREDIS_AVAILABLE:
                temp_client = aioredis.from_url(redis_client)
                try:
                    await asyncio.wait_for(temp_client.ping(), timeout=1.0)
                    return True
                finally:
                    await temp_client.aclose()
            elif REDIS_AVAILABLE:
                temp_client = redis.Redis.from_url(redis_client)
                try:
                    temp_client.ping()
                    return True
                finally:
                    temp_client.close()
            return None
        
        # Se for cliente assíncrono
        if AIOREDIS_AVAILABLE and isinstance(redis_client, aioredis.Redis):
            await asyncio.wait_for(redis_client.ping(), timeout=1.0)
            return True
        
        # Se for cliente síncrono
        if REDIS_AVAILABLE and isinstance(redis_client, redis.Redis):
            redis_client.ping()
            return True
        
        return None
    except Exception:
        return False


def create_health_router(
    service_name: str,
    database_engine: Optional[Engine] = None,
    redis_client: Optional[Union[redis.Redis, aioredis.Redis, str]] = None,
) -> APIRouter:
    """Cria router FastAPI com endpoints /health e /ready.
    
    Args:
        service_name: Nome do serviço (ex: "user", "tenant")
        database_engine: Engine SQLAlchemy para verificação de banco
        redis_client: Cliente Redis para verificação (opcional)
        
    Returns:
        APIRouter configurado com endpoints de health check
    """
    router = APIRouter(tags=["Health"])
    
    @router.get("/health", status_code=status.HTTP_200_OK)
    def health():
        """Endpoint básico de saúde.
        
        Sempre retorna 200 OK se o serviço está rodando.
        Não verifica dependências - use /ready para isso.
        """
        return {
            "status": "ok",
            "service": service_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    
    @router.get("/ready", status_code=status.HTTP_200_OK)
    async def ready():
        """Endpoint de readiness.
        
        Verifica se todas as dependências estão disponíveis:
        - Database (obrigatório)
        - Redis (opcional, se configurado)
        
        Retorna 200 se tudo está OK, 503 se alguma dependência falhou.
        """
        checks = {}
        all_healthy = True
        
        # Verificar banco de dados
        db_healthy = check_database_health(database_engine) if database_engine else False
        checks["database"] = db_healthy
        if not db_healthy:
            all_healthy = False
        
        # Verificar Redis (se configurado)
        redis_healthy = await check_redis_health(redis_client)
        checks["redis"] = redis_healthy
        if redis_healthy is False:  # False significa configurado mas indisponível
            all_healthy = False
        
        response_data = {
            "status": "ready" if all_healthy else "not_ready",
            "service": service_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "checks": checks,
        }
        
        if all_healthy:
            return JSONResponse(
                content=response_data,
                status_code=status.HTTP_200_OK,
            )
        else:
            return JSONResponse(
                content=response_data,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
    
    return router

