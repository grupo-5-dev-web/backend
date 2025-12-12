"""CORS (Cross-Origin Resource Sharing) configuration utilities.

Provides environment-based CORS configuration:
- Development: allows all origins (*)
- Production: restricts to specific domains from CORS_ORIGINS env var
"""

from __future__ import annotations

import os
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def get_cors_origins() -> List[str]:
    """Obtém lista de origens permitidas para CORS baseado no ambiente.
    
    - Development: retorna ["*"] (permite todos)
    - Production: retorna lista de domínios de CORS_ORIGINS (obrigatório)
    
    Returns:
        Lista de origens permitidas
        
    Raises:
        ValueError: Se em produção e CORS_ORIGINS não estiver configurado
    """
    environment = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()
    
    if environment in ("production", "prod"):
        cors_origins = os.getenv("CORS_ORIGINS", "").strip()
        
        if not cors_origins:
            raise ValueError(
                "CORS_ORIGINS must be set in production. "
                "Configure allowed domains separated by commas, e.g.: "
                "CORS_ORIGINS=https://app.example.com,https://admin.example.com"
            )
        
        # Separar por vírgula e remover espaços em branco
        origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
        
        if not origins:
            raise ValueError(
                "CORS_ORIGINS must contain at least one valid domain in production."
            )
        
        return origins
    
    # Development: permite todos
    return ["*"]


def configure_cors(app: FastAPI) -> None:
    """Configura middleware CORS no app FastAPI baseado no ambiente.
    
    Args:
        app: Instância FastAPI para configurar
        
    Raises:
        ValueError: Se em produção e CORS_ORIGINS não estiver configurado
    """
    origins = get_cors_origins()
    
    # Configurações adicionais
    allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"
    max_age = int(os.getenv("CORS_MAX_AGE", "600"))  # Default: 10 minutos
    
    # Em desenvolvimento com *, não podemos permitir credentials
    # (CORS spec: quando Access-Control-Allow-Origin é *, credentials deve ser false)
    if origins == ["*"] and allow_credentials:
        allow_credentials = False
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
        max_age=max_age,
    )

