from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from app.database import get_db, engine, Base
from app import models, schemas, auth
from app import bigquery_client

# Criar tabelas no banco de dados
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LabVotoAI API",
    description="API backend para o projeto LabVotoAI",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configurar CORS para permitir acesso de qualquer origem
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Bem-vindo ao LabVotoAI API"}

@app.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    try:
        # Tenta fazer uma consulta simples para verificar a conexão
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")


@app.post("/login", response_model=schemas.TokenResponse, tags=["Autenticação"])
def login(credenciais: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Endpoint de login - retorna token JWT"""
    usuario = db.query(models.Usuario).filter(models.Usuario.email == credenciais.email).first()
    
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos"
        )
    
    if not auth.verificar_senha(credenciais.senha, usuario.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos"
        )
    
    if not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo"
        )
    
    access_token = auth.criar_token_acesso(data={"sub": usuario.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/busca", response_model=schemas.BuscaResponse, tags=["Busca"])
def buscar(
    query: str,
    usuario_atual: models.Usuario = Depends(auth.verificar_token),
    db: Session = Depends(get_db)
):
    """Endpoint protegido de busca - requer autenticação"""
    # Exemplo simples de busca - você pode implementar a lógica real aqui
    resultados = []
    
    # Por enquanto, retorna uma resposta de exemplo
    if query:
        resultados = [
            {"id": 1, "titulo": f"Resultado para: {query}", "descricao": "Descrição do resultado"},
            {"id": 2, "titulo": f"Outro resultado: {query}", "descricao": "Mais uma descrição"},
        ]
    
    return {
        "resultados": resultados,
        "total": len(resultados)
    }


# ==================== CRUD DE USUÁRIOS ====================

@app.get("/usuarios", response_model=list[schemas.UsuarioResponse], tags=["Usuários"])
def listar_usuarios(
    skip: int = 0,
    limit: int = 100,
    usuario_atual: models.Usuario = Depends(auth.verificar_token),
    db: Session = Depends(get_db)
):
    """Lista todos os usuários - requer autenticação"""
    usuarios = db.query(models.Usuario).offset(skip).limit(limit).all()
    return usuarios


@app.get("/usuarios/{usuario_id}", response_model=schemas.UsuarioResponse, tags=["Usuários"])
def obter_usuario(
    usuario_id: int,
    usuario_atual: models.Usuario = Depends(auth.verificar_token),
    db: Session = Depends(get_db)
):
    """Obtém um usuário específico por ID - requer autenticação"""
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    return usuario


@app.post("/usuarios", response_model=schemas.UsuarioResponse, status_code=status.HTTP_201_CREATED, tags=["Usuários"])
def criar_usuario(usuario: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    """Cria um novo usuário"""
    # Verificar se o email já existe
    usuario_existente = db.query(models.Usuario).filter(models.Usuario.email == usuario.email).first()
    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado"
        )
    
    # Criar hash da senha
    senha_hash = auth.gerar_hash_senha(usuario.senha)
    
    # Criar novo usuário
    novo_usuario = models.Usuario(
        nome_completo=usuario.nome_completo,
        email=usuario.email,
        senha_hash=senha_hash,
        cargo=usuario.cargo,
        municipio=usuario.municipio,
        uf=usuario.uf.upper() if usuario.uf else None  # Converter UF para maiúsculo
    )
    
    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)
    
    return novo_usuario


@app.put("/usuarios/{usuario_id}", response_model=schemas.UsuarioResponse, tags=["Usuários"])
def atualizar_usuario(
    usuario_id: int,
    usuario_update: schemas.UsuarioUpdate,
    usuario_atual: models.Usuario = Depends(auth.verificar_token),
    db: Session = Depends(get_db)
):
    """Atualiza um usuário existente - requer autenticação"""
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    # Verificar se o email já está em uso por outro usuário
    if usuario_update.email and usuario_update.email != usuario.email:
        email_existente = db.query(models.Usuario).filter(
            models.Usuario.email == usuario_update.email,
            models.Usuario.id != usuario_id
        ).first()
        if email_existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email já está em uso por outro usuário"
            )
    
    # Atualizar apenas os campos fornecidos
    update_data = usuario_update.model_dump(exclude_unset=True)
    
    # Se houver senha, criar hash
    if "senha" in update_data:
        update_data["senha_hash"] = auth.gerar_hash_senha(update_data.pop("senha"))
    
    # Converter UF para maiúsculo se fornecido
    if "uf" in update_data and update_data["uf"]:
        update_data["uf"] = update_data["uf"].upper()
    
    # Atualizar campos
    for field, value in update_data.items():
        setattr(usuario, field, value)
    
    db.commit()
    db.refresh(usuario)
    
    return usuario


@app.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Usuários"])
def deletar_usuario(
    usuario_id: int,
    usuario_atual: models.Usuario = Depends(auth.verificar_token),
    db: Session = Depends(get_db)
):
    """Deleta um usuário - requer autenticação"""
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    db.delete(usuario)
    db.commit()
    
    return None


# ==================== ANÁLISE DE PARTIDOS ====================

def obter_dados_mockados_partido(partido: str, abrangencia: str, territorio: str) -> dict:
    """Retorna dados mockados de mandatos para um partido"""
    
    # Dados base para NOVO (conforme exemplo da imagem)
    dados_novo = {
        "nacional": {
            "senador": {"eleitos": 3, "total": 81},
            "deputado_federal": {"eleitos": 18, "total": 513}
        },
        "estadual": {
            "governador": {"eleitos": 2, "total": 27},
            "deputado_estadual": {"eleitos": 25, "total": 1024}
        },
        "municipal": {
            "prefeito": {"eleitos": 12, "total": 5569},
            "vereador": {"eleitos": 0, "total": 0}
        }
    }
    
    # Dados mockados para PT
    dados_pt = {
        "nacional": {
            "senador": {"eleitos": 8, "total": 81},
            "deputado_federal": {"eleitos": 68, "total": 513}
        },
        "estadual": {
            "governador": {"eleitos": 5, "total": 27},
            "deputado_estadual": {"eleitos": 120, "total": 1024}
        },
        "municipal": {
            "prefeito": {"eleitos": 250, "total": 5569},
            "vereador": {"eleitos": 1500, "total": 0}
        }
    }
    
    # Dados mockados para PL
    dados_pl = {
        "nacional": {
            "senador": {"eleitos": 12, "total": 81},
            "deputado_federal": {"eleitos": 99, "total": 513}
        },
        "estadual": {
            "governador": {"eleitos": 7, "total": 27},
            "deputado_estadual": {"eleitos": 180, "total": 1024}
        },
        "municipal": {
            "prefeito": {"eleitos": 400, "total": 5569},
            "vereador": {"eleitos": 2500, "total": 0}
        }
    }
    
    # Mapeamento de partidos
    dados_partidos = {
        "NOVO": dados_novo,
        "PT": dados_pt,
        "PL": dados_pl
    }
    
    # Retornar dados do partido ou dados padrão se não encontrado
    return dados_partidos.get(partido.upper(), dados_novo)


@app.get("/api/v1/analise-partido/{partido}/{abrangencia}/{territorio}", 
         response_model=schemas.AnalisePartidoResponseV2, 
         tags=["Partidos"])
def analise_partido(
    partido: str,
    abrangencia: str,
    territorio: str,
    municipio: Optional[str] = None
):
    """
    Endpoint de análise de partidos políticos
    
    Retorna os cargos eleitos de um partido baseado nos filtros:
    - partido: Sigla do partido (ex: NOVO, PT, PL)
    - abrangencia: Nacional, Estadual ou Municipal
    - territorio: Sigla da UF (para Estadual e Municipal) ou qualquer valor (para Nacional)
    - municipio: Nome do município (obrigatório para abrangência Municipal, query parameter)
    
    Exemplos:
    - /api/v1/analise-partido/NOVO/Nacional/Brasil
    - /api/v1/analise-partido/NOVO/Estadual/SP
    - /api/v1/analise-partido/NOVO/Municipal/SP?municipio=São Paulo
    """
    
    # Validar abrangência
    abrangencias_validas = ["Nacional", "Estadual", "Municipal"]
    if abrangencia not in abrangencias_validas:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Abrangência deve ser uma das opções: {', '.join(abrangencias_validas)}"
        )
    
    # Validar que para Municipal, municipio é obrigatório
    if abrangencia == "Municipal" and not municipio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Para abrangência Municipal, o parâmetro 'municipio' é obrigatório (query parameter)"
        )
    
    try:
        # Buscar dados no BigQuery
        cargos_eleitos = bigquery_client.buscar_cargos_eleitos_partido(
            partido=partido,
            abrangencia=abrangencia,
            territorio=territorio if abrangencia != "Nacional" else None,
            municipio=municipio
        )
        
        # Construir resposta
        return {
            "partido": partido.upper(),
            "abrangencia": abrangencia,
            "territorio": territorio,
            "municipio": municipio,
            "cargos_eleitos": cargos_eleitos
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar cargos eleitos: {str(e)}"
        )


# ==================== BUSCA DE POLÍTICOS (BigQuery) ====================

@app.get("/api/v1/politicos/busca/{nome}", 
         response_model=schemas.BuscaCandidatoResponse, 
         tags=["Políticos"])
def buscar_politico(
    nome: str,
    limit: int = 100
):
    """
    Busca políticos/candidatos pelo nome no BigQuery.
    
    A busca é feita de forma parcial (LIKE) nos campos:
    - nome: Nome completo do candidato
    - nome_urna: Nome de urna do candidato
    
    Parâmetros:
    - nome: Termo de busca (nome completo, parcial ou sobrenome)
    - limit: Limite de resultados (padrão: 100, máximo: 500)
    
    Exemplos:
    - /api/v1/politicos/busca/Guilherme Boulos
    - /api/v1/politicos/busca/Boulos
    - /api/v1/politicos/busca/Lula
    """
    
    # Validar limite
    if limit > 500:
        limit = 500
    if limit < 1:
        limit = 1
    
    # Validar termo de busca
    if not nome or len(nome.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O termo de busca deve ter pelo menos 2 caracteres"
        )
    
    try:
        # Buscar no BigQuery
        candidatos = bigquery_client.buscar_candidatos_por_nome(nome.strip(), limit)
        
        return {
            "resultados": candidatos,
            "total": len(candidatos),
            "termo_busca": nome.strip()
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar candidatos: {str(e)}"
        )


# ==================== VOTOS PARTIDO (BigQuery) ====================

@app.get("/api/v1/votos-partido", 
         response_model=schemas.VotosPartidoResponse, 
         tags=["Partidos"])
def buscar_votos_partido(
    sigla_partido: str,
    sigla_uf: str,
    cargo: str,
    ano: int = 2024,
    turnos: Optional[str] = None
):
    """
    Busca votos de um partido por município com percentual de votos válidos.
    
    Retorna os resultados agregados por município mostrando:
    - Votos do partido
    - Total de votos válidos
    - Proporção e percentual de votos válidos
    
    Parâmetros:
    - sigla_partido: Sigla do partido (ex: PODE, PT, PL) - obrigatório
    - sigla_uf: Sigla da UF (ex: AM, SP, RJ) - obrigatório
    - cargo: Cargo da eleição (ex: prefeito, governador, presidente) - obrigatório
    - ano: Ano da eleição (padrão: 2024)
    - turnos: Lista de turnos separados por vírgula (ex: "1,2" ou "1") - padrão: "1,2"
    
    Exemplos:
    - /api/v1/votos-partido?sigla_partido=PODE&sigla_uf=AM&cargo=prefeito
    - /api/v1/votos-partido?sigla_partido=PT&sigla_uf=SP&cargo=prefeito&ano=2020&turnos=1
    """
    
    # Validar parâmetros obrigatórios
    if not sigla_partido or not sigla_partido.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O parâmetro 'sigla_partido' é obrigatório"
        )
    
    if not sigla_uf or not sigla_uf.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O parâmetro 'sigla_uf' é obrigatório"
        )
    
    if not cargo or not cargo.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O parâmetro 'cargo' é obrigatório"
        )
    
    # Validar ano
    if ano < 2000 or ano > 2100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O ano deve estar entre 2000 e 2100"
        )
    
    # Processar turnos
    turnos_list = [1, 2]  # padrão
    if turnos:
        try:
            turnos_list = [int(t.strip()) for t in turnos.split(",") if t.strip()]
            if not turnos_list:
                turnos_list = [1, 2]
            # Validar turnos (geralmente 1 ou 2)
            for t in turnos_list:
                if t not in [1, 2]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Os turnos devem ser 1 ou 2"
                    )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato inválido para 'turnos'. Use números separados por vírgula (ex: '1,2')"
            )
    
    try:
        # Buscar dados no BigQuery
        resultados = bigquery_client.buscar_votos_partido(
            sigla_partido=sigla_partido.strip(),
            sigla_uf=sigla_uf.strip(),
            cargo=cargo.strip(),
            ano=ano,
            turnos=turnos_list
        )
        
        # Construir resposta
        return {
            "resultados": resultados,
            "total": len(resultados),
            "ano": ano,
            "sigla_partido": sigla_partido.upper(),
            "sigla_uf": sigla_uf.upper(),
            "cargo": cargo.lower(),
            "turnos": turnos_list
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar votos do partido: {str(e)}"
        )

