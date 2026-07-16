# Document Reconciliation Protocol

Apply this protocol **only when user-uploaded documents are present** to determine which data to use for each manifest input. When no documents are present, skip this entire protocol and follow the manifest's declared source priority directly (datamart first → user paste → AI estimate → ask).

## Calibrate trust by document origin

Trust the values in a document according to where the document came from:

- **Operational sources** (rent roll, T-12, bank statement, property management export): **High confidence** — these are actual performance.
- **Third-party validated reports** (appraisal, Phase I, survey): **High confidence for facts within scope** (e.g., an appraisal's unit count is trustworthy; its 10-year exit cap projection is still a projection).
- **Marketing / offering materials** (OM, broker package, broker pro forma): **Physical facts are reliable** (units, SF, year built). **Projections require scrutiny** — they are the seller's assumptions, not facts.
- **User-created models** (the client's prior underwriting spreadsheets, scratch pro formas): treat values as **user assumptions, not facts**. Do not promote them above datamart for physical facts or current operations.

## The three reconciliation rules

For each manifest input, classify the field type and apply the matching rule.

### Rule 1 — Physical facts

**Applies to:** unit count, rentable SF, bed/bath mix, year built, year renovated, lot size, structure type.

**Action:** Use the document's value. Note datamart variance only if the difference is **greater than 5%**.

If you adopt the document's value over the datamart's, record `source_class: resolved_document` and `source_detail: "<doc type> dated <date>, Rule 1"`. If the variance exceeded 5%, surface a one-line note in the gaps section of the narrative — framed neutrally.

### Rule 2 — Current operations

**Applies to:** in-place rents (per unit type), current physical occupancy, T-12 actual expenses, current GPR, current vacancy & credit loss, T-12 line-item operating expenses.

**Action:** Prefer the document if it is **dated within 90 days**. Otherwise use the datamart.

When adopting the document, state in the source audit: *"Using <source> dated <date>"*. Record `source_class: resolved_document` and `source_detail: "<doc type> dated <date>, Rule 2"`.

### Rule 3 — Projections

**Applies to:** pro forma rents, projected expense ratios, exit cap assumptions, rent growth, expense growth, stabilized occupancy targets — anything forward-looking.

**Action:** **Flag but do not adopt.** Surface the document's projection in the gap-filling form (step 3 of the main flow) and let the user choose. State to the user: *"Document projects <X>; I'll use this unless you prefer market-derived estimates."*

If the user picks the document's value, record `source_class: resolved_document` with `source_detail: "<doc type>, Rule 3 — user-confirmed"`. If the user picks the market value, record `resolved_ai_estimate` or `resolved_user_paste` as applicable.

### Market data

**Applies to:** cap rate benchmarks, rent comparables, sale comparables, market vacancy, submarket rent growth.

**Action:** **Always prefer the datamart.** Market data should be systematically sourced. If the document presents materially different market data, note it as a one-liner in the gaps section but do not let it override the datamart.

## Tone for variance notes

Frame variances **neutrally**. Differences usually reflect timing or methodology, not errors.

- ✓ *"Unit count of 142 per the OM differs from our recorded 138 units. Using 142 per the offering materials — please confirm."*
- ✗ Avoid: *"The OM overstates..."* / *"Our data contradicts..."* / *"The broker is wrong about..."*

## Reading dates

A document's relevance is bounded by its date.

- For **Rule 2 (current ops)**: 90 days is the threshold. Older T-12s or rent rolls fall back to the datamart.
- For **Rule 3 (projections)**: any date is acceptable as a flag-and-defer.
- For **Rule 1 (physical facts)**: dates rarely matter — a building's unit count doesn't change.

If a document has no date visible, ask the user for it before applying Rule 2. Do not assume the document is current.

## Cross-reference with the source_detail field

Every manifest input you write to the payload must carry a `source_detail` string that lets a later reader reconstruct provenance. When a document drove the value, that string must include both the **document type** and the **rule applied** — e.g.:

- `"OM dated 2026-03-15, Rule 1"` (physical fact from OM)
- `"rent roll dated 2026-04-30, Rule 2"` (current ops from rent roll)
- `"broker pro forma, Rule 3 — user-confirmed"` (projection from OM that the user accepted)

This makes the source audit at the end of the narrative reconstructable without re-reading every document.
