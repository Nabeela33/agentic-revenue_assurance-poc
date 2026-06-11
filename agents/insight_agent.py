import pandas as pd


def _find_impact_column(df):
    for col in ["estimated_monthly_impact", "monthly_impact", "estimated_customer_impact", "charge_amount"]:
        if col in df.columns:
            return col
    return None


def _normalise_exception_type(value):
    value = str(value).upper()
    if "SNB" in value or "SERVICE NO BILL" in value:
        return "SNB"
    if "BNS" in value or "BILL NO SERVICE" in value:
        return "BNS"
    return "Other"


def run_insight_agent(project_id, location, approved_design, generated_sql, exception_df, total_reconciled_records=0):
    df = exception_df.copy()

    if "exception_type" in df.columns:
        df["exception_category"] = df["exception_type"].apply(_normalise_exception_type)
    else:
        df["exception_category"] = "Other"

    impact_col = _find_impact_column(df)
    if impact_col:
        df[impact_col] = pd.to_numeric(df[impact_col], errors="coerce").fillna(0)
    else:
        impact_col = "estimated_monthly_impact"
        df[impact_col] = 0.0

    snb_df = df[df["exception_category"] == "SNB"].copy()
    bns_df = df[df["exception_category"] == "BNS"].copy()

    snb_count = len(snb_df)
    bns_count = len(bns_df)
    total_exceptions = len(df)

    snb_impact = float(snb_df[impact_col].abs().sum()) if not snb_df.empty else 0.0
    bns_impact = float(bns_df[impact_col].abs().sum()) if not bns_df.empty else 0.0
    monthly_impact = snb_impact + bns_impact
    annualised_impact = monthly_impact * 12

    exception_breakdown = pd.DataFrame(
        [{"category": "SNB", "count": snb_count}, {"category": "BNS", "count": bns_count}]
    )

    if "product_name" in df.columns:
        impact_breakdown = (
            df.groupby("product_name")[impact_col]
            .sum()
            .abs()
            .sort_values(ascending=False)
            .reset_index()
        )
        impact_breakdown.columns = ["category", "impact"]

        grouped = (
            df.pivot_table(index="product_name", columns="exception_category", values=impact_col, aggfunc="sum", fill_value=0)
            .reset_index()
        )
        if "SNB" not in grouped.columns:
            grouped["SNB"] = 0
        if "BNS" not in grouped.columns:
            grouped["BNS"] = 0
        grouped["Total Impact"] = grouped["SNB"].abs() + grouped["BNS"].abs()
        product_control_breakdown = grouped.rename(columns={"product_name": "product"})[
            ["product", "SNB", "BNS", "Total Impact"]
        ].sort_values("Total Impact", ascending=False)
    else:
        impact_breakdown = pd.DataFrame(columns=["category", "impact"])
        product_control_breakdown = pd.DataFrame(columns=["product", "SNB", "BNS", "Total Impact"])

    top_exceptions = df.sort_values(impact_col, ascending=False).head(10).copy()

    insight_rows = [
        {"section": "KPI", "metric": "Total Reconciled Records", "category": "Overall", "value": int(total_reconciled_records)},
        {"section": "KPI", "metric": "SNB Exceptions", "category": "SNB", "value": int(snb_count)},
        {"section": "KPI", "metric": "BNS Exceptions", "category": "BNS", "value": int(bns_count)},
        {"section": "KPI", "metric": "SNB Monthly Impact", "category": "SNB", "value": round(snb_impact, 2)},
        {"section": "KPI", "metric": "BNS Monthly Impact", "category": "BNS", "value": round(bns_impact, 2)},
        {"section": "KPI", "metric": "Total Monthly Impact", "category": "Financial", "value": round(monthly_impact, 2)},
        {"section": "KPI", "metric": "Annualised Impact", "category": "Financial", "value": round(annualised_impact, 2)},
    ]

    for _, row in impact_breakdown.iterrows():
        insight_rows.append(
            {"section": "Financial Impact by Product", "metric": "Monthly Impact", "category": row["category"], "value": round(float(row["impact"]), 2)}
        )

    return {
        "summary": "Insight dashboard generated.",
        "insight_df": pd.DataFrame(insight_rows),
        "exception_breakdown": exception_breakdown,
        "impact_breakdown": impact_breakdown,
        "product_control_breakdown": product_control_breakdown,
        "top_exceptions": top_exceptions,
        "exception_count": total_exceptions,
        "total_reconciled_records": int(total_reconciled_records),
        "snb_count": snb_count,
        "bns_count": bns_count,
        "snb_impact": snb_impact,
        "bns_impact": bns_impact,
        "monthly_impact": monthly_impact,
        "annualised_impact": annualised_impact,
    }
