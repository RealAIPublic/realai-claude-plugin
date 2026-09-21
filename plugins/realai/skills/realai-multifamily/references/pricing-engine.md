# Unit pricing calculations and decision checks

This reference defines calculation and interpretation rules, not an executable engine.
Run arithmetic in code using the normalized subject records and supported comparisons.
Apply only calculations relevant to the requested units. Use the parent skill's shared
infrastructure guidance before invoking the authoritative NOI or forecasting engines.

## Comparable rent basis

Keep face and net-effective rents separate. For a lease of `L` months with total rent
concessions `C`, net-effective monthly rent is `(face monthly rent × L − C) / L`.
Identify which fees or credits are included and do not mix lease terms without adjustment.
An advertised concession may be conditional; establish applicability before using it.

Estimate achievable rent from comparable size, beds/baths, condition, location, and terms.
Attribute adjustments to evidence; do not invent unit premiums. If the evidence supports
a range, preserve that range instead of presenting an unjustifiably exact target.
The operator's market rent is a cross-check, not automatically achievable rent.

## Current listing episode and vacancy

Validate that a listing date and day count belong to the current episode. A later lease
or move-in can mean the observation describes a completed listing. Review the underlying
dates and current status rather than treating a historical row as a current vacancy.
Compute elapsed days against the analysis date, recording the observation date separately.

Listing duration, physical vacancy, and time since a unit became ready are different
clocks. A unit may be marketed while occupied. Use the correct label and do not replace
one clock with another when a field is absent.

Accounting proration may support an estimate only when the charge basis, month length,
full-month rent, and vacancy-loss definition are known and no adjustments distort the
entry. Under those assumptions, vacancy days in the month may be estimated as
`vacancy loss / applicable monthly rent × days in month`. This does not establish the
start of a vacancy spanning multiple months or days on market. Label estimates; otherwise
leave the action-dependent timing unresolved rather than invent a date.

## Metrics

| Metric | Calculation and interpretation |
|---|---|
| Monthly market gap | Comparable net-effective achievable rent minus current net-effective rent; retain negative gaps |
| Gap percentage | Divide the gap by the disclosed denominator; use market rent for loss-to-lease and current rent for a proposed increase |
| Annualized gross rent gap | Sum included unit gaps × 12; distinguish total net gap from positive-only opportunity |
| Daily vacancy revenue exposure | Achievable monthly rent divided by a disclosed day-count convention; opportunity cost, not guaranteed recoverable income |
| Expiration exposure | Counts and rent gaps for leases actually expiring in a defined window |
| Renewal increase | Proposed face rent relative to current face rent, with concession changes and any applicable cap treated separately |

The full-year run rate of leases rolling within six months is not six-month realized
revenue. A capture scenario needs actual timing, renewal or turnover outcomes, concessions,
downtime, and implementation costs. Do not label gross upside as NOI; operating-engine
inputs must reflect incremental costs rather than apply an average expense ratio as a
marginal pass-through. Numerical forecasts use the forecasting engine when needed.

## Unit decisions

- For a confirmed vacant, ready unit, compare its current ask and terms with supported
  positioning and current activity. Recommend listing or adjustment when evidence supports it.
- For a slow listing, examine exposure, tours, applications, condition, and price.
  Above-normal days on market alone does not prove overpricing. Make a staged change
  conditional on observed activity and an explicit review date; do not promise a lease date.
- For an upcoming renewal, use the actual lease end and verified notice rules. Consider
  retention economics and consistent renewal policies. Do not infer resident-specific
  price tolerance from aggregate household profiles.
- For an above-market lease, preserve the negative gap and assess renewal risk. A flat
  renewal may still be above market; neither a token increase nor a reduction is automatic.
- For payment exceptions or disputed occupancy, reconcile the record before prescribing
  a renewal action. A balance or zero receipts is not an automatic nonrenewal decision.
- For clustered expirations, consider feasible term staggering with the user's policy,
  resident agreement, seasonality, and applicable requirements.

Separate current-condition upside from renovation premiums and include completion timing.
Do not double-count the same rent lift. Dates, prices, and assumptions should be auditable
from the input records; keep unresolved issues visible only where they affect the action.
