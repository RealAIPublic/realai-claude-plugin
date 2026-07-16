# Multifamily Comps — Retrieval & Selection Instructions

Read this file when the manifest or workflow requires sales comps or rent comps for the subject property.

---

## Sales Comps

Your job is to find multifamily sales comps for the subject property.

**Retrieval:** Query property sales within the last 3 years, at progressively wider geographies until the pool reaches 10. Start with zipcode (limit 25), then census place (limit 20), then county (limit 20). Maximum 3 queries — stop as soon as any single query returns 10 or more.

**Refine the pool:** Calculate distance from subject for all returned properties and keep the closest 15.

**Selection (4–6 comps):**

- **Exclude:** Properties with a different `rent_type` (AFFORDABLE vs. MARKET) or household restrictions.
- **Rank by (priority order):**
  1. **Distance** — prioritize < 5 miles
  2. **Unit count** — match tier (Small < 75, Standard 75–250, Large > 250); if fewer than 6 comps, allow one tier variance
  3. **Building style** — group similar (LOW_RISE / GARDEN / TOWNHOUSE vs. MID_RISE / HIGH_RISE)
  4. **Vintage / quality** — prioritize comps within ±10 years of subject's year (renovation year if available, else year built) and within ±1 improvement rating tier; comps deviating > 15 years or 2+ rating tiers may be included if no closer alternative exists
  5. **Sale date** — give higher priority to more recent sales
  6. **Amenities and other features** — give some weight before finalizing ranking

Either return comps with their attributes to the proceeding prompt (including rationale for your selection), or evaluate your selections as they compare to the subject and provide a well-reasoned response to the user's question.

---

## Rent Comps

Your job is to find multifamily rent comps for the subject property.

**Retrieval:** Query multifamily properties at progressively wider geographies until you obtain 10 eligible. Properties must have a non-null in-place rent, unit count, and the `rent_type` and household restrictions must equal those of the subject. Start with zipcode (limit 25), then census place (limit 20), then county (limit 20). Maximum 3 queries — stop as soon as any single query returns 10 or more.

**Refine the pool:** Calculate distance from subject for all returned properties and keep the closest 15.

**Selection (4–6 comps):**

- **Rank by (priority order):**
  1. **Distance** — prioritize < 5 miles
  2. **Unit-type rent overlap** — identify the subject's bedroom types (0–4 bed); for each comp, check whether it has a non-null value in `mf_asking_rent_sqft_latest_{N}bed` or `mf_in_place_rent_latest_{N}_bed` for at least one matching N; prefer comps that match more bedroom types; a comp with zero overlap may still be selected but should not be chosen over an otherwise comparable comp that has overlap
  3. **Unit count** — match tier (Small < 75, Standard 75–250, Large > 250); if fewer than 6 comps, allow one tier variance
  4. **Building style** — group similar (LOW_RISE / GARDEN / TOWNHOUSE vs. MID_RISE / HIGH_RISE)
  5. **Vintage / quality** — prioritize comps within ±10 years of subject's year (renovation year if available, else year built) and within ±1 improvement rating tier; comps deviating > 15 years or 2+ rating tiers may be included if no closer alternative exists
  6. **Amenities and other features** — give some weight before finalizing ranking

Either return comps with their attributes to the proceeding prompt (including rationale for your selection), or evaluate your selections as they compare to the subject and provide a well-reasoned response to the user's question.

If responding directly to the user, consider whether the property is performing as expected for its segment, and give 1–3 actionable recommendations.
