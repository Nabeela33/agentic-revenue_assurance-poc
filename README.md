# Agentic Revenue Assurance POC

Telecom Revenue Assurance POC using:

- One Siebel source data
- Antillia billing data
- BigQuery
- Vertex AI Gemini
- Streamlit
- Cloud Run

## Agent Flow

1. Design Agent proposes the control design based on user request, table metadata and mapping context.
2. User approves the design.
3. Developer Agent generates BigQuery SQL using Vertex AI and executes it.
4. User reviews and approves the control output.
5. Insight Agent creates business summary and downloadable insights.

## Environment Variables

PROJECT_ID=telecom-data-lake  
BQ_DATASET=ra_poc  
GCS_BUCKET=telecom-data-lake-ra-poc  
LOCATION=europe-west2  

## Deploy

```bash
gcloud builds submit --tag gcr.io/telecom-data-lake/agentic-ra-poc

gcloud run deploy agentic-ra-poc \
  --image gcr.io/telecom-data-lake/agentic-ra-poc \
  --platform managed \
  --region europe-west2 \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=telecom-data-lake,BQ_DATASET=ra_poc,GCS_BUCKET=telecom-data-lake-ra-poc,LOCATION=europe-west2
