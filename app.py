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

st.markdown("""
<style>
.main-title {background: linear-gradient(90deg, #2F4F7F 0%, #5B2A86 100%); padding: 24px 28px; border-radius: 18px; color: white; margin-bottom: 18px;}
.main-title h1 {color: white; margin-bottom: 0px;}
.main-title p {color: #E8E8F0; margin-top: 8px; font-size: 15px;}
h2, h3 {color: #2F4F7F;}
div[data-testid="stMetric"] {background: #F5F7FB; border: 1px solid #E3E8F0; padding: 16px; border-radius: 14px; box-shadow: 0 1px 4px rgba(0,0,0,0.04);}
div.stButton > button:first-child {border-radius: 10px; font-weight: 600;}
section[data-testid="stSidebar"] {background-color: #F1F4F8;}
</style>
""", unsafe_allow_html=True)

PROJECT_ID = os.getenv("PROJECT_ID", "telecom-data-lake")
DATASET = os.getenv("BQ_DATASET", "ra_poc")
BUCKET = os.getenv("GCS_BUCKET", "telecom-data-lake-ra-poc")
LOCATION = os.getenv("LOCATION", "global")

TABLES = ["siebel_accounts", "siebel_assets", "siebel_orders", "antillia_accounts", "antillia_products"]
PRODUCT_OPTIONS = ["Cloud Voice", "SIP Trunk", "PSTN Line", "Broadband", "FTTP Broadband", "FTTC Broadband", "Ethernet Circuit", "MPLS Circuit", "Mobile Voice", "SD-WAN"]
CONTROL_OPTIONS = ["Service No Bill (SNB)", "Bill No Service (BNS)"]

st.markdown("""
<div class="main-title">
    <h1>Agentic Revenue Assurance POC</h1>
    
</div>
""", unsafe_allow_html=True)


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
    selected_controls = st.multiselect("Controls", CONTROL_OPTIONS, default=CONTROL_OPTIONS)
    selected_products = st.multiselect("Products", PRODUCT_OPTIONS, default=["Cloud Voice", "SIP Trunk", "PSTN Line", "Broadband"])
    user_request = st.text_area("Request", "Identify SNB and BNS exceptions between One Siebel and Antillia for the selected products.", height=110)
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
    st.caption("Creates a stable data mapping model and control model. It does not write SQL.")

    if run_design:
        with st.spinner("Design Agent is generating data mapping and control model..."):
            design_output = run_design_agent(PROJECT_ID, LOCATION, user_request, control_family, metadata, mapping_reference, design_feedback, selected_controls, selected_products)
            st.session_state["design_output"] = design_output
            st.session_state["selected_controls"] = selected_controls
            st.session_state["selected_products"] = selected_products
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
        st.info("Choose controls/products in the sidebar and run the Design Agent.")

