"""
Script para migrar o banco de dados para a nova estrutura
Execute: python migrate_db.py
"""
from sqlalchemy import text
from app.database import engine, SessionLocal
from app import models

def migrate_db():
    """Migra o banco de dados para a nova estrutura"""
    db = SessionLocal()
    try:
        # Verificar se a coluna nome_completo já existe
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='usuarios' AND column_name='nome_completo'
        """))
        
        if result.fetchone() is None:
            print("Migrando banco de dados...")
            
            # Adicionar novas colunas
            db.execute(text("""
                ALTER TABLE usuarios 
                ADD COLUMN IF NOT EXISTS nome_completo VARCHAR,
                ADD COLUMN IF NOT EXISTS cargo VARCHAR,
                ADD COLUMN IF NOT EXISTS municipio VARCHAR,
                ADD COLUMN IF NOT EXISTS uf VARCHAR(2)
            """))
            
            # Migrar dados: se existe 'nome', copiar para 'nome_completo'
            db.execute(text("""
                UPDATE usuarios 
                SET nome_completo = COALESCE(nome, 'Usuário sem nome')
                WHERE nome_completo IS NULL
            """))
            
            # Tornar nome_completo obrigatório (após migrar dados)
            db.execute(text("""
                ALTER TABLE usuarios 
                ALTER COLUMN nome_completo SET NOT NULL
            """))
            
            # Remover coluna antiga 'nome' se existir
            try:
                db.execute(text("ALTER TABLE usuarios DROP COLUMN IF EXISTS nome"))
            except:
                pass  # Ignora se a coluna não existir
            
            db.commit()
            print("Migração concluída com sucesso!")
        else:
            print("Banco de dados já está atualizado.")
            
    except Exception as e:
        db.rollback()
        print(f"Erro ao migrar banco de dados: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate_db()


