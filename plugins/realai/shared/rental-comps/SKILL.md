---
name: rental-comps
description: "Use this skill to find multifamily rent comps for a subject property. Trigger when the user asks for: rental comps, rent comparables, market rent analysis, rent benchmarks, or in-place rent comparisons. This skill queries properties with rent data at progressively wider geographies, then filters and ranks results to select 8-10 high-quality comps based on proximity, household restrictions, unit-type overlap, size, building type, and vintage."
license: Proprietary
---

# Multifamily Rental Comps

Find and select comparable rental properties for a subject multifamily property.

## Query Strategy

Query property_mfr at progressively wider geographies. In a single combined call per step, pull mf_rent_and_occupancy_snapshot (comp-set / benchmark rent variant) and mf_property_attributes. Filter each step by the matching foreign key on property_mfr. Filter the county step on county_id only — no NOT_IN exclusion on census_place_id (it silently drops NULL rows). Dedupe happens in Pool Refinement.

| Step | Geography | Foreign Key |
|------|-----------|-------------|
| 1 | Census Place | census_place_id |
| 2 | County | county_id |

**Retrieve ALL eligible rows at each geography step, paginating until the result set is exhausted — never trim, rank, or stop mid-pagination.** Results are not distance-ordered, so a partial page pull can silently drop the nearest comps. Proceed to the wider geography only if fewer than 20 eligible candidates exist after full retrieval. Exclude the subject property itself from all candidate pulls.

Maximum 3 query steps total. Pagination continuations don't count toward the budget — only geography steps do. Keep the bundle to these two non-own-table topics; do not add separate-data-source topics (rent_roll_latest, mf_rent_ts*) to this loop — each would force its own call.

Still retrieve mf_property_attributes.household_restrictions for every candidate — used at selection, not as a filter. Its format is inconsistent; never filter or compare on the raw value.

### Eligibility Requirements

Properties must have:
- Non-null `mf_rent_and_occupancy_snapshot.in_place_rent_latest`
- Non-null `mf_property_attributes.unit_count`
- `mf_property_attributes.rent_type` EQUALS the subject's (catalog enum casing — observed values MARKET / AFFORDABLE)

## Pool Refinement

Once retrieval is complete for the geography step:
1. If the county step was needed, merge with census-place results and dedupe by property ID — dedupe here only, never in the query
2. Calculate distance from subject using mf_property_attributes.latitude/longitude for subject and each candidate
3. Keep the closest 15 — retaining restriction-matching candidates first, then filling by distance

## Selection Criteria (8-10 Comps)

### Ranking Factors (Priority Order)

1. **Distance** — Prioritize properties <5 miles from subject
2. **Household Restrictions** — Normalize each value (subject and comps) to a set of active restrictions by meaning, not format: NULL or nothing affirmed (e.g., all-false JSON) = unrestricted; otherwise the set of affirmed restrictions, matching labels case-insensitively (SENIOR ≈ senior_citizen). Uninterpretable values = unknown. Prefer matches; rank unknowns below matches but above mismatches. Select a mismatch only if fewer than 8 matches exist, and flag it in the rationale.
3. **Unit-Type Rent Overlap** — Identify the subject's bedroom types (0-4 bed). For each comp, check for a non-null value in:
   - `mf_rent_and_occupancy_snapshot.asking_rent_latest_{N}_bed`, OR
   - `mf_rent_and_occupancy_snapshot.in_place_rent_latest_{N}_bed`
   ...for at least one matching N. Prefer comps that match more bedroom types. A comp with zero overlap may still be selected but should not be chosen over an otherwise comparable comp that has overlap.
4. **Unit Count** — Match size tier:
   | Tier | Units |
   |------|-------|
   | Small | <75 |
   | Standard | 75-250 |
   | Large | >250 |
   If fewer than 10 candidates match the subject's tier, allow ±1 tier.
5. **Building Style** — Group similar types:
   - Low-density: LOW_RISE, GARDEN, TOWNHOUSE
   - Mid/high-density: MID_RISE, HIGH_RISE
   The live domain also includes SINGLE_FAMILY_HOME and MOBILE_HOME_RV_PARK, which fall in neither group: treat each as its own group (comparable only to a subject of the same style). Read the full set of distinct values at runtime before bucketing.
6. **Vintage/Quality** — Prioritize comps within:
   - ±10 years of subject's renovation year (or year built if no renovation)
   - ±1 tier on `mf_property_attributes.improvements_rating`, an ordinal letter grade (A/B/C observed; A highest); ±1 tier = one letter step
   Comps deviating >15 years or 2+ rating tiers may be included only if no closer alternative exists.
7. **Amenities & Features** — Give some weight before finalizing. Source from mf_amenities (community_amenities and unit_amenities — free-text, so parse rather than expect flags) via one dedicated query for the closest-15 only, after the retrieval loop; do not add it to the retrieval bundle.

## Output

Either:
1. **Return comps to the next prompt** — Include all relevant attributes and rationale for each selection, OR
2. **Evaluate and respond directly** — Compare selections to the subject and provide a well-reasoned response to the user's question.

### When Responding Directly

Consider whether the property is performing as expected for its segment, and provide **1-3 actionable recommendations**.
