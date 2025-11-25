# LabVotoAI - Backend API

Backend desenvolvido com FastAPI e PostgreSQL para o projeto LabVotoAI.

## Pré-requisitos

- Python 3.8+
- Docker e Docker Compose
- pip (gerenciador de pacotes Python)

## Configuração

### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

### 2. Configurar variáveis de ambiente (Opcional)

**Se estiver usando Docker:** Não é necessário criar o arquivo `.env`, pois o `docker-compose.yml` já tem as configurações.

**Se estiver usando Python localmente:** Crie um arquivo `.env` na raiz do projeto (ou copie o `.env.example`):

```bash
# Copiar o arquivo de exemplo
cp .env.example .env
```

Ou crie manualmente um arquivo `.env` com:
```env
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
DB_NAME=labvotoai
```

**Nota:** No Windows, arquivos que começam com ponto (`.env`) podem estar ocultos. Use `ls -Force` no PowerShell ou habilite "Mostrar arquivos ocultos" no Explorador de Arquivos.

### 3. Subir o banco de dados

```bash
docker-compose up -d
```

Isso irá iniciar o PostgreSQL em um container Docker na porta 5432.

### 4. Rodar a aplicação

#### Opção 1: Usando Docker (Recomendado - Não precisa instalar Python)
```bash
docker-compose up
```

Isso irá iniciar tanto o banco de dados quanto a API. Acesse `http://localhost:8000/docs`

#### Opção 2: Usando Python localmente

**Primeiro, certifique-se de que o Python está instalado:**
```bash
python --version
```

Se não estiver instalado, veja o arquivo `INSTALACAO.md` para instruções.

**Instalar dependências:**
```bash
pip install -r requirements.txt
```

**Iniciar a aplicação:**
```bash
# Opção A: Usando o script run.py
python run.py

# Opção B: Usando uvicorn diretamente
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Opção C: Usando o script batch (Windows)
start_server.bat
```

A aplicação estará disponível em `http://localhost:8000`

### 5. Verificar conexão com banco (opcional)

Antes de rodar a aplicação, você pode testar a conexão:
```bash
python test_connection.py
```

## Documentação da API

Após iniciar a aplicação, acesse:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Endpoints

- `GET /` - Mensagem de boas-vindas
- `GET /health` - Verificação de saúde da API e conexão com banco de dados

## Estrutura do Projeto

```
labvotoai/
├── app/
│   ├── __init__.py
│   ├── main.py          # Aplicação principal FastAPI
│   └── database.py      # Configuração do banco de dados
├── docker-compose.yml   # Configuração do PostgreSQL e API
├── Dockerfile           # Imagem Docker para a API
├── requirements.txt     # Dependências Python
├── .env                 # Variáveis de ambiente (opcional, veja seção 2)
├── .env.example         # Exemplo de arquivo .env
└── start_server.bat     # Script para iniciar no Windows
```

## Solução de Problemas

### Swagger não está acessível
- Verifique se a aplicação está rodando (veja os logs no terminal)
- Acesse `http://localhost:8000/docs` (não esqueça do `/docs`)
- Verifique se não há outro processo usando a porta 8000

### Erro de conexão com banco
- Verifique se o container está rodando: `docker ps`
- Verifique os logs do container: `docker logs labvotoai_db`
- Se estiver usando Python localmente, verifique se o arquivo `.env` existe (veja seção 2)
- As configurações padrão são: usuário `postgres`, senha `postgres`, banco `labvotoai`

