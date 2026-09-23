# Mapping property-management records

Identify reports by their contents, periods, and units rather than vendor names. Map only
what the requested question needs. Reuse the same normalized records across calculations;
do not make the user provide a prescribed package when existing evidence is sufficient.

## What each record supports

| Contents | Useful for |
|---|---|
| Unit identifiers, actual and market rent, occupancy or vacancy status | Current unit economics and status |
| Lease begin/end dates and notice terms | Unit-specific renewal and marketing timing |
| Expiration counts by month and floorplan | Aggregate roll concentration; not exact unit dates |
| Contacts, tours, applications, approvals, leases, and cancellations | Leasing funnel and possible friction |
| Dated occupancy series | Historical occupancy movement |
| Charges, receipts, concessions, balances, write-offs, and vacancy loss | Reconciliation and payment questions, within the report's accounting definitions |

Inventory columns internally before deriving dependent metrics. A missing column is not
zero. Disclose its absence when it blocks a requested action or changes the conclusion;
do not append an inventory of every unavailable field to the answer.

## Build reliable units and floorplans

Keep one row per physical unit for a snapshot, preserving the original unit identifier,
building, floorplan, and source date. Multiple charges, residents, or leases can create
several rows for a unit; reconcile those before counting or summing rents. Distinguish
physical units, revenue units, occupied units, and down/model/admin units. Exclude
non-revenue units only from measures whose denominator actually calls for revenue units.

Derive beds, baths, and square footage from supplied records, supported unit data, or the
property's public floorplans. Do not guess from a floorplan code. Unresolved floorplans
can remain in totals that do not need a crosswalk; pause their bedroom-specific comparison
and ask for clarification only if it matters to the requested recommendation.

Normalize unit identifiers cautiously. Leading zeros and building prefixes may carry
meaning. Verify a normalization does not merge distinct units; keep ambiguous matches
unmatched rather than borrow another unit's rent, lease date, or listing history.

## Match coverage and status

When combining unit sources, calculate coverage against the relevant report population:
matched revenue units divided by report revenue units, with both counts on the same date
and inclusion basis. Distinguish coverage from listing activity. An off-market unit can
be covered; null listing fields do not prove a unit is unlisted or occupied.

Use an explicit, current status observation for a listing-status conclusion. Missing rows
or missing listing fields remain unknown when status matters. Preserve unmatched subject
units in the calculation set, leaving only source-dependent attributes unresolved.

Reconcile differences using observation dates, accounting definitions, and supporting
records. Zero receipts may reflect timing or prepayments. Vacancy-loss entries may include
adjustments. Neither establishes vacancy, delinquency, or a never-moved-in resident by
itself. Avoid repeating names or other resident identifiers when a unit identifier suffices.

## Expiration and leasing patterns

Reconcile monthly expirations and month-to-month counts to report totals before describing
the roll. Actual per-unit lease-end dates permit exact schedules; aggregate monthly
counts do not. Do not infer unit lease ends from move-in plus twelve months unless a
clearly labeled scenario is useful and that assumption is explicitly supported.

Use an available non-code calculator for monthly counts and shares. Useful investigation heuristics include a
next-quarter expiration count at least 1.3 times the following quarter, or at least 25%
of a floorplan expiring in one month when that floorplan has eight or more units. These
are screening heuristics, not universal operating limits. Show counts when denominators
are small; a zero following-quarter denominator makes the ratio undefined. Seasonality,
lease terms, and staffing determine whether concentration is actually problematic.

For funnel conversion, align periods and definitions: events occurring this month may not
belong to the same prospect cohort. Define denominators for tours, applications, approvals,
and signed leases. A weak stage identifies where to investigate; it does not by itself
prove that price, product, or the manager caused the loss.