with tabs[2]:
    st.subheader("Developer Agent")
    st.caption("Runs reconciliation and returns the exception table. SQL is generated internally and not shown.")

    if not st.session_state.get("design_approved"):
        st.warning("Approve the Design Agent output first.")
    else:
        developer_feedback = st.text_area("Developer feedback / change request", "", height=80)
        if st.button("Run Developer Agent", type="primary"):
            with st.spinner("Developer Agent is reconciling One Siebel and Antillia in BigQuery..."):
                developer_result = run_developer_agent(PROJECT_ID, LOCATION, DATASET, st.session_state["design_output"], metadata, developer_feedback, st.session_state.get("selected_controls", CONTROL_OPTIONS), st.session_state.get("selected_products", []))
                st.session_state["developer_result"] = developer_result
                st.session_state["developer_ran_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state["control_approved"] = False
                st.session_state.pop("insights", None)

        if "developer_result" in st.session_state:
            result = st.session_state["developer_result"]
            exception_df = result["exception_df"]
            impact = 0.0
            if "estimated_monthly_impact" in exception_df.columns:
                impact = pd.to_numeric(exception_df["estimated_monthly_impact"], errors="coerce").fillna(0).abs().sum()

            snb_count = exception_df["exception_type"].astype(str).str.contains("SNB", case=False).sum() if "exception_type" in exception_df.columns else 0
            bns_count = exception_df["exception_type"].astype(str).str.contains("BNS", case=False).sum() if "exception_type" in exception_df.columns else 0

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Reconciled", f"{result.get('total_reconciled_records', 0):,}")
            col2.metric("SNB Exceptions", f"{snb_count:,}")
            col3.metric("BNS Exceptions", f"{bns_count:,}")
            col4.metric("Monthly Impact", f"£{impact:,.2f}")

            st.markdown("### Reconciliation Output")
            st.dataframe(exception_df, use_container_width=True)
            st.download_button("Download Control Output", exception_df.to_csv(index=False).encode("utf-8"), file_name="control_output.csv", mime="text/csv")

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
    st.caption("Creates a concise executive dashboard from the approved reconciliation output.")

    if not st.session_state.get("control_approved"):
        st.warning("Approve the Developer Agent output first.")
    else:
        if st.button("Run Insight Agent", type="primary"):
            with st.spinner("Insight Agent is preparing the dashboard..."):
                insights = run_insight_agent(PROJECT_ID, LOCATION, st.session_state["design_output"], st.session_state["developer_result"]["generated_sql"], st.session_state["developer_result"]["exception_df"], st.session_state["developer_result"].get("total_reconciled_records", 0))
                st.session_state["insights"] = insights
                st.session_state["insight_ran_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if "insights" in st.session_state:
            insights = st.session_state["insights"]
            insight_df = insights["insight_df"]

            st.markdown("### Insight Dashboard")
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("Total Reconciled", f"{insights.get('total_reconciled_records', 0):,}")
            kpi2.metric("SNB Exceptions", f"{insights.get('snb_count', 0):,}")
            kpi3.metric("BNS Exceptions", f"{insights.get('bns_count', 0):,}")
            kpi4.metric("Monthly Impact", f"£{insights.get('monthly_impact', 0):,.2f}")

            kpi5, kpi6, kpi7 = st.columns(3)
            kpi5.metric("SNB Impact", f"£{insights.get('snb_impact', 0):,.2f}")
            kpi6.metric("BNS Impact", f"£{insights.get('bns_impact', 0):,.2f}")
            kpi7.metric("Annualised Impact", f"£{insights.get('annualised_impact', 0):,.2f}")

            st.divider()
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1:
                st.markdown("#### SNB vs BNS Exception Mix")
                exception_breakdown = insights.get("exception_breakdown", pd.DataFrame())
                if not exception_breakdown.empty:
                    st.bar_chart(exception_breakdown.set_index("category")["count"], use_container_width=True)

            with chart_col2:
                st.markdown("#### Financial Impact by Product")
                impact_breakdown = insights.get("impact_breakdown", pd.DataFrame())
                if not impact_breakdown.empty:
                    st.bar_chart(impact_breakdown.set_index("category")["impact"], use_container_width=True)

            product_control_breakdown = insights.get("product_control_breakdown", pd.DataFrame())
            if not product_control_breakdown.empty:
                st.markdown("### Product Impact by Control")
                st.dataframe(product_control_breakdown, use_container_width=True)

            st.markdown("### Top Exceptions")
            top_exceptions = insights.get("top_exceptions", pd.DataFrame())
            if not top_exceptions.empty:
                st.dataframe(top_exceptions, use_container_width=True)

            st.markdown("### Revenue Assurance Report")
            st.dataframe(insight_df, use_container_width=True)
            st.download_button("Download Revenue Assurance Report", insight_df.to_csv(index=False).encode("utf-8"), file_name="revenue_assurance_report.csv", mime="text/csv")

with tabs[4]:
    st.subheader("Audit Trail")
    audit = {
        "project_id": PROJECT_ID,
        "dataset": DATASET,
        "bucket": BUCKET,
        "location": LOCATION,
        "selected_controls": st.session_state.get("selected_controls", []),
        "selected_products": st.session_state.get("selected_products", []),
        "design_created_at": st.session_state.get("design_created_at", ""),
        "design_approved": st.session_state.get("design_approved", False),
        "design_approved_at": st.session_state.get("design_approved_at", ""),
        "developer_ran_at": st.session_state.get("developer_ran_at", ""),
        "control_approved": st.session_state.get("control_approved", False),
        "control_approved_at": st.session_state.get("control_approved_at", ""),
        "insight_ran_at": st.session_state.get("insight_ran_at", ""),
    }
    st.json(audit)
