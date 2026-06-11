import pandas as pd


def _empty_df(columns):
    return pd.DataFrame(columns=columns)


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


def _top_breakdown(df, column, metric_name, top_n=10):
    if column not in df.columns:
        return _empty_df(["category", "count", "metric"])

    out = (
        df[column]
        .astype(str)
        .value_counts()
        .head(top_n)
        .reset_index()
    )

    out.columns = ["category", "count"]
    out["metric"] = metric_name
    return out


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
        monthly_impact = df[impact_col].abs().sum()

    annualised_impact = monthly_impact * 12

    exception_breakdown = _top_breakdown(
        df,
        "exception_type",
        "Exceptions by Type",
    )

    product_col = None
    for col in ["product_name", "asset_type"]:
        if col in df.columns:
            product_col = col
            break

    product_breakdown = (
        _top_breakdown(df, product_col, "Top Products")
        if product_col
        else _empty_df(["category", "count", "metric"])
    )

    account_col = None
    for col in ["account_id", "billing_account_id"]:
        if col in df.columns:
            account_col = col
            break

    account_breakdown = (
        _top_breakdown(df, account_col, "Top Accounts")
        if account_col
        else _empty_df(["category", "count", "metric"])
    )

    impact_breakdown = _empty_df(["category", "impact"])

    if impact_col and product_col:
        impact_breakdown = (
            df.groupby(product_col)[impact_col]
            .sum()
            .abs()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
        )
        impact_breakdown.columns = ["category", "impact"]

    insight_rows = [
        {
            "metric": "Total Exceptions",
            "category": "Overall",
            "value": total_exceptions,
        },
        {
            "metric": "Estimated Monthly Impact",
            "category": "Financial",
            "value": round(float(monthly_impact), 2),
        },
        {
            "metric": "Estimated Annualised Impact",
            "category": "Financial",
            "value": round(float(annualised_impact), 2),
        },
        {
            "metric": "Impact Column Used",
            "category": "Metadata",
            "value": impact_col or "Not available",
        },
    ]

    for _, row in exception_breakdown.iterrows():
        insight_rows.append(
            {
                "metric": "Exception Type",
                "category": row["category"],
                "value": int(row["count"]),
            }
        )

    for _, row in product_breakdown.iterrows():
        insight_rows.append(
            {
                "metric": "Top Product",
                "category": row["category"],
                "value": int(row["count"]),
            }
        )

    for _, row in account_breakdown.iterrows():
        insight_rows.append(
            {
                "metric": "Top Account",
                "category": row["category"],
                "value": int(row["count"]),
            }
        )

    for _, row in impact_breakdown.iterrows():
        insight_rows.append(
            {
                "metric": "Product Impact",
                "category": row["category"],
                "value": round(float(row["impact"]), 2),
            }
        )

    insight_df = pd.DataFrame(insight_rows)

    summary = f"""
## Insight Dashboard

Use this dashboard to review exception volume, product concentration, account concentration and estimated financial impact.

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
        "product_breakdown": product_breakdown,
        "account_breakdown": account_breakdown,
        "impact_breakdown": impact_breakdown,
        "monthly_impact": monthly_impact,
        "annualised_impact": annualised_impact,
    }
