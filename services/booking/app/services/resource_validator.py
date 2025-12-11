import httpx
from fastapi import HTTPException

async def validar_recurso_existe(
    resource_service_url: str,
    resource_id: str,
    auth_token: str | None = None,
):
    if not resource_service_url:
        return {"id": resource_id}

    url = f"{resource_service_url.rstrip('/')}/resources/{resource_id}"

    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers)
        except httpx.RequestError:
            raise HTTPException(
                500,
                "Erro ao comunicar com o Resource Service",
            )

    if resp.status_code == 404:
        raise HTTPException(404, "Recurso não encontrado")

    if resp.status_code != 200:
        raise HTTPException(
            500,
            f"Erro ao validar recurso no serviço Resource (status={resp.status_code})",
        )

    return resp.json()