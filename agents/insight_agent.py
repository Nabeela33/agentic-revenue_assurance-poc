import pandas as pd


def run_insight_agent(
    project_id,
    location,
    approved_design,
    generated_sql,
    exception_df,
):
    """
    Insight Agent:
    - Creates insight tables for charts/visuals
    - Does not write long narrative
    - Produces downloadable insight dataframe
    """

    df = exception_df.copy()

    insight_rows = []

    total_exceptions = len(df)

    impact_col = ""
    monthly_impact = 0.0

    for col in [
        "estimated_monthly_impact",
        "monthly_impact",
        "estimated_customer_impact",
        "charge_amount",
    ]:
        if col in df.columns:
            impact_col = col
            monthly_impact = (
                pd.to_numeric(df[col], errors="coerce")
                .fillna(0)
                .abs()
                .sum()
            )
            break

    insight_rows.append(
        {
            "metric": "Total Exceptions",
            "category": "Overall",
            "value": total_exceptions,
        }
    )

    insight_rows.append(
        {
            "metric": "Estimated Monthly Impact",
            "category": "Financial",
            "value": round(float(monthly_impact), 2),
        }
    )

    insight_rows.append(
        {
            "metric": "Estimated Annualised Impact",
            "category": "Financial",
            "value": round(float(monthly_impact) * 12, 2),
        }
    )

    if "exception_type" in df.columns:
        for key, value in df["exception_type"].astype(str).value_counts().items():
            insight_rows.append(
                {
                    "metric": "Exception Type",
                    "category": key,
                    "value": int(value),
                }
            )

    for col in [
        "product_name",
        "asset_type",
        "account_id",
        "billing_account_id",
    ]:
        if col in df.columns:
            top_values = df[col].astype(str).value_counts().head(10)

            for key, value in top_values.items():
                insight_rows.append(
                    {
                        "metric": f"Top {col}",
                        "category": key,
                        "value": int(value),
                    }
                )

    insight_df = pd.DataFrame(insight_rows)

    summary = f"""
## Insight Summary

| Metric | Value |
|---|---:|
| Total exceptions | {total_exceptions:,} |
| Estimated monthly impact | £{monthly_impact:,.2f} |
| Estimated annualised impact | £{monthly_impact * 12:,.2f} |

Use the charts below to review exception distribution, product impact and account concentration.
"""

    return {
        "summary": summary,
        "insight_df": insight_df,
    }
