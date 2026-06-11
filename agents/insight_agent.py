import pandas as pd


def _find_impact_column(df):
    for col in [
        "estimated_monthly_impact",
        "monthly_impact",
        "estimated_customer_impact",
        "charge_amount",
    ]:
        if col in df.columns:
            return col
    return None


def _first_existing_column(df, candidates):
    for col in candidates:
        if col in df.columns:
            return col
    return None


def run_insight_agent(
    project_id,
    location,
    approved_design,
    generated_sql,
    exception_df,
):
    df = exception_df.copy()

    total_exceptions = len(df)

    impact_col = _find_impact_column(df)
    monthly_impact = 0.0

    if impact_col:
        df[impact_col] = pd.to_numeric(df[impact_col], errors="coerce").fillna(0)
        monthly_impact = float(df[impact_col].abs().sum())

    annualised_impact = monthly_impact * 12

    exception_breakdown = pd.DataFrame(columns=["category", "count"])
    if "exception_type" in df.columns:
        exception_breakdown = (
            df["exception_type"]
            .astype(str)
            .value_counts()
            .reset_index()
        )
        exception_breakdown.columns = ["category", "count"]

    product_col = _first_existing_column(df, ["product_name", "asset_type"])
    account_col = _first_existing_column(df, ["account_id", "billing_account_id"])

    impact_breakdown = pd.DataFrame(columns=["category", "impact"])

    if impact_col and product_col:
        impact_breakdown = (
            df.groupby(product_col)[impact_col]
            .sum()
            .abs()
            .sort_values(ascending=False)
            .head(8)
            .reset_index()
        )
        impact_breakdown.columns = ["category", "impact"]
    elif impact_col and account_col:
        impact_breakdown = (
            df.groupby(account_col)[impact_col]
            .sum()
            .abs()
            .sort_values(ascending=False)
            .head(8)
            .reset_index()
        )
        impact_breakdown.columns = ["category", "impact"]

    top_exceptions = df.head(10).copy()

    insight_rows = [
        {
            "section": "KPI",
            "metric": "Total Exceptions",
            "category": "Overall",
            "value": total_exceptions,
        },
        {
            "section": "KPI",
            "metric": "Estimated Monthly Impact",
            "category": "Financial",
            "value": round(monthly_impact, 2),
        },
        {
            "section": "KPI",
            "metric": "Estimated Annualised Impact",
            "category": "Financial",
            "value": round(annualised_impact, 2),
        },
    ]

    for _, row in exception_breakdown.iterrows():
        insight_rows.append(
            {
                "section": "Exception Mix",
                "metric": "Exception Count",
                "category": row["category"],
                "value": int(row["count"]),
            }
        )

    for _, row in impact_breakdown.iterrows():
        insight_rows.append(
            {
                "section": "Financial Impact",
                "metric": "Impact",
                "category": row["category"],
                "value": round(float(row["impact"]), 2),
            }
        )

    insight_df = pd.DataFrame(insight_rows)

    summary = f"""
## Insight Dashboard

| KPI | Value |
|---|---:|
| Total Exceptions | {total_exceptions:,} |
| Estimated Monthly Impact | £{monthly_impact:,.2f} |
| Estimated Annualised Impact | £{annualised_impact:,.2f} |
"""

    return {
        "summary": summary,
        "insight_df": insight_df,
        "exception_breakdown": exception_breakdown,
        "impact_breakdown": impact_breakdown,
        "top_exceptions": top_exceptions,
        "exception_count": total_exceptions,
        "monthly_impact": monthly_impact,
        "annualised_impact": annualised_impact,
    }
