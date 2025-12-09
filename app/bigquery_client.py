import os
from google.cloud import bigquery
from google.oauth2 import service_account

# Configuração do BigQuery
PROJECT_ID = "endless-datum-477312-h2"
DATASET_ID = "labvoto"
TABLE_CANDIDATOS = f"{PROJECT_ID}.{DATASET_ID}.candidatos"


def get_bigquery_client():
    """
    Inicializa e retorna um cliente BigQuery.
    
    A autenticação é feita via:
    1. Variável de ambiente GOOGLE_APPLICATION_CREDENTIALS (caminho do JSON)
    2. Ou variável GOOGLE_CREDENTIALS_JSON (conteúdo JSON direto - para Cloud Run)
    """
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    
    if credentials_json:
        # Para Cloud Run: credenciais JSON direto na variável de ambiente
        import json
        credentials_info = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(credentials_info)
        return bigquery.Client(credentials=credentials, project=PROJECT_ID)
    elif credentials_path:
        # Para desenvolvimento local: caminho do arquivo JSON
        credentials = service_account.Credentials.from_service_account_file(credentials_path)
        return bigquery.Client(credentials=credentials, project=PROJECT_ID)
    else:
        # Tenta usar credenciais padrão do ambiente (ADC)
        return bigquery.Client(project=PROJECT_ID)


def buscar_candidatos_por_nome(termo: str, limit: int = 100) -> list[dict]:
    """
    Busca candidatos pelo nome ou nome_urna usando busca parcial (LIKE).
    
    Args:
        termo: Termo de busca (nome completo, parcial ou sobrenome)
        limit: Limite de resultados (padrão: 100)
    
    Returns:
        Lista de dicionários com os dados dos candidatos
    """
    client = get_bigquery_client()
    
    # Query com busca parcial case-insensitive
    query = f"""
        SELECT *
        FROM `{TABLE_CANDIDATOS}`
        WHERE LOWER(nome) LIKE LOWER(@termo)
           OR LOWER(nome_urna) LIKE LOWER(@termo)
        LIMIT @limit
    """
    
    # Parâmetros para evitar SQL injection
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("termo", "STRING", f"%{termo}%"),
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
        ]
    )
    
    # Executar query
    query_job = client.query(query, job_config=job_config)
    results = query_job.result()
    
    # Converter para lista de dicionários
    candidatos = []
    for row in results:
        candidatos.append(dict(row))
    
    return candidatos

