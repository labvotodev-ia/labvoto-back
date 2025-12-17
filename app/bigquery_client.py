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


def buscar_votos_partido(
    sigla_partido: str,
    sigla_uf: str,
    cargo: str,
    ano: int = 2024,
    turnos: list[int] = None
) -> list[dict]:
    """
    Busca votos de um partido por município com percentual de votos válidos.
    
    Args:
        sigla_partido: Sigla do partido (ex: PODE, PT, PL)
        sigla_uf: Sigla da UF (ex: AM, SP, RJ)
        cargo: Cargo (ex: prefeito, governador, presidente)
        ano: Ano da eleição (padrão: 2024)
        turnos: Lista de turnos (padrão: [1, 2])
    
    Returns:
        Lista de dicionários com os resultados da consulta
    """
    if turnos is None:
        turnos = [1, 2]
    
    client = get_bigquery_client()
    
    # Query adaptada - convertendo DECLARE para parâmetros do BigQuery
    # Como DECLARE não é suportado diretamente, vamos usar parâmetros e construir a query
    query = """
        WITH votos_partido AS (
          SELECT
            rcd.ano,
            rcd.turno,
            rcd.sigla_uf,
            rcd.id_municipio_tse,
            rcd.cargo,
            rcd.sigla_partido AS partido,
            SUM(rcd.votos) AS votos_partido
          FROM `basedosdados.br_tse_eleicoes.resultados_candidato` rcd
          WHERE rcd.ano = @ano_alvo
            AND rcd.turno IN UNNEST(@turnos)
            AND rcd.sigla_partido = @sigla_partido
            AND rcd.sigla_uf = @sigla_uf
            AND rcd.cargo = @cargo
            AND rcd.resultado LIKE 'eleito%'
          GROUP BY ano, turno, sigla_uf, id_municipio_tse, cargo, partido
        ),
        votos_validos_total AS (
          SELECT
            dvm.ano,
            dvm.turno,
            dvm.sigla_uf,
            dvm.id_municipio_tse,
            dvm.cargo,
            SUM(dvm.votos_validos) AS votos_validos
          FROM `basedosdados.br_tse_eleicoes.detalhes_votacao_municipio` dvm
          WHERE dvm.ano = @ano_alvo
            AND dvm.turno IN UNNEST(@turnos)
          GROUP BY ano, turno, sigla_uf, id_municipio_tse, cargo
        )
        SELECT
          v.ano,
          v.sigla_uf,
          v.id_municipio_tse,
          v.cargo,
          v.partido,
          v.votos_partido,
          t.votos_validos,
          SAFE_DIVIDE(v.votos_partido, t.votos_validos) AS prop_votos_validos,
          SAFE_MULTIPLY(SAFE_DIVIDE(v.votos_partido, t.votos_validos), 100) AS perc_votos_validos
        FROM votos_partido v
        LEFT JOIN votos_validos_total t
          USING (ano, turno, sigla_uf, id_municipio_tse, cargo)
        ORDER BY ano, sigla_uf, id_municipio_tse, cargo, perc_votos_validos DESC
    """
    
    # Parâmetros para evitar SQL injection
    query_parameters = [
        bigquery.ScalarQueryParameter("ano_alvo", "INT64", ano),
        bigquery.ArrayQueryParameter("turnos", "INT64", turnos),
        bigquery.ScalarQueryParameter("sigla_partido", "STRING", sigla_partido.upper()),
        bigquery.ScalarQueryParameter("sigla_uf", "STRING", sigla_uf.upper()),
        bigquery.ScalarQueryParameter("cargo", "STRING", cargo.lower())
    ]
    
    # Configurar job com parâmetros
    job_config = bigquery.QueryJobConfig(
        query_parameters=query_parameters
    )
    
    # Executar query
    query_job = client.query(query, job_config=job_config)
    results = query_job.result()
    
    # Converter para lista de dicionários
    votos_resultados = []
    for row in results:
        votos_resultados.append({
            "ano": row.ano,
            "sigla_uf": row.sigla_uf,
            "id_municipio_tse": row.id_municipio_tse,
            "cargo": row.cargo,
            "partido": row.partido,
            "votos_partido": row.votos_partido,
            "votos_validos": row.votos_validos,
            "prop_votos_validos": float(row.prop_votos_validos) if row.prop_votos_validos is not None else None,
            "perc_votos_validos": float(row.perc_votos_validos) if row.perc_votos_validos is not None else None
        })
    
    return votos_resultados


