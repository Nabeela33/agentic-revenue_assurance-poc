import os
from datetime import datetime

import pandas as pd
import streamlit as st

from agents.design_agent import run_design_agent
from agents.developer_agent import run_developer_agent
from agents.insight_agent import run_insight_agent
from utils.bigquery_client import get_metadata, preview
from utils.gcs_client import load_mapping


st.set_page_config(
    page_title="Agentic Revenue Assurance POC",
    layout="wide",
)

PROJECT_ID = os.getenv("PROJECT_ID", "telecom-data-lake")
DATASET = os.getenv("BQ_DATASET", "ra_poc")
BUCKET = os.getenv("GCS_BUCKET", "telecom-data-lake-ra-poc")
LOCATION = os.getenv("LOCATION", "europe-west2")

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

    control_family = st.selectbox(
        "Control Family",
        ["Completeness", "Accuracy"],
    )

    user_request = st.text_area(
        "Request",
        "Design a completeness control to identify Service No Bill between One Siebel and Antillia.",
        height=130,
    )

    run_design = st.button("Run Design Agent", type="primary")


tabs = st.tabs(
    [
        "Data Overview",
        "Design Agent",
        "Developer Agent",
        "Insight Agent",
        "Audit Trail",
    ]
)


with tabs[0]:
    st.subheader("BigQuery Source Tables")

    cols = st.columns(5)

    for idx, table in enumerate(TABLES):
        row_count = metadata.get(table, {}).get("row_count", 0)
        cols[idx].metric(table, f"{row_count:,}")

    st.markdown("### Table Metadata")

    metadata_rows = []

    for table in TABLES:
        table_meta = metadata.get(table, {})
        metadata_rows.append(
            {
                "table": table,
                "row_count": table_meta.get("row_count", 0),
                "columns": ", ".join(table_meta.get("columns", [])),
            }
        )

    st.dataframe(pd.DataFrame(metadata_rows), use_container_width=True)

    st.markdown("### Preview Data")

    selected_table = st.selectbox("Select table", TABLES)

    try:
        preview_df = preview(PROJECT_ID, DATASET, selected_table)
        st.dataframe(preview_df, use_container_width=True)
    except Exception as error:
        st.error(f"Could not preview table: {error}")


with tabs[1]:
    st.subheader("Design Agent")

    if run_design:
        with st.spinner("Design Agent is analysing the request, metadata and mapping context..."):
            design_output = run_design_agent(
                project_id=PROJECT_ID,
                location=LOCATION,
                user_request=user_request,
                control_family=control_family,
                metadata=metadata,
                mapping=mapping_reference,
            )

            st.session_state["design_output"] = design_output
            st.session_state["design_created_at"] = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

    if "design_output" in st.session_state:
        st.markdown(st.session_state["design_output"])

        if st.button("Approve Design", type="primary"):
            st.session_state["design_approved"] = True
            st.session_state["design_approved_at"] = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            st.success("Design approved. Developer Agent can now build the control.")
    else:
        st.info("Enter a request in the sidebar and run the Design Agent.")


with tabs[2]:
    st.subheader("Developer Agent")

    if not st.session_state.get("design_approved"):
        st.warning("Approve the Design Agent output first.")
    else:
        if st.button("Run Developer Agent", type="primary"):
            with st.spinner("Developer Agent is generating SQL and executing it in BigQuery..."):
                developer_result = run_developer_agent(
                    project_id=PROJECT_ID,
                    location=LOCATION,
                    dataset=DATASET,
                    approved_design=st.session_state["design_output"],
                    metadata=metadata,
                )

                st.session_state["developer_result"] = developer_result
                st.session_state["developer_ran_at"] = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

        if "developer_result" in st.session_state:
            result = st.session_state["developer_result"]
            exception_df = result["exception_df"]

            st.markdown("### Generated SQL")
            st.code(result["generated_sql"], language="sql")

            impact = 0.0

            for column in [
                "estimated_monthly_impact",
                "monthly_impact",
                "estimated_customer_impact",
                "charge_amount",
            ]:
                if column in exception_df.columns:
                    impact = (
                        pd.to_numeric(exception_df[column], errors="coerce")
                        .fillna(0)
                        .abs()
                        .sum()
                    )
                    break

            col1, col2 = st.columns(2)
            col1.metric("Exceptions Found", f"{len(exception_df):,}")
            col2.metric("Estimated Monthly Impact", f"£{impact:,.2f}")

            st.markdown("### Control Output")
            st.dataframe(exception_df, use_container_width=True)

            st.download_button(
                "Download Control Output",
                exception_df.to_csv(index=False).encode("utf-8"),
                file_name="control_output.csv",
                mime="text/csv",
            )

            if st.button("Approve Control Output", type="primary"):
                st.session_state["control_approved"] = True
                st.session_state["control_approved_at"] = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                st.success("Control output approved. Insight Agent can now run.")


with tabs[3]:
    st.subheader("Insight Agent")

    if not st.session_state.get("control_approved"):
        st.warning("Approve the Developer Agent output first.")
    else:
        if st.button("Run Insight Agent", type="primary"):
            with st.spinner("Insight Agent is generating business summary and downloadable insights..."):
                insights = run_insight_agent(
                    project_id=PROJECT_ID,
                    location=LOCATION,
                    approved_design=st.session_state["design_output"],
                    generated_sql=st.session_state["developer_result"]["generated_sql"],
                    exception_df=st.session_state["developer_result"]["exception_df"],
                )

                st.session_state["insights"] = insights
                st.session_state["insight_ran_at"] = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

        if "insights" in st.session_state:
            st.markdown(st.session_state["insights"]["summary"])

            insight_df = st.session_state["insights"]["insight_df"]

            st.markdown("### Downloadable Insight File")
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
