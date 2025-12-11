import os
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt
from uuid import UUID

pwd_context = CryptContext(schemes=["bcrypt", "sha256_crypt"], deprecated="auto")

# lidas tanto em CI quanto em "prod"
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS512")
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24"))


def criar_token_jwt(user_id: UUID, tenant_id: UUID,  user_type: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode = {
        "exp": expire,
        "sub": str(user_id),         # id do usuário
        "tenant_id": str(tenant_id), # id do tenant
        "user_type": user_type,       # "admin" ou "user"
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