def buscar_custo_por_voto_eleitos(
    anos: list[int],
    cargos: list[str],
    siglas_uf: list[str],
    sigla_partido: str,
) -> list[dict]:
    """
    Executa a query de custo por voto para candidatos eleitos, unificando votos
    entre tabelas geral e municipal, e juntando com despesas.

    Args:
        anos: Lista de anos (ex: [2022])
        cargos: Lista de cargos (ex: ["deputado federal"])
        siglas_uf: Lista de UFs (ex: ["SP"])
        sigla_partido: Sigla do partido (ex: "PODE")

    Returns:
        Lista de dicionários com o resultado da query
    """
    if not anos:
        raise ValueError("O parâmetro 'anos' não pode estar vazio")
    if not cargos:
        raise ValueError("O parâmetro 'cargos' não pode estar vazio")
    if not siglas_uf:
        raise ValueError("O parâmetro 'siglas_uf' não pode estar vazio")
    if not sigla_partido or not sigla_partido.strip():
        raise ValueError("O parâmetro 'sigla_partido' é obrigatório")

    client = get_bigquery_client()

    query = """
        WITH votos_unificados AS (
          SELECT
            r.ano,
            r.cargo,
            r.sigla_uf,
            r.resultado,
            r.sigla_partido,
            r.sequencial_candidato,
            SUM(r.votos) AS votos
          FROM (
            SELECT
              ano,
              cargo,
              sigla_uf,
              resultado,
              sigla_partido,
              sequencial_candidato,
              CAST(NULL AS STRING) AS id_municipio,
              votos
            FROM `basedosdados.br_tse_eleicoes.resultados_candidato`
            UNION ALL
            SELECT
              ano,
              cargo,
              sigla_uf,
              resultado,
              sigla_partido,
              sequencial_candidato,
              id_municipio,
              votos
            FROM `basedosdados.br_tse_eleicoes.resultados_candidato_municipio`
          ) r
          WHERE r.ano IN UNNEST(@anos)
            AND r.cargo IN UNNEST(@cargos)
            AND r.sigla_partido = @sigla_partido
            AND r.resultado LIKE 'eleito%'
            AND r.sigla_uf IN UNNEST(@siglas_uf)
          GROUP BY 1, 2, 3, 4, 5, 6
        ),
        despesas AS (
          SELECT
            d.ano,
            d.sigla_uf,
            d.cargo,
            d.sequencial_candidato,
            SUM(d.valor_despesa) AS despesas_totais
          FROM `basedosdados.br_tse_eleicoes.despesas_candidato` d
          WHERE d.ano IN UNNEST(@anos)
            AND d.cargo IN UNNEST(@cargos)
            AND d.sigla_uf IN UNNEST(@siglas_uf)
          GROUP BY 1, 2, 3, 4
        )
        SELECT
          v.ano,
          v.cargo,
          v.sigla_uf,
          cd.sigla_partido,
          cd.numero AS numero_candidato,
          cd.nome_urna,
          v.votos,
          d.despesas_totais,
          SAFE_DIVIDE(d.despesas_totais, v.votos) AS custo_por_voto
        FROM votos_unificados v
        JOIN `basedosdados.br_tse_eleicoes.candidatos` cd
          ON cd.sequencial = v.sequencial_candidato
          AND cd.ano = v.ano
        LEFT JOIN despesas d
          ON d.ano = v.ano
          AND d.sigla_uf = v.sigla_uf
          AND d.cargo = v.cargo
          AND d.sequencial_candidato = v.sequencial_candidato
        ORDER BY v.ano, v.sigla_uf, v.votos DESC
    """

    query_parameters = [
        bigquery.ArrayQueryParameter("anos", "INT64", anos),
        bigquery.ArrayQueryParameter("cargos", "STRING", cargos),
        bigquery.ArrayQueryParameter("siglas_uf", "STRING", siglas_uf),
        bigquery.ScalarQueryParameter("sigla_partido", "STRING", sigla_partido.upper()),
    ]

    job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
    query_job = client.query(query, job_config=job_config)
    results = query_job.result()

    saida: list[dict] = []
    for row in results:
        saida.append(
            {
                "ano": row.ano,
                "cargo": row.cargo,
                "sigla_uf": row.sigla_uf,
                "sigla_partido": row.sigla_partido,
                "numero_candidato": int(row.numero_candidato) if row.numero_candidato is not None else None,
                "nome_urna": row.nome_urna,
                "votos": int(row.votos) if row.votos is not None else 0,
                "despesas_totais": float(row.despesas_totais) if row.despesas_totais is not None else None,
                "custo_por_voto": float(row.custo_por_voto) if row.custo_por_voto is not None else None,
            }
        )

    return saida


