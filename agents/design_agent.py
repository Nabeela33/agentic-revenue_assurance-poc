def _format_list(values):
    if not values:
        return "All products"
    return ", ".join(values)


def run_design_agent(project_id, location, user_request, control_family, metadata, mapping, feedback="", controls=None, products=None):
    controls = controls or ["Service No Bill (SNB)", "Bill No Service (BNS)"]
    products = products or []
    controls_text = ", ".join(controls)
    products_text = _format_list(products)

    include_snb = any("SNB" in c or "Service No Bill" in c for c in controls)
    include_bns = any("BNS" in c or "Bill No Service" in c for c in controls)

    control_names = []
    if include_snb:
        control_names.append("Service No Bill (SNB)")
    if include_bns:
        control_names.append("Bill No Service (BNS)")
    control_name_text = " + ".join(control_names) if control_names else "No control selected"

    exception_logic = []
    if include_snb:
        exception_logic.append("SNB: Active Siebel service asset has no matching active Antillia billing product/account.")
    if include_bns:
        exception_logic.append("BNS: Active Antillia billing product has no matching active Siebel service asset.")
    exception_text = "<br>".join(exception_logic) if exception_logic else "No exception condition selected."

    model = f"""
## 1. Source Data Model

| System | Entity | Table | Primary / Business Key | Important Fields | Role in Control |
|---|---|---|---|---|---|
| One Siebel | Account | siebel_accounts | account_id | account_id, account_name, account_type, region, status | Customer context |
| One Siebel | Service Asset | siebel_assets | asset_id, service_number | asset_id, account_id, asset_type, asset_status, service_number | Service inventory population |
| One Siebel | Order | siebel_orders | order_id, asset_id | order_id, account_id, asset_id, order_status, total_price | Commercial/order context |
| Antillia | Billing Account | antillia_accounts | billing_account_id, service_number | billing_account_id, account_id, service_number, status | Billing account context |
| Antillia | Billing Product | antillia_products | billing_product_id, asset_id | billing_product_id, billing_account_id, asset_id, product_name, charge_amount, status | Billing product population |

## 2. Relationship Model Within Systems

| System | Parent Table | Child Table | Join Key | Cardinality | Purpose |
|---|---|---|---|---|---|
| One Siebel | siebel_accounts | siebel_assets | account_id | One-to-Many | Link customer account to service inventory |
| One Siebel | siebel_assets | siebel_orders | asset_id | One-to-Many | Link provisioned service to order activity |
| Antillia | antillia_accounts | antillia_products | billing_account_id | One-to-Many | Link billing account to billable products |

## 3. Cross-System Mapping Model

| Mapping Level | One Siebel Table | One Siebel Field | Antillia Table | Antillia Field | Match Strength | Purpose |
|---|---|---|---|---|---|---|
| Service | siebel_assets | service_number | antillia_accounts | service_number | Primary | Service-level reconciliation key |
| Asset | siebel_assets | asset_id | antillia_products | asset_id | Secondary | Technical asset matching key |
| Account | siebel_accounts / siebel_assets | account_id | antillia_accounts | account_id | Context | Customer/account validation |
| Product | siebel_assets | asset_type | antillia_products | product_name | Validation | Product-level consistency and impact grouping |
| Status | siebel_assets | asset_status | antillia_products | status | Validation | Active/Ceased billing alignment |

## 4. Control Model

| Control Component | Design |
|---|---|
| Control Name | {control_name_text} |
| Control Type | {control_family} |
| Products in Scope | {products_text} |
| Base Population | Active records from service inventory and billing, filtered by selected products |
| SNB Population | Active Siebel assets from `siebel_assets` |
| BNS Population | Active Antillia billing products from `antillia_products` joined to `antillia_accounts` |
| Primary Match Key | `siebel_assets.service_number` ↔ `antillia_accounts.service_number` |
| Secondary Match Key | `siebel_assets.asset_id` ↔ `antillia_products.asset_id` |
| Exception Condition | {exception_text} |
| Impact Field / Proxy | BNS uses `antillia_products.charge_amount`; SNB uses product-level monthly charge proxy |
| Output Columns | exception_type, account_id, billing_account_id, asset_id, service_number, product_name, status, estimated_monthly_impact, recommended_action |

## 5. Control Summary

| Metric | Design Value |
|---|---|
| Controls Requested | {controls_text} |
| Product Filter | {products_text} |
| Reconciliation Level | Service + Asset level |
| Expected Output | Combined SNB and BNS exception table |
| Approval Required | Yes, before Developer Agent runs reconciliation |

## 6. Approval

Approve this data model/control model or provide feedback to regenerate.
"""
    if feedback:
        model += f"\n\n**Applied Feedback:** {feedback}\n"
    return model
