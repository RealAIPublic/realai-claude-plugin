# MF Sale Comps

> Methodology for finding multifamily sale comps. Reusable: this skill is the primary owner; `realai-investment`, `realai-underwriting`, and `realai-property-analysis` reference this file.

## Job

Find multifamily sales comps for the subject property.

## Retrieval
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

## Selection (4–6 comps)

**Exclude:** different `rent_type` (AFFORDABLE vs. MARKET) or 'household_restrictions'.

**Rank by, in priority order:**

1. **Distance** — prioritize <5 miles.
2. **Unit count** — match tier on `unit_count` (Small <75, Standard 75–250, Large >250); allow one tier variance if fewer than 6 qualify.
3. **Building style** — group similar  `building_style` (LOW_RISE / GARDEN / TOWNHOUSE vs. MID_RISE / HIGH_RISE).
4. **Vintage / quality** — prioritize comps within ±10 years of subject's renovation year (or built year if no renovation) and within ±1 improvement rating tier. Comps deviating >15 years or 2+ rating tiers may be included if no closer alternative exists.
5. **Sale date** — give higher priority to more recent sales (`latest_sale_date`).
6. **Amenities and other features or issues** — weight these before finalizing ranking. Amenities come from `mf_amenities` as JSON strings (`community_amenities`, `unit_amenities`) keyed by category — parse them. 

## Output shape

Either return comps with their attributes and rationale to the calling skill, or evaluate selections against the subject and produce a user-facing read.

For a user-facing read, also assess:
- Whether subject's basis aligns with the comp set
- $/unit and cap rate positioning of the subject in the comp distribution
- Material outliers and what's driving them
