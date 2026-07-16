# Multifamily Comps — Retrieval & Selection Instructions

Read this file when the manifest or workflow requires sales comps or rent comps for the subject property.

---

## Sales Comps

Your job is to find multifamily sales comps for the subject property.

**Retrieval:** Query property sales within the last 3 years, at progressively wider geographies until the pool reaches 10. Start with zipcode (limit 25), then census place (limit 20), then county (limit 20). Maximum 3 queries — stop as soon as any single query returns 10 or more.

Work entirely on the `property_mfr` entity. For both the screen and the ranking, pull two topics together in a **single query call** — both are non-own-table, so no separate calls are needed:

 1. **`mf_property_attributes`** — carries the sale fields (`latest_sale_date`, `latest_sale_price`, `latest_sale_price_per_unit`), the coordinates (`latitude`, `longitude`), and every ranking field (`unit_count`, `building_style`, `year_built`, `year_renovated`, `improvements_rating`, `rent_type`, `household_restrictions`, `property_type`).
 2. **`mf_amenities`** — `community_amenities` and `unit_amenities`, returned as **JSON strings keyed by category** (parse them; they are not plain text).

 **Do not** pull `mf_sales_history`: its only three fields (`latest_sale_date`, `latest_sale_price`, `latest_sale_price_per_unit`) are duplicated verbatim inside `mf_property_attributes`, so it adds nothing.

 ### Screening

 Query MF properties whose most recent sale falls within the last 3 years, at progressively wider geographies until the pool reaches 10.
 
 1. **Sale window.** Filter on `mf_property_attributes.latest_sale_date >= (today − 3 years)`. Only the single most-recent transaction per property is stored — there is no multi-sale history — so a property whose last trade predates the window is simply absent, and you cannot recover an older sale for a property that has since resold.
 2. **Geography progression** (widen only as needed; swap the geography FK each step):
    - **Zipcode** (`zipcode_id`) — limit 25
    - **Census place** (`census_place_id`) — limit 20
    - **County** (`county_id`) — limit 20
 3. **Stop rule.** Maximum 3 queries — stop as soon as any single query returns 10 or more.
 4. **Always-on filters** (apply in every screen query):
- Require `latest_sale_price IS_NOT_NULL` — a row can carry a sale date but a null price, which is useless for a comp.
- Restrict `property_type` to the subject's class (**default `RENTAL`**) — `CONDO`/`COOP` "sales" reflect individual-unit transactions, not whole-asset trades.
- Exclude `building_style` values `SINGLE_FAMILY_HOME` and `MOBILE_HOME_RV_PARK` unless the subject is itself one of these; even within `property_type = RENTAL` the screen returns scattered single-family and 1–2-unit records. Consider a minimum `unit_count` floor aligned to the subject.

## Refine the pool

Calculate distance from subject for all returned properties and keep the closest 15 for filtering.
**Selection (4–6 comps):**

- **Exclude:** Properties with a different `rent_type` (AFFORDABLE vs. MARKET) or household restrictions.
- **Rank by (priority order):**
  1. **Distance** — prioritize < 5 miles
  2. **Unit count** — match tier (Small < 75, Standard 75–250, Large > 250); if fewer than 6 comps, allow one tier variance
  3. **Building style** — group similar  `building_style` (LOW_RISE / GARDEN / TOWNHOUSE vs. MID_RISE / HIGH_RISE)
  4. **Vintage / quality** — prioritize comps within ±10 years of subject's year (renovation year if available, else year built) and within ±1 improvement rating tier; comps deviating > 15 years or 2+ rating tiers may be included if no closer alternative exists
  5. **Sale date** — give higher priority to more recent sales (`latest_sale_date`).
  6. **Amenities and other features** — weight these before finalizing ranking. Amenities come from `mf_amenities` as JSON strings (`community_amenities`, `unit_amenities`) keyed by category — parse them.

Either return comps with their attributes to the proceeding prompt (including rationale for your selection), or evaluate your selections as they compare to the subject and provide a well-reasoned response to the user's question.

---

## Rent Comps

Your job is to find multifamily rent comps for the subject property.

**Retrieval:** Query property_mfr at progressively wider geographies until 10 eligible are obtained. Properties must have a non-null in-place rent, unit count, and matching `rent_type` and `household_restrictions`. Start with **zipcode** (limit 25) → **census place** (limit 20) → **county** (limit 20). Maximum 3 queries — stop as soon as any single query returns 10 or more.
Filter each step by the matching foreign key on property_mfr (zipcode_id, then census_place_id, then county_id).

In a single combined call per step, pull mf_rent_and_occupancy_snapshot (the comp-set / benchmark rent variant) and mf_property_attributes.

Eligibility filters (all must pass):
 - mf_rent_and_occupancy_snapshot.in_place_rent_latest IS_NOT_NULL
 - mf_property_attributes.unit_count IS_NOT_NULL
 - mf_property_attributes.rent_type EQUALS the subject's (catalog enum casing — observed values MARKET / AFFORDABLE)
 - mf_property_attributes.household_restrictions — match to the subject's value (IS_NULL when the subject is unrestricted, EQUALS otherwise). The domain includes SENIOR, STUDENT, INCOME_RESTRICTED, CORPORATE, MILITARY, ASSISTED_LIVING and others, so do not hardcode — read it at runtime.

**Refine the pool:** Calculate distance from the subject using mf_property_attributes.latitude and mf_property_attributes.longitude (already returned by the candidate pull) for both the subject and each candidate, and keep the closest 15.

**Selection (4–6 comps):**

- **Rank by (priority order):**
  1. **Distance** — prioritize < 5 miles
  2. **Unit-type rent overlap** — identify the subject's bedroom types (0–4 bed); for each comp, check whether it has a non-null value in `mf_asking_rent_sqft_latest_{N}bed` or `mf_in_place_rent_latest_{N}_bed` for at least one matching N; prefer comps that match more bedroom types; a comp with zero overlap may still be selected but should not be chosen over an otherwise comparable comp that has overlap
  3. **Unit count** — match tier (Small < 75, Standard 75–250, Large > 250); if fewer than 6 comps, allow one tier variance
  4. **Building style** — group similar   `building_style` (LOW_RISE / GARDEN / TOWNHOUSE vs. MID_RISE / HIGH_RISE)
  5. **Vintage / quality** — prioritize comps within ±10 years of subject's year (renovation year if available, else year built) and within ±1 improvement rating tier; comps deviating > 15 years or 2+ rating tiers may be included if no closer alternative exists
  6. **Amenities and other features** — Give some weight to amenities and other features before finalizing. Source amenities from mf_amenities (community_amenities and unit_amenities — both free-text strings, so parse rather than expect flags); it is non-own-table and can ride in the same combined call, or be pulled only for the closest-15 to keep early steps lean.

Either return comps with their attributes to the proceeding prompt (including rationale for your selection), or evaluate your selections as they compare to the subject and provide a well-reasoned response to the user's question.

If responding directly to the user, consider whether the property is performing as expected for its segment, and give 1–3 actionable recommendations.
