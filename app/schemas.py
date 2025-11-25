from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UsuarioCreate(BaseModel):
    nome_completo: str = Field(..., min_length=1, description="Nome completo do usuário")
    email: EmailStr = Field(..., description="Email do usuário")
    senha: str = Field(..., min_length=6, description="Senha do usuário (mínimo 6 caracteres)")
    cargo: Optional[str] = Field(None, description="Cargo do usuário")
    municipio: Optional[str] = Field(None, description="Município do usuário")
    uf: Optional[str] = Field(None, max_length=2, description="UF do usuário (2 caracteres)")


class UsuarioUpdate(BaseModel):
    nome_completo: Optional[str] = Field(None, min_length=1, description="Nome completo do usuário")
    email: Optional[EmailStr] = Field(None, description="Email do usuário")
    senha: Optional[str] = Field(None, min_length=6, description="Senha do usuário (mínimo 6 caracteres)")
    cargo: Optional[str] = Field(None, description="Cargo do usuário")
    municipio: Optional[str] = Field(None, description="Município do usuário")
    uf: Optional[str] = Field(None, max_length=2, description="UF do usuário (2 caracteres)")
    ativo: Optional[bool] = Field(None, description="Status ativo/inativo do usuário")


class UsuarioResponse(BaseModel):
    id: int
    nome_completo: str
    email: str
    cargo: Optional[str] = None
    municipio: Optional[str] = None
    uf: Optional[str] = None
    ativo: bool
    criado_em: Optional[datetime] = None
    atualizado_em: Optional[datetime] = None

    class Config:
        from_attributes = True


class BuscaRequest(BaseModel):
    query: str


class BuscaResponse(BaseModel):
    resultados: list
    total: int

