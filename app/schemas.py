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


# ==================== SCHEMAS PARA ANÁLISE DE PARTIDOS ====================

class MandatoInfo(BaseModel):
    eleitos: int
    total: int


class MandatosNacional(BaseModel):
    senador: MandatoInfo
    deputado_federal: MandatoInfo


class MandatosEstadual(BaseModel):
    governador: MandatoInfo
    deputado_estadual: MandatoInfo


class MandatosMunicipal(BaseModel):
    prefeito: MandatoInfo
    vereador: Optional[MandatoInfo] = None


class MandatosPartido(BaseModel):
    nacional: MandatosNacional
    estadual: MandatosEstadual
    municipal: MandatosMunicipal


class AnalisePartidoResponse(BaseModel):
    partido: str
    abrangencia: str
    territorio: str
    mandatos: MandatosPartido


# ==================== SCHEMAS PARA ANÁLISE DE PARTIDOS V2 (BigQuery) ====================

class CargoEleito(BaseModel):
    cargo: str
    total_cargos_eleitos: int


class AnalisePartidoResponseV2(BaseModel):
    partido: str
    abrangencia: str
    territorio: str
    municipio: Optional[str] = None
    cargos_eleitos: list[CargoEleito]


# ==================== SCHEMAS PARA BUSCA DE CANDIDATOS (BigQuery) ====================

from typing import Any
from datetime import date

class CandidatoResponse(BaseModel):
    """Schema para dados de candidato retornados do BigQuery"""
    ano: Optional[int] = None
    id_eleicao: Optional[str] = None
    tipo_eleicao: Optional[str] = None
    data_eleicao: Optional[date] = None
    sigla_uf: Optional[str] = None
    id_municipio: Optional[str] = None
    id_municipio_tse: Optional[str] = None
    titulo_eleitoral: Optional[str] = None
    cpf: Optional[str] = None
    sequencial: Optional[str] = None
    numero: Optional[str] = None
    nome: Optional[str] = None
    nome_urna: Optional[str] = None
    numero_partido: Optional[int] = None
    sigla_partido: Optional[str] = None
    
    # Campos adicionais que podem existir na tabela
    nome_partido: Optional[str] = None
    cargo: Optional[str] = None
    situacao: Optional[str] = None
    situacao_turno: Optional[str] = None
    votos: Optional[int] = None
    genero: Optional[str] = None
    grau_instrucao: Optional[str] = None
    estado_civil: Optional[str] = None
    cor_raca: Optional[str] = None
    ocupacao: Optional[str] = None
    data_nascimento: Optional[date] = None
    idade: Optional[int] = None
    email: Optional[str] = None
    
    class Config:
        from_attributes = True
        extra = "allow"  # Permite campos adicionais não definidos


class BuscaCandidatoResponse(BaseModel):
    """Schema para resposta da busca de candidatos"""
    resultados: list[dict]  # Lista flexível para aceitar todos os campos do BigQuery
    total: int
    termo_busca: str

