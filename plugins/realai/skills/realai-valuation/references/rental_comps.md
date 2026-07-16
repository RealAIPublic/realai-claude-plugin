# MF Rental Comps

> Methodology for finding multifamily rental comps. Reusable: this skill is the primary owner; `realai-investment`, `realai-underwriting`, and `realai-property-analysis` (Mark-to-Market and Manager frames) reference this file.

## Job

Find multifamily rent comps for the subject property.

## Retrieval

Query property_mfr at progressively wider geographies until 10 eligible are obtained. Properties must have a non-null in-place rent, unit count, and matching `rent_type` and `household_restrictions`. Start with **zipcode** (limit 25) → **census place** (limit 20) → **county** (limit 20). Maximum 3 queries — stop as soon as any single query returns 10 or more.
Filter each step by the matching foreign key on property_mfr (zipcode_id, then census_place_id, then county_id).

In a single combined call per step, pull mf_rent_and_occupancy_snapshot (the comp-set / benchmark rent variant) and mf_property_attributes.

Eligibility filters (all must pass):
 - mf_rent_and_occupancy_snapshot.in_place_rent_latest IS_NOT_NULL
 - mf_property_attributes.unit_count IS_NOT_NULL
 - mf_property_attributes.rent_type EQUALS the subject's (catalog enum casing — observed values MARKET / AFFORDABLE)
 - mf_property_attributes.household_restrictions — match to the subject's value (IS_NULL when the subject is unrestricted, EQUALS otherwise). The domain includes SENIOR, STUDENT, INCOME_RESTRICTED, CORPORATE, MILITARY, ASSISTED_LIVING and others, so do not hardcode — read it at runtime.

## Refine the pool

Calculate distance from the subject using mf_property_attributes.latitude and mf_property_attributes.longitude (already returned by the candidate pull) for both the subject and each candidate, and keep the closest 15.

## Selection (4–6 comps), ranked by priority order

1. **Distance** — prioritize <5 miles.
2. **Unit-type rent overlap**: Identify the subject's bedroom types (0–4 bed). For each comp, check whether it has a non-null value in mf_rent_and_occupancy_snapshot.asking_rent_sqft_latest_{N}_bed OR mf_rent_and_occupancy_snapshot.in_place_rent_latest_{N}_bed for at least one matching N (N in 0–4). Prefer comps that match more bedroom types. A comp with zero overlap may still be selected but should not be chosen over an otherwise comparable comp that has overlap.
3. **Unit count** — match tier (Small <75, Standard 75–250, Large >250); allow one tier variance if fewer than 6 qualify.
4. **Building style**  (mf_property_attributes.building_style) — group similar (LOW_RISE / GARDEN / TOWNHOUSE vs. MID_RISE / HIGH_RISE).
5. **Vintage / quality** — prioritize comps within ±10 years of subject's renovation year (or built year if no renovation) and within ±1 improvement rating tier. Comps deviating >15 years or 2+ rating tiers may be included if no closer alternative exists.
6. **Amenities and other features or issues** — Give some weight to amenities and other features before finalizing. Source amenities from mf_amenities (community_amenities and unit_amenities — both free-text strings, so parse rather than expect flags); it is non-own-table and can ride in the same combined call, or be pulled only for the closest-15 to keep early steps lean.

## Output shape

Either return comps with their attributes and rationale to the calling skill, or evaluate selections against the subject and produce a user-facing read.

For a user-facing read, also assess:
- Whether the property is performing as expected for its segment
- 1–3 actionable recommendations
- Asking-vs-in-place spread at subject vs. comps
- Where the subject sits in the comp rent distribution
