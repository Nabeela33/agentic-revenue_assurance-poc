import os
from datetime import datetime

import pandas as pd
import streamlit as st

from agents.design_agent import run_design_agent
from agents.developer_agent import run_developer_agent
from agents.insight_agent import run_insight_agent
from utils.bigquery_client import get_metadata, preview
from utils.gcs_client import load_mapping


st.set_page_config(page_title="Agentic Revenue Assurance POC", layout="wide")

PROJECT_ID = os.getenv("PROJECT_ID", "telecom-data-lake")
DATASET = os.getenv("BQ_DATASET", "ra_poc")
BUCKET = os.getenv("GCS_BUCKET", "telecom-data-lake-ra-poc")
LOCATION = os.getenv("LOCATION", "global")

TABLES = [
    "siebel_accounts",
    "siebel_assets",
    "siebel_orders",
    "antillia_accounts",
    "antillia_products",
]

st.title("Agentic Revenue Assurance POC")
st.caption("One Siebel vs Antillia | Vertex AI + BigQuery + Streamlit + Cloud Run")


@st.cache_data(ttl=600)
def load_metadata():
    return get_metadata(PROJECT_ID, DATASET)


@st.cache_data(ttl=600)
def load_mapping_ref():
    return load_mapping(BUCKET)


metadata = load_metadata()
mapping_reference = load_mapping_ref()

with st.sidebar:
    st.header("Control Request")
    control_family = st.selectbox("Control Family", ["Completeness", "Accuracy"])
    user_request = st.text_area(
        "Request",
        "Design a completeness control to identify Service No Bill between One Siebel and Antillia.",
        height=130,
    )
    design_feedback = st.text_area("Design feedback / change request", "", height=80)
    run_design = st.button("Run Design Agent", type="primary")

tabs = st.tabs(["Data Overview", "Design Agent", "Developer Agent", "Insight Agent", "Audit Trail"])


with tabs[0]:
    st.subheader("Source Data Overview")
    cols = st.columns(5)
    for idx, table in enumerate(TABLES):
        row_count = metadata.get(table, {}).get("row_count", 0)
        cols[idx].metric(table, f"{row_count:,}")

    st.markdown("### Preview Data")
    selected_table = st.selectbox("Select table", TABLES)

    try:
        preview_df = preview(PROJECT_ID, DATASET, selected_table)
        st.dataframe(preview_df, use_container_width=True)
    except Exception as error:
        st.error(f"Could not preview table: {error}")


