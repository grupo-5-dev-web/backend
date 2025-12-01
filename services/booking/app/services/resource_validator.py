import httpx
from fastapi import HTTPException

async def validar_recurso_existe(resource_service_url: str, resource_id: str):
    """
    Consulta o Resource Service: /resources/<id>
    Em ambiente de teste (sem URL), retorna um mock.
    """
    # Ambiente de teste: não valida externo
    if not resource_service_url:
        return {"id": resource_id, "tenant_id": None}

    url = f"{resource_service_url.rstrip('/')}/{resource_id}"

    async with httpx.AsyncClient() as client:
        resp = await client.get(url)

    if resp.status_code == 404:
        raise HTTPException(404, "Recurso não encontrado")

    if resp.status_code != 200:
        raise HTTPException(500, "Erro ao validar recurso no serviço Resource")

    return resp.json()