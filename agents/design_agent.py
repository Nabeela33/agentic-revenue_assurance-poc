import json
from utils.vertex_client import call_gemini


def run_design_agent(
    project_id,
    location,
    user_request,
    control_family,
    metadata,
    mapping,
    feedback="",
):
    prompt = f"""
You are the Design Agent for a telecom Revenue Assurance POC.

Your output must be a DATA MODEL and CONTROL MODEL only.

Hard rules:
- Do not write an essay.
- Do not write SQL.
- Do not explain concepts.
- Do not invent tables or columns.
- Use only tables and columns from metadata.
- Output must be concise and structured.
- Use markdown tables only.
- If user feedback is provided, revise the model using that feedback.

User request:
{user_request}

Control family:
{control_family}

User feedback:
{feedback}

Available BigQuery metadata:
{json.dumps(metadata, indent=2)}

Mapping context:
{mapping}

Return only the following sections.

## 1. Source Data Model

| System | Entity | Table | Primary / Business Key | Important Fields | Role in Control |
|---|---|---|---|---|---|

Rules for this table:
- Include only tables required for the selected control.
- Entity examples: Account, Order, Service Asset, Billing Account, Billing Product.
- Important fields should be comma-separated column names only.
- Role in Control should be short.

## 2. Relationship Model Within Systems

| System | Parent Table | Child Table | Join Key | Cardinality | Purpose |
|---|---|---|---|---|---|

Rules:
- Show how One Siebel tables join to each other.
- Show how Antillia tables join to each other.
- Include only relationships useful for the control.

## 3. Cross-System Mapping Model

| Mapping Level | One Siebel Table | One Siebel Field | Antillia Table | Antillia Field | Match Strength | Purpose |
|---|---|---|---|---|---|---|

Rules:
- Mapping Level examples: Service, Asset, Account, Order, Product, Status.
- Match Strength must be one of: Primary, Secondary, Context, Validation.
- For SNB/BNS, service-level mapping should usually be primary if service_number exists.
- Do not include impossible mappings.

## 4. Control Model

| Control Component | Design |
|---|---|

Must include exactly these rows:
| Control Name | ... |
| Control Type | ... |
| Base Population | ... |
| Match Population | ... |
| Primary Match Key | ... |
| Secondary Match Key | ... |
| Exception Condition | ... |
| Impact Field / Proxy | ... |
| Output Columns | ... |

## 5. Review Points

| Review Point | Why It Matters |
|---|---|

Include max 5 review points.

## 6. Approval

Approve this data model/control model or provide feedback to regenerate.
"""

    return call_gemini(project_id, location, prompt)
