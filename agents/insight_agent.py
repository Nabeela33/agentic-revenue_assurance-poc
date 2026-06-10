import json
import pandas as pd

from utils.vertex_client import call_gemini


def run_insight_agent(
    project_id,
    location,
    approved_design,
    generated_sql,
    exception_df,
):
    """
    Insight Agent:
    - Reads approved design
    - Reviews generated SQL
    - Analyses exception output
    - Produces business summary
    - Produces downloadable insight dataframe
    """

    preview_records = exception_df.head(50).to_dict(orient="records")

    impact_col = ""
    monthly_impact = 0.0

    for col in [
        "estimated_monthly_impact",
        "monthly_impact",
        "estimated_customer_impact",
        "charge_amount",
    ]:
        if col in exception_df.columns:
            impact_col = col
            monthly_impact = (
                pd.to_numeric(exception_df[col], errors="coerce")
                .fillna(0)
                .abs()
                .sum()
            )
            break

    prompt = f"""
You are the Insight Agent for a telecom Revenue Assurance POC.

Your job:
- Analyse the approved control output.
- Summarise findings in business language.
- Highlight financial impact.
- Identify risk themes.
- Recommend next actions.
- Avoid inventing numbers that are not in the data.

Approved design:
{approved_design}

Generated SQL:
{generated_sql}

Exception count:
{len(exception_df)}

Impact column used:
{impact_col}

Estimated monthly impact:
{monthly_impact}

Sample exception records:
{json.dumps(preview_records, indent=2, default=str)}

Return markdown with:

## Executive Summary

## What The Control Found

## Estimated Financial Impact

## Key Risk Themes

## Recommended Actions

## Productionisation Notes
"""

    summary = call_gemini(
        project_id=project_id,
        location=location,
        prompt=prompt,
    )

    insight_rows = [
        {
            "metric": "exception_count",
            "value": len(exception_df),
        },
        {
            "metric": "impact_column_used",
            "value": impact_col,
        },
        {
            "metric": "estimated_monthly_impact",
            "value": round(float(monthly_impact), 2),
        },
        {
            "metric": "estimated_annualised_impact",
            "value": round(float(monthly_impact) * 12, 2),
        },
    ]

    for col in [
        "exception_type",
        "product_name",
        "asset_type",
        "account_id",
        "billing_account_id",
    ]:
        if col in exception_df.columns:
            top_values = exception_df[col].astype(str).value_counts().head(10)

            for key, count in top_values.items():
                insight_rows.append(
                    {
                        "metric": f"top_{col}",
                        "value": f"{key}: {count}",
                    }
                )

    insight_df = pd.DataFrame(insight_rows)

    return {
        "summary": summary,
        "insight_df": insight_df,
    }
