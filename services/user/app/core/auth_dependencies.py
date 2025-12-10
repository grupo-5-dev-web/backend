from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core.security import SECRET_KEY, JWT_ALGORITHM
from app.core.database import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")

class TokenPayload(BaseModel):
    sub: UUID
    tenant_id: UUID

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Valida o JWT e retorna o objeto User do banco.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )

    user = db.query(User).filter(User.id == token_data.sub).first()

    # garante que o tenant do token bate com o tenant do usuário
    if not user or str(user.tenant_id) != str(token_data.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado ou tenant inválido",
        )

    return user
