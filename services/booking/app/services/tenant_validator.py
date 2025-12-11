# services/booking/app/services/tenant_validator.py
import httpx
from fastapi import HTTPException

async def validar_tenant_existe(
    tenant_service_url: str,
    tenant_id: str,
    auth_token: str | None = None,
):
    """
    Valida existência do tenant via Tenant Service.
    Em ambiente de teste (sem URL), retorna mock.
    """
    if not tenant_service_url:
        return {"id": tenant_id}

    url = f"{tenant_service_url.rstrip('/')}/tenants/{tenant_id}"

    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers)
        except httpx.RequestError:
            raise HTTPException(
                status_code=500,
                detail="Erro ao comunicar com o Tenant Service",
            )

    if resp.status_code == 404:
        raise HTTPException(404, "Tenant não encontrado")

    if resp.status_code != 200:
        raise HTTPException(
            500,
            f"Erro ao comunicar com o Tenant Service (status={resp.status_code})",
        )

    return resp.json()
