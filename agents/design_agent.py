import json
from utils.vertex_client import call_gemini


def run_design_agent(project_id, location, user_request, control_family, metadata, mapping, feedback=""):
    prompt = f"""
You are the Design Agent for a telecom Revenue Assurance POC.

Your role is to create a DATA MAPPING / CONTROL MODEL only.
Do not write SQL.
Do not give long explanation.
Do not write an essay.
Do not execute anything.
Do not invent tables or columns.

User request:
{user_request}

Control family:
{control_family}

User feedback, if this is regeneration:
{feedback}

Available table metadata:
{json.dumps(metadata, indent=2)}

Mapping context:
{mapping}

Return concise markdown with these exact sections:

## Data Mapping Model

| Layer | Source System | Table | Key Field | Business Meaning |
|---|---|---|---|---|

## Cross-System Mapping

| One Siebel Field | Antillia Field | Match Type | Purpose |
|---|---|---|---|

## Control Model

| Item | Design |
|---|---|

Rows should include:
- Control name
- Control objective
- Base population
- Match logic
- Exception logic
- Impact field
- Output fields

## Assumptions

Use max 5 bullet points.

## Approval

End with:
Approve this design or provide feedback to regenerate.
"""

    return call_gemini(project_id, location, prompt)
