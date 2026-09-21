# Finding and ranking places

Use when the user wants places that meet criteria or an ordered shortlist. A named-place
comparison does not automatically need a ranking. Property discovery belongs to
realai-multifamily; when a question asks for markets and then buildings within them,
carry the selected geography forward to that skill.

Follow `${CLAUDE_PLUGIN_ROOT}/shared/multi-entity-analysis.md` for consistent populations,
calculations, missing components, and claim verification. Retrieval mechanics remain in
shared/data-retrieval/data-access.md. The guidance here concerns what makes a geographic ranking useful.

## Define a fair comparison

Use the geography, grain, constraints, and priorities already supplied. Ask only when an
unresolved choice would substantially change the candidates or the meaning of “best.”
For an exploratory question, a stated reasonable assumption can be enough to proceed.
Do not require a separate intake exchange or approval of every criterion.

Separate hard constraints from preferences. A budget ceiling or required location may
exclude a place; faster rent growth may improve its standing. A population threshold is
not a universal hard constraint: small communities may be the intended subjects. Where
population is not measured at the chosen grain, use a relevant topic sample count if a
sufficiency check is needed. Do not equate NULL population with an empty geography.

For a single-metric question, sort that measure. For a compound thesis, record each
component's field or derived measure, direction, normalization population, weight, and
whether it came from the user or an analytical assumption. Explain the important choices
with the result; a criteria table helps when it makes the method assessable.

## Choose and combine signals

Prefer fields that express the user's thesis directly. A proxy must be identified; an
available field is not automatically a useful proxy. User priorities control weighting.
Do not quietly add guardrails that change who wins. Present other risks separately or
include them as clearly identified assumptions when they are necessary to interpret fit.

Use the same score scale across components. National percentiles suit national comparisons;
MSA percentiles suit comparison within that MSA. A pool percentile is relative only to
the eligible candidate set. Do not mix raw z-scores and 0–100 percentiles in a weighted sum.
If using percentiles, apply direction after normalization: `100 - percentile` for
lower-is-better measures. For a consistent z-score method, change the sign instead.

Affordability ratios and days on market often read lower-is-better. Migration flow and
cohort fields need particular care: inbound age describes arrivals; outbound age describes
departures; origin/destination IDs are identifiers, not scores. The documented mobility
score reads higher as more stable residents, so confirm its meaning before inverting it.

Compute composites in code and retain component contributions. Inspect close ranks for
sensitivity to assumed weights. A winning composite does not mean a place leads on each
input. Missing components require the common eligibility treatment in the shared guide;
never turn NULLs into zero or silently change weights for individual places.

## Avoid selection bias

A shortlist drawn only from the leaders on one component can miss the best combined
candidate. Prefer the full eligible population when practical. If evidence collection
requires screening, use a broad candidate set across the relevant dimensions and describe
the resulting scope. A limited first page or prescreen is not a complete national ranking.

Use snapshots for comparable current conditions or trailing changes when they answer
the thesis. Add histories when trajectory shape, acceleration, or a numerical projection
matters. A snapshot may carry a usable current measure even when a time-series topic is
unavailable. Grain-specific coverage and query constraints belong to the shared references.

Do not relax user constraints silently to obtain attractive winners. If evidence supports
only a partial shortlist, give that result with the consequential limit. An irrelevant
unused NULL column does not belong in the comparison.

## Distinguish observed from projected opportunity

“Fastest-growing last year” needs observed growth. “Best rental markets” may be answered
from current fundamentals without forecasting every candidate. Use numerical forecasts
only when projected outcomes are part of the requested criteria, following the engine
contract linked from SKILL.md. Preserve confidence differences in the interpretation.
Capital-market band positioning is a historical comparison, not a future cap-rate value.

Make the result easy to compare: sorted bars or a table for candidates, a scatterplot for
a tradeoff, or a map when location adds meaning and reliable coordinates are available.
Interactive weights are useful when the host supports them and preferences drive close
ranks. Explain the differences that matter without imposing a report template.
