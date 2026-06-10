import json
from utils.vertex_client import call_gemini


def run_design_agent(project_id, location, user_request, control_family, metadata, mapping):
    prompt = f"""
You are the Design Agent for a telecom Revenue Assurance POC.

Your job:
- Understand the user's control request.
- Use the available BigQuery metadata and mapping context.
- Propose a control design.
- Do NOT write SQL.
- Do NOT execute logic.
- Do NOT invent tables or columns.

User request:
{user_request}

Control family:
{control_family}

Available table metadata:
{json.dumps(metadata, indent=2)}

Mapping context:
{mapping}

Return markdown with:

## Proposed Control Design

### 1. Control Name
### 2. Objective
### 3. Control Type
### 4. Source Tables
### 5. Candidate Join Keys
### 6. Base Population
### 7. Exception Definition
### 8. Output Fields
### 9. Impact Estimate
### 10. Assumptions
### 11. Approval Question

End with:
Please approve this design before the Developer Agent builds the control.
"""
    return call_gemini(project_id, location, prompt)
