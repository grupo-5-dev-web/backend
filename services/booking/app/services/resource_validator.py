import httpx
from fastapi import HTTPException

async def validar_recurso_existe(resource_service_url: str, resource_id: str):
    """
    Consulta o Resource Service: /resources/<id>
    Retorna erro 404 se o recurso não existir.
    """
    url = f"{resource_service_url.rstrip('/')}/{resource_id}"

    async with httpx.AsyncClient() as client:
        resp = await client.get(url)

    if resp.status_code == 404:
        raise HTTPException(404, "Recurso não encontrado")

    if resp.status_code != 200:
        raise HTTPException(500, "Erro ao validar recurso no serviço Resource")

    return resp.json()