import os
import httpx
from fastapi import HTTPException


def is_testing() -> bool:
    """
    Detecta se está rodando `pytest`.
    """
    return os.getenv("PYTEST_CURRENT_TEST") is not None


async def validar_tenant_existe(tenant_service_url: str, tenant_id: str):
    """
    Valida se o tenant existe via Tenant Service.
    Em modo de teste, não faz chamada HTTP.
    """
    # 1. Bypass no pytest
    if is_testing():
        return {"id": tenant_id}

    # 2. Garantir que tenant_service_url existe
    if not tenant_service_url:
        raise HTTPException(
            status_code=500,
            detail="TENANT_SERVICE_URL não configurada no serviço atual",
        )

    # 3. Monta URL correta
    # Exemplo: http://tenant:8000/tenants/<tenant_id>
    base = tenant_service_url.rstrip("/")
    url = f"{base}/{tenant_id}"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
    except httpx.RequestError:
        raise HTTPException(
            status_code=500,
            detail="Erro ao comunicar com o Tenant Service",
        )

    if resp.status_code == 404:
        raise HTTPException(404, "Tenant não encontrado")

    if resp.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail="Erro inesperado ao consultar o Tenant Service",
        )

    return resp.json()