from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db, engine, Base
from app import models, schemas, auth

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

