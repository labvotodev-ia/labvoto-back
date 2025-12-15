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


def buscar_cargos_eleitos_partido(
    partido: str,
    abrangencia: str,
    territorio: str = None,
    municipio: str = None
) -> list[dict]:
    """
    Busca cargos eleitos de um partido no BigQuery baseado na abrangência.
    
    Args:
        partido: Sigla do partido (ex: NOVO, PT, PL)
        abrangencia: Nacional, Estadual ou Municipal
        territorio: Sigla da UF (para Estadual e Municipal) ou None (para Nacional)
        municipio: Nome do município (apenas para abrangência Municipal)
    
    Returns:
        Lista de dicionários com 'cargo' e 'total_cargos_eleitos'
    """
    client = get_bigquery_client()
    
    # Base da query
    query = """
        SELECT
            rc.cargo,
            COUNT(rc.cargo) AS total_cargos_eleitos
        FROM `endless-datum-477312-h2.labvoto.resultados_candidato` rc
        LEFT JOIN `endless-datum-477312-h2.labvoto.dir_municipios` mn 
            ON mn.id_municipio_tse = rc.id_municipio_tse
        WHERE 
            rc.ano IN (2012, 2016, 2020, 2024)
            AND rc.sigla_partido = @partido
            AND rc.resultado LIKE 'eleito%'
    """
    
    # Parâmetros base
    query_parameters = [
        bigquery.ScalarQueryParameter("partido", "STRING", partido.upper())
    ]
    
    # Adicionar filtros baseados na abrangência
    if abrangencia == "Nacional":
        query += """
            AND rc.sigla_uf IS NOT NULL
            AND mn.nome IS NOT NULL
        """
    elif abrangencia == "Estadual":
        if not territorio:
            raise ValueError("Para abrangência Estadual, o parâmetro 'territorio' (sigla_uf) é obrigatório")
        query += """
            AND rc.sigla_uf = @sigla_uf
            AND mn.nome IS NOT NULL
        """
        query_parameters.append(
            bigquery.ScalarQueryParameter("sigla_uf", "STRING", territorio.upper())
        )
    elif abrangencia == "Municipal":
        if not territorio:
            raise ValueError("Para abrangência Municipal, o parâmetro 'territorio' (sigla_uf) é obrigatório")
        if not municipio:
            raise ValueError("Para abrangência Municipal, o parâmetro 'municipio' é obrigatório")
        query += """
            AND rc.sigla_uf = @sigla_uf
            AND mn.nome = @municipio
        """
        query_parameters.append(
            bigquery.ScalarQueryParameter("sigla_uf", "STRING", territorio.upper())
        )
        query_parameters.append(
            bigquery.ScalarQueryParameter("municipio", "STRING", municipio)
        )
    
    # Finalizar query
    query += """
        GROUP BY
            rc.cargo
        ORDER BY
            total_cargos_eleitos DESC
    """
    
    # Configurar job com parâmetros
    job_config = bigquery.QueryJobConfig(
        query_parameters=query_parameters
    )
    
    # Executar query
    query_job = client.query(query, job_config=job_config)
    results = query_job.result()
    
    # Converter para lista de dicionários
    cargos_eleitos = []
    for row in results:
        cargos_eleitos.append({
            "cargo": row.cargo,
            "total_cargos_eleitos": row.total_cargos_eleitos
        })
    
    return cargos_eleitos
