from utils.bigquery_client import run_sql

PRODUCT_PROXY = {
    "PSTN Line": 18.50,
    "PSTN": 18.50,
    "Broadband": 32.00,
    "BB": 32.00,
    "FTTP Broadband": 45.00,
    "FTTC Broadband": 38.00,
    "SIP Trunk": 14.00,
    "Ethernet Circuit": 220.00,
    "MPLS Circuit": 180.00,
    "Cloud Voice": 9.50,
    "Mobile Voice": 24.00,
    "SD-WAN": 150.00,
}


def _sql_list(values):
    return ", ".join("'" + str(v).replace("'", "\\'") + "'" for v in values)


def _proxy_case(field_name):
    parts = ["CASE"]
    for product, price in PRODUCT_PROXY.items():
        parts.append(f"WHEN LOWER({field_name}) = LOWER('{product}') THEN {price}")
    parts.append("ELSE 30.00 END")
    return "\n            ".join(parts)


def _build_product_filter(products, field_name):
    if not products:
        return "1=1"
    return f"{field_name} IN ({_sql_list(products)})"


def run_developer_agent(project_id, location, dataset, approved_design, metadata, feedback="", controls=None, products=None):
    controls = controls or ["Service No Bill (SNB)", "Bill No Service (BNS)"]
    products = products or []

    include_snb = any("SNB" in c or "Service No Bill" in c for c in controls)
    include_bns = any("BNS" in c or "Bill No Service" in c for c in controls)

    product_filter_siebel = _build_product_filter(products, "a.asset_type")
    product_filter_antillia = _build_product_filter(products, "bp.product_name")
    proxy_case = _proxy_case("a.asset_type")

    queries = []

    if include_snb:
        queries.append(f"""
        SELECT
            'SNB - Service No Bill' AS exception_type,
            'One Siebel' AS source_system,
            a.account_id AS account_id,
            CAST(NULL AS STRING) AS billing_account_id,
            a.asset_id AS asset_id,
            a.service_number AS service_number,
            a.asset_type AS product_name,
            a.asset_status AS status,
            CAST(NULL AS FLOAT64) AS charge_amount,
            CAST(({proxy_case}) AS FLOAT64) AS estimated_monthly_impact,
            'Create or correct billing product in Antillia for active Siebel service.' AS recommended_action
        FROM `{project_id}.{dataset}.siebel_assets` a
        LEFT JOIN `{project_id}.{dataset}.antillia_accounts` ba
            ON a.service_number = ba.service_number
        LEFT JOIN `{project_id}.{dataset}.antillia_products` bp
            ON ba.billing_account_id = bp.billing_account_id
            OR a.asset_id = bp.asset_id
        WHERE LOWER(a.asset_status) = 'active'
          AND ({product_filter_siebel})
          AND bp.billing_product_id IS NULL
        """)

    if include_bns:
        queries.append(f"""
        SELECT
            'BNS - Bill No Service' AS exception_type,
            'Antillia' AS source_system,
            ba.account_id AS account_id,
            bp.billing_account_id AS billing_account_id,
            bp.asset_id AS asset_id,
            ba.service_number AS service_number,
            bp.product_name AS product_name,
            bp.status AS status,
            CAST(bp.charge_amount AS FLOAT64) AS charge_amount,
            CAST(bp.charge_amount AS FLOAT64) AS estimated_monthly_impact,
            'Validate billing product and cease/correct if no active Siebel service exists.' AS recommended_action
        FROM `{project_id}.{dataset}.antillia_products` bp
        JOIN `{project_id}.{dataset}.antillia_accounts` ba
            ON bp.billing_account_id = ba.billing_account_id
        LEFT JOIN `{project_id}.{dataset}.siebel_assets` a
            ON bp.asset_id = a.asset_id
            OR ba.service_number = a.service_number
        WHERE LOWER(bp.status) = 'active'
          AND ({product_filter_antillia})
          AND a.asset_id IS NULL
        """)

    if not queries:
        raise ValueError("No controls selected. Select SNB, BNS, or both.")

    sql = "\nUNION ALL\n".join(queries) + "\nLIMIT 500"
    exception_df = run_sql(project_id=project_id, sql=sql)

    total_reconciled_sql = f"""
    SELECT
        (
            SELECT COUNT(*)
            FROM `{project_id}.{dataset}.siebel_assets` a
            WHERE LOWER(a.asset_status) = 'active'
              AND ({product_filter_siebel})
        )
        +
        (
            SELECT COUNT(*)
            FROM `{project_id}.{dataset}.antillia_products` bp
            WHERE LOWER(bp.status) = 'active'
              AND ({product_filter_antillia})
        ) AS total_reconciled_records
    """
    total_df = run_sql(project_id=project_id, sql=total_reconciled_sql)
    total_reconciled_records = int(total_df.iloc[0]["total_reconciled_records"])

    return {
        "generated_sql": sql,
        "exception_df": exception_df,
        "raw_response": "Deterministic reconciliation logic executed.",
        "row_count": len(exception_df),
        "total_reconciled_records": total_reconciled_records,
    }
