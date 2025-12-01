import httpx
from fastapi import HTTPException

async def validar_usuario_existe(user_service_url: str, user_id: str):
    """
    Valida existência do usuário via User Service.
    """
    # http://user:8000/users/<user_id>
    url = f"{user_service_url.rstrip('/')}/{user_id}"

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url)
        except httpx.RequestError:
            raise HTTPException(
                status_code=500,
                detail="Erro ao comunicar com o User Service"
            )

    if resp.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Usuário não encontrado"
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail="Erro inesperado no User Service"
        )

    return resp.json()