def buscar_distribuicao_fundo_eleitoral(
    anos: list[int],
    cargos: list[str],
    siglas_uf: list[str],
    sigla_partido: str,
) -> list[dict]:
    """
    Executa a query de distribuição de fundo eleitoral (FE/FP) por candidato,
    unificando votos e juntando com receitas públicas e despesas.

    Args:
        anos: Lista de anos (ex: [2022])
        cargos: Lista de cargos (ex: ["deputado federal"])
        siglas_uf: Lista de UFs (ex: ["SP"])
        sigla_partido: Sigla do partido (ex: "PODE")

    Returns:
        Lista de dicionários com o resultado da query
    """
    if not anos:
        raise ValueError("O parâmetro 'anos' não pode estar vazio")
    if not cargos:
        raise ValueError("O parâmetro 'cargos' não pode estar vazio")
    if not siglas_uf:
        raise ValueError("O parâmetro 'siglas_uf' não pode estar vazio")
    if not sigla_partido or not sigla_partido.strip():
        raise ValueError("O parâmetro 'sigla_partido' é obrigatório")

    client = get_bigquery_client()

    query = """
        WITH votos_unificados AS (
          SELECT
            r.ano,
            r.cargo,
            r.sigla_uf,
            r.resultado,
            r.sigla_partido,
            r.sequencial_candidato,
            SUM(r.votos) AS votos
          FROM (
            SELECT
              ano,
              cargo,
              sigla_uf,
              resultado,
              sigla_partido,
              sequencial_candidato,
              votos
            FROM `basedosdados.br_tse_eleicoes.resultados_candidato`
            UNION ALL
            SELECT
              ano,
              cargo,
              sigla_uf,
              resultado,
              sigla_partido,
              sequencial_candidato,
              votos
            FROM `basedosdados.br_tse_eleicoes.resultados_candidato_municipio`
          ) r
          WHERE r.ano IN UNNEST(@anos)
            AND r.cargo IN UNNEST(@cargos)
            AND r.sigla_partido = @sigla_partido
            AND r.sigla_uf IN UNNEST(@siglas_uf)
          GROUP BY 1, 2, 3, 4, 5, 6
        ),
        receitas_publicas AS (
          SELECT
            rc.ano,
            rc.sigla_uf,
            rc.sequencial_candidato,
            SUM(rc.valor_receita) AS valor_fe_fp
          FROM `basedosdados.br_tse_eleicoes.receitas_candidato` rc
          WHERE rc.ano IN UNNEST(@anos)
            AND rc.sigla_uf IN UNNEST(@siglas_uf)
            AND (
              LOWER(rc.fonte_receita) LIKE '%fundo partid_rio%'
              OR LOWER(rc.fonte_receita) LIKE '%fundo especial%'
              OR LOWER(rc.fonte_receita) LIKE '%fefc%'
            )
          GROUP BY 1, 2, 3
        ),
        despesas AS (
          SELECT
            d.ano,
            d.sigla_uf,
            d.cargo,
            d.sequencial_candidato,
            SUM(d.valor_despesa) AS despesas_totais
          FROM `basedosdados.br_tse_eleicoes.despesas_candidato` d
          WHERE d.ano IN UNNEST(@anos)
            AND d.cargo IN UNNEST(@cargos)
            AND d.sigla_uf IN UNNEST(@siglas_uf)
          GROUP BY 1, 2, 3, 4
        )
        SELECT
          v.ano,
          v.cargo,
          v.sigla_uf,
          v.resultado,
          cd.sigla_partido,
          cd.numero AS numero_candidato,
          cd.nome_urna,
          v.votos,
          rec.valor_fe_fp,
          d.despesas_totais,
          SAFE_DIVIDE(d.despesas_totais, v.votos) AS custo_por_voto
        FROM votos_unificados v
        JOIN `basedosdados.br_tse_eleicoes.candidatos` cd
          ON cd.sequencial = v.sequencial_candidato
          AND cd.ano = v.ano
        LEFT JOIN receitas_publicas rec
          ON rec.ano = v.ano
          AND rec.sigla_uf = v.sigla_uf
          AND rec.sequencial_candidato = v.sequencial_candidato
        LEFT JOIN despesas d
          ON d.ano = v.ano
          AND d.sigla_uf = v.sigla_uf
          AND d.cargo = v.cargo
          AND d.sequencial_candidato = v.sequencial_candidato
        ORDER BY v.ano, v.sigla_uf, v.votos DESC
    """

    query_parameters = [
        bigquery.ArrayQueryParameter("anos", "INT64", anos),
        bigquery.ArrayQueryParameter("cargos", "STRING", cargos),
        bigquery.ArrayQueryParameter("siglas_uf", "STRING", siglas_uf),
        bigquery.ScalarQueryParameter("sigla_partido", "STRING", sigla_partido.upper()),
    ]

    job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
    query_job = client.query(query, job_config=job_config)
    results = query_job.result()

    saida: list[dict] = []
    for row in results:
        saida.append(
            {
                "ano": row.ano,
                "cargo": row.cargo,
                "sigla_uf": row.sigla_uf,
                "resultado": row.resultado,
                "sigla_partido": row.sigla_partido,
                "numero_candidato": int(row.numero_candidato) if row.numero_candidato is not None else None,
                "nome_urna": row.nome_urna,
                "votos": int(row.votos) if row.votos is not None else 0,
                "valor_fe_fp": float(row.valor_fe_fp) if row.valor_fe_fp is not None else None,
                "despesas_totais": float(row.despesas_totais) if row.despesas_totais is not None else None,
                "custo_por_voto": float(row.custo_por_voto) if row.custo_por_voto is not None else None,
            }
        )

    return saida