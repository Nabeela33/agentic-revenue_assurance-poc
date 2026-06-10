import re
import json

from utils.vertex_client import call_gemini
from utils.bigquery_client import run_sql


def extract_sql(response_text):
    """
    Extract SQL from Gemini response.
    """

    match = re.search(
        r"```sql\s*(.*?)```",
        response_text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if match:
        return match.group(1).strip().rstrip(";")

    idx = response_text.upper().find("SELECT")

    if idx >= 0:
        return response_text[idx:].strip().rstrip(";")

    raise ValueError("Developer Agent did not return SQL.")


def validate_sql(sql):
    """
    Allow only SELECT statements.
    """

    sql_upper = sql.upper()

    if not sql_upper.startswith("SELECT"):
        raise ValueError("Only SELECT statements are allowed.")

    forbidden = [
        "DELETE ",
        "UPDATE ",
        "INSERT ",
        "MERGE ",
        "DROP ",
        "TRUNCATE ",
        "CREATE ",
        "ALTER ",
    ]

    for keyword in forbidden:
        if keyword in sql_upper:
            raise ValueError(f"Unsafe SQL detected: {keyword.strip()}")

    return sql


def run_developer_agent(
    project_id,
    location,
    dataset,
    approved_design,
    metadata,
):
    """
    Developer Agent:
    - Reads approved design
    - Generates BigQuery SQL using Gemini
    - Executes SQL in BigQuery
    - Returns exception dataset
    """

    prompt = f"""
You are the Developer Agent for a telecom Revenue Assurance POC.

The user has approved the following control design:

{approved_design}

Available table metadata:

{json.dumps(metadata, indent=2)}

Generate ONE BigQuery Standard SQL SELECT query.

Rules:
1. Use only available tables and columns.
2. Use fully qualified table names:
   `{project_id}.{dataset}.table_name`
3. Return exception records only.
4. Add a column named exception_type.
5. Add a column named recommended_action.
6. Add estimated_monthly_impact or estimated_customer_impact if possible.
7. LIMIT 500.
8. Return SQL only inside a ```sql block.
"""

    response = call_gemini(
        project_id=project_id,
        location=location,
        prompt=prompt,
    )

    sql = extract_sql(response)

    sql = validate_sql(sql)

    exception_df = run_sql(
        project_id=project_id,
        sql=sql,
    )

    return {
        "generated_sql": sql,
        "exception_df": exception_df,
        "raw_response": response,
        "row_count": len(exception_df),
    }
