import httpx
from fastapi import HTTPException

async def validar_tenant_existe(tenant_service_url: str, tenant_id: str):
    """
    Em produção: valida o Tenant no Tenant Service.
    Em testes (tenant_service_url=None): ignora e retorna fake OK.
    """
    
    if not tenant_service_url:
        return {"id": tenant_id}

    url = f"{tenant_service_url.rstrip('/')}/{tenant_id}"

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url)
        except httpx.RequestError:
            raise HTTPException(
                status_code=500,
                detail="Erro ao comunicar com o Tenant Service"
            )

    if resp.status_code == 404:
        raise HTTPException(404, "Tenant não encontrado")

    if resp.status_code != 200:
        raise HTTPException(
            500,
            "Erro ao comunicar com o Tenant Service"
        )

    return resp.json()
