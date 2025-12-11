import httpx
from fastapi import HTTPException

async def validar_usuario_existe(
    user_service_url: str,
    user_id: str,
    auth_token: str | None = None,
):

    if not user_service_url:
        return {"id": user_id, "tenant_id": None}

    url = f"{user_service_url.rstrip('/')}/users/{user_id}"

    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers)
        except httpx.RequestError:
            raise HTTPException(
                status_code=500,
                detail="Erro ao comunicar com o User Service",
            )

    if resp.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Usuário não encontrado",
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"Erro inesperado no User Service (status={resp.status_code})",
        )

    return resp.json()
