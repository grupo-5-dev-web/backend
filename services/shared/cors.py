"""CORS configuration utilities for FastAPI services."""

import logging
import os
from typing import List

logger = logging.getLogger(__name__)


def get_cors_origins() -> List[str]:
    """
    Get CORS origins from environment with smart defaults.
    
    Returns:
        List of allowed CORS origins
        
    Raises:
        RuntimeError: If CORS_ORIGINS is not configured in production environment
    """
    raw_origins = os.getenv("CORS_ORIGINS", "")
    
    if raw_origins:
        # Explicit configuration provided
        return [o.strip() for o in raw_origins.split(",") if o.strip()]
    
    # Fallback: allow all for dev/test, raise error in production
    is_dev = os.getenv("ENVIRONMENT", "development") in ["development", "dev", "test"]
    if is_dev:
        logger.warning("CORS_ORIGINS not set. Using wildcard (*) for development. Set CORS_ORIGINS in production!")
        return ["*"]
    else:
        raise RuntimeError("CORS_ORIGINS environment variable must be set in production. Refusing to start with insecure CORS configuration.")
