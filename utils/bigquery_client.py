from google.cloud import bigquery


def get_metadata(project_id, dataset):
    client = bigquery.Client(project=project_id)

    tables = [
        "siebel_accounts",
        "siebel_assets",
        "siebel_orders",
        "antillia_accounts",
        "antillia_products",
    ]

    metadata = {}

    for table_name in tables:
        table_id = f"{project_id}.{dataset}.{table_name}"
        table = client.get_table(table_id)

        metadata[table_name] = {
            "row_count": table.num_rows,
            "columns": [field.name for field in table.schema],
            "schema": [
                {
                    "name": field.name,
                    "type": field.field_type,
                    "mode": field.mode,
                }
                for field in table.schema
            ],
        }

    return metadata


def preview(project_id, dataset, table_name):
    client = bigquery.Client(project=project_id)

    query = f"""
    SELECT *
    FROM `{project_id}.{dataset}.{table_name}`
    LIMIT 20
    """

    return client.query(query).to_dataframe()


def run_sql(project_id, sql):
    client = bigquery.Client(project=project_id)
    return client.query(sql).to_dataframe()