with tabs[1]:
    st.subheader("Design Agent")
    st.caption("Creates the data mapping model and control model. It does not write SQL.")

    if run_design:
        with st.spinner("Design Agent is generating data mapping and control model..."):
            design_output = run_design_agent(
                project_id=PROJECT_ID,
                location=LOCATION,
                user_request=user_request,
                control_family=control_family,
                metadata=metadata,
                mapping=mapping_reference,
                feedback=design_feedback,
            )
            st.session_state["design_output"] = design_output
            st.session_state["design_created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state["design_approved"] = False
            st.session_state.pop("developer_result", None)
            st.session_state["control_approved"] = False
            st.session_state.pop("insights", None)

    if "design_output" in st.session_state:
        st.markdown(st.session_state["design_output"])
        design_col1, design_col2 = st.columns(2)

        with design_col1:
            if st.button("Approve Design", type="primary"):
                st.session_state["design_approved"] = True
                st.session_state["design_approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success("Design approved. Developer Agent can now build the control.")

        with design_col2:
            if st.button("Regenerate Design"):
                st.session_state.pop("design_output", None)
                st.session_state["design_approved"] = False
                st.session_state.pop("developer_result", None)
                st.session_state["control_approved"] = False
                st.session_state.pop("insights", None)
                st.rerun()
    else:
        st.info("Enter a request in the sidebar and run the Design Agent.")


with tabs[2]:
    st.subheader("Developer Agent")
    st.caption("Runs reconciliation and returns the exception table. SQL is generated internally and not shown.")

    if not st.session_state.get("design_approved"):
        st.warning("Approve the Design Agent output first.")
    else:
        developer_feedback = st.text_area("Developer feedback / change request", "", height=80)

        if st.button("Run Developer Agent", type="primary"):
            with st.spinner("Developer Agent is reconciling One Siebel and Antillia in BigQuery..."):
                developer_result = run_developer_agent(
                    project_id=PROJECT_ID,
                    location=LOCATION,
                    dataset=DATASET,
                    approved_design=st.session_state["design_output"],
                    metadata=metadata,
                    feedback=developer_feedback,
                )
                st.session_state["developer_result"] = developer_result
                st.session_state["developer_ran_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state["control_approved"] = False
                st.session_state.pop("insights", None)

        if "developer_result" in st.session_state:
            result = st.session_state["developer_result"]
            exception_df = result["exception_df"]
            impact = 0.0

            for column in ["estimated_monthly_impact", "monthly_impact", "estimated_customer_impact", "charge_amount"]:
                if column in exception_df.columns:
                    impact = pd.to_numeric(exception_df[column], errors="coerce").fillna(0).abs().sum()
                    break

            col1, col2 = st.columns(2)
            col1.metric("Exceptions Found", f"{len(exception_df):,}")
            col2.metric("Estimated Monthly Impact", f"£{impact:,.2f}")

            st.markdown("### Reconciliation Output")
            st.dataframe(exception_df, use_container_width=True)

            st.download_button(
                "Download Control Output",
                exception_df.to_csv(index=False).encode("utf-8"),
                file_name="control_output.csv",
                mime="text/csv",
            )

            control_col1, control_col2 = st.columns(2)
            with control_col1:
                if st.button("Approve Control Output", type="primary"):
                    st.session_state["control_approved"] = True
                    st.session_state["control_approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    st.success("Control output approved. Insight Agent can now run.")

            with control_col2:
                if st.button("Regenerate Control"):
                    st.session_state.pop("developer_result", None)
                    st.session_state["control_approved"] = False
                    st.session_state.pop("insights", None)
                    st.rerun()


with tabs[3]:
    st.subheader("Insight Agent")
    st.caption("Creates a dashboard from the approved reconciliation output.")

    if not st.session_state.get("control_approved"):
        st.warning("Approve the Developer Agent output first.")
    else:
        if st.button("Run Insight Agent", type="primary"):
            with st.spinner("Insight Agent is preparing the dashboard..."):
                insights = run_insight_agent(
                    project_id=PROJECT_ID,
                    location=LOCATION,
                    approved_design=st.session_state["design_output"],
                    generated_sql=st.session_state["developer_result"]["generated_sql"],
                    exception_df=st.session_state["developer_result"]["exception_df"],
                )
                st.session_state["insights"] = insights
                st.session_state["insight_ran_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if "insights" in st.session_state:
            insights = st.session_state["insights"]
            insight_df = insights["insight_df"]
            total_exceptions = int(insights.get("exception_count", len(st.session_state["developer_result"]["exception_df"])))
            monthly_impact = float(insights.get("monthly_impact", 0))
            annualised_impact = float(insights.get("annualised_impact", 0))

            st.markdown("### Insight Dashboard")
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Total Exceptions", f"{total_exceptions:,}")
            kpi2.metric("Monthly Impact", f"£{monthly_impact:,.2f}")
            kpi3.metric("Annualised Impact", f"£{annualised_impact:,.2f}")

            chart_col1, chart_col2 = st.columns(2)
            with chart_col1:
                st.markdown("#### Exceptions by Type")
                exception_breakdown = insights.get("exception_breakdown", pd.DataFrame())
                if not exception_breakdown.empty:
                    st.bar_chart(exception_breakdown.set_index("category")["count"], use_container_width=True)
                else:
                    st.info("No exception type breakdown available.")

            with chart_col2:
                st.markdown("#### Top Products")
                product_breakdown = insights.get("product_breakdown", pd.DataFrame())
                if not product_breakdown.empty:
                    st.bar_chart(product_breakdown.set_index("category")["count"], use_container_width=True)
                else:
                    st.info("No product breakdown available.")

            chart_col3, chart_col4 = st.columns(2)
            with chart_col3:
                st.markdown("#### Top Accounts")
                account_breakdown = insights.get("account_breakdown", pd.DataFrame())
                if not account_breakdown.empty:
                    st.bar_chart(account_breakdown.set_index("category")["count"], use_container_width=True)
                else:
                    st.info("No account breakdown available.")

            with chart_col4:
                st.markdown("#### Financial Impact by Product")
                impact_breakdown = insights.get("impact_breakdown", pd.DataFrame())
                if not impact_breakdown.empty:
                    st.bar_chart(impact_breakdown.set_index("category")["impact"], use_container_width=True)
                else:
                    st.info("No impact breakdown available.")

            st.markdown("### Insight Table")
            st.dataframe(insight_df, use_container_width=True)

            st.download_button(
                "Download Insights",
                insight_df.to_csv(index=False).encode("utf-8"),
                file_name="ra_insights.csv",
                mime="text/csv",
            )


with tabs[4]:
    st.subheader("Audit Trail")
    audit = {
        "project_id": PROJECT_ID,
        "dataset": DATASET,
        "bucket": BUCKET,
        "location": LOCATION,
        "design_created_at": st.session_state.get("design_created_at", ""),
        "design_approved": st.session_state.get("design_approved", False),
        "design_approved_at": st.session_state.get("design_approved_at", ""),
        "developer_ran_at": st.session_state.get("developer_ran_at", ""),
        "control_approved": st.session_state.get("control_approved", False),
        "control_approved_at": st.session_state.get("control_approved_at", ""),
        "insight_ran_at": st.session_state.get("insight_ran_at", ""),
    }
    st.json(audit)
