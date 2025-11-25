"""
Script para inicializar o banco de dados e criar um usuário de teste
Execute: python init_db.py
"""
from app.database import engine, Base, SessionLocal
from app import models
from app.auth import gerar_hash_senha

def init_db():
    """Cria as tabelas e um usuário de teste"""
    # Criar todas as tabelas
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Verificar se já existe um usuário com o email de teste
        usuario_existente = db.query(models.Usuario).filter(
            models.Usuario.email == "teste@example.com"
        ).first()
        
        if usuario_existente:
            print("Usuário de teste já existe!")
            print(f"Email: {usuario_existente.email}")
            return
        
        # Criar usuário de teste
        usuario_teste = models.Usuario(
            nome_completo="Usuário de Teste",
            email="teste@example.com",
            senha_hash=gerar_hash_senha("senha123"),
            ativo=True
        )
        
        db.add(usuario_teste)
        db.commit()
        db.refresh(usuario_teste)
        
        print("=" * 50)
        print("Banco de dados inicializado com sucesso!")
        print("=" * 50)
        print("\nUsuário de teste criado:")
        print(f"  Email: teste@example.com")
        print(f"  Senha: senha123")
        print("\nVocê pode usar essas credenciais para fazer login na API.")
        print("=" * 50)
        
    except Exception as e:
        db.rollback()
        print(f"Erro ao inicializar banco de dados: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    init_db()

