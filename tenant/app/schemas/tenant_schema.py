from pydantic import BaseModel, HttpUrl, ConfigDict, field_validator

class TenantBase(BaseModel):
    nome: str
    dominio: str
    logo: str
    tema_cor: str
    plano: str
    
    @field_validator("logo")
    def validar_url_logo(cls, v):
        try:
            HttpUrl(v)
        except Exception:
            raise ValueError("URL inválida para o campo 'logo'")
        return v

class TenantCreate(TenantBase):
    pass

class TenantOut(TenantBase):
    id: int
    nome: str
    dominio: str
    logo: str
    tema_cor: str
    plano: str
    
    model_config = ConfigDict(from_attributes=True)