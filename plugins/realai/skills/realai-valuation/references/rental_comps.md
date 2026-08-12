# MF Rental Comps

> Methodology for finding multifamily rental comps. Reusable: this skill is the primary owner; `realai-investment`, `realai-underwriting`, and `realai-property-analysis` (Mark-to-Market and Manager frames) reference this file.

## Job

Find multifamily rent comps for the subject property.

## Retrieval

Query property_mfr at progressively wider geographies until 15 eligible are obtained. Properties must have a non-null in-place rent, unit count, and matching `rent_type`. Start with **zipcode** (limit 25) → **census place** (limit 25) → **county** (limit 25). Maximum 3 queries — stop as soon as any single query returns 15 or more.
Filter each step by the matching foreign key on property_mfr (zipcode_id, then census_place_id, then county_id).

In a single combined call per step, pull mf_rent_and_occupancy_snapshot (the comp-set / benchmark rent variant) and mf_property_attributes.

Eligibility filters (all must pass):
 - mf_rent_and_occupancy_snapshot.in_place_rent_latest IS_NOT_NULL
 - mf_property_attributes.unit_count IS_NOT_NULL
 - mf_property_attributes.rent_type EQUALS the subject's (catalog enum casing — observed values MARKET / AFFORDABLE)

Still retrieve `mf_property_attributes.household_restrictions` for every candidate — it is used at selection, not as a filter. Its format is inconsistent; never filter or compare on the raw value.

## Refine the pool

Calculate distance from the subject using mf_property_attributes.latitude and mf_property_attributes.longitude (already returned by the candidate pull) for both the subject and each candidate. Keep the closest 15 — retaining restriction-matching candidates first, then filling by distance.

## Selection (4–6 comps), ranked by priority order

1. **Distance** — prioritize <5 miles.
2. **Household restrictions** — Normalize each value (subject and comps) to a set of active restrictions by meaning, not format: NULL or nothing affirmed (e.g., an all-false JSON object) = unrestricted; otherwise the set of affirmed restrictions, matching labels case-insensitively (SENIOR ≈ senior_citizen). Uninterpretable values = unknown. Prefer matches; rank unknowns below matches but above mismatches. Select a mismatch only if fewer than 4 matches exist, and flag it in the rationale. The domain includes SENIOR, STUDENT, INCOME_RESTRICTED, CORPORATE, MILITARY, ASSISTED_LIVING and others, so do not hardcode — read it at runtime.
3. **Unit-type rent overlap**: Identify the subject's bedroom types (0–4 bed). For each comp, check whether it has a non-null value in mf_rent_and_occupancy_snapshot.asking_rent_sqft_latest_{N}_bed OR mf_rent_and_occupancy_snapshot.in_place_rent_latest_{N}_bed for at least one matching N (N in 0–4). Prefer comps that match more bedroom types. A comp with zero overlap may still be selected but should not be chosen over an otherwise comparable comp that has overlap.
4. **Unit count** — match tier (Small <75, Standard 75–250, Large >250); allow one tier variance if fewer than 6 qualify.
5. **Building style**  (mf_property_attributes.building_style) — group similar (LOW_RISE / GARDEN / TOWNHOUSE vs. MID_RISE / HIGH_RISE).
6. **Vintage / quality** — prioritize comps within ±10 years of subject's renovation year (or built year if no renovation) and within ±1 improvement rating tier. Comps deviating >15 years or 2+ rating tiers may be included if no closer alternative exists.
7. **Amenities and other features or issues** — Give some weight to amenities and other features before finalizing. Source amenities from mf_amenities (community_amenities and unit_amenities — both free-text strings, so parse rather than expect flags); it is non-own-table and can ride in the same combined call, or be pulled only for the closest-15 to keep early steps lean.

## Output shape

Either return comps with their attributes and rationale to the calling skill, or evaluate selections against the subject and produce a user-facing read.

For a user-facing read, also assess:
- Whether the property is performing as expected for its segment
- 1–3 actionable recommendations
- Asking-vs-in-place spread at subject vs. comps
- Where the subject sits in the comp rent distribution
