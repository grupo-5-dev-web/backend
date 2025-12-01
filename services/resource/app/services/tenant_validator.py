import httpx
from fastapi import HTTPException

async def validar_tenant_existe(tenant_service_url: str, tenant_id: str):
    url = f"{tenant_service_url}/{tenant_id}"

    async with httpx.AsyncClient() as client:
        resp = await client.get(url)

    if resp.status_code != 200:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
