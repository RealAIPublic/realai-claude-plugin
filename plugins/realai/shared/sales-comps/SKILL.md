---
name: sales-comps
description: "Use this skill to find multifamily sales comps for a subject property. Trigger when the user asks for: comparable sales, sales comps, recent transactions, market comps for valuation, or price-per-unit benchmarks. This skill queries property sales data at progressively wider geographies, then filters and ranks results to select 4-6 high-quality comps based on proximity, size, building type, vintage, and sale recency."
license: Proprietary
---

# Multifamily Sales Comps

Find and select comparable sales for a subject multifamily property.

## Query Strategy

Query property sales within the last 3 years at progressively wider geographies until the pool reaches 10 properties. **Stop as soon as any single query returns 10 or more results.**

| Step | Geography | Limit |
|------|-----------|-------|
| 1 | Zipcode | 25 |
| 2 | Census Place | 20 |
| 3 | County | 20 |

Maximum 3 queries total.

## Pool Refinement

Once you have a pool of results:

1. Calculate distance from subject for all properties
2. Keep the closest 15 properties for filtering

## Selection Criteria (4-6 Comps)

### Hard Exclusions

Exclude properties with:
- Different `rent_type` (AFFORDABLE vs MARKET)
- Different `household_restrictions`

### Ranking Factors (Priority Order)

1. **Distance** — Prioritize properties <5 miles from subject

2. **Unit Count** — Match size tier:
   | Tier | Units |
   |------|-------|
   | Small | <75 |
   | Standard | 75-250 |
   | Large | >250 |

   If fewer than 6 comps remain, allow one tier variance.

3. **Building Style** — Group similar types:
   - Group A: LOW_RISE, GARDEN, TOWNHOUSE
   - Group B: MID_RISE, HIGH_RISE

4. **Vintage/Quality** — Prioritize comps within:
   - ±10 years of subject's renovation year (or year built if no renovation)
   - ±1 improvement rating tier

   Comps deviating >15 years or 2+ rating tiers may be included only if no closer alternative exists.

5. **Sale Date** — Give higher priority to more recent sales

6. **Amenities & Features** — Give some weight to amenities and other features or issues discovered during analysis before finalizing rankings.

## Output

Either:

1. **Return comps to the proceeding prompt** — Include all relevant attributes and rationale for each selection, OR

2. **Evaluate and respond** — Compare selections to the subject property and provide a well-reasoned response to the user's question.
